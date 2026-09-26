"""CPython simulation of the Splat Companion's combined ESP-NOW + BLE loop.

Reuses test_sim.py's harness: the real modem/main.py runs in a thread behind
a fake UART and a fake ESP-NOW radio, and the real host espnow_manager.py
talks to it. On top of that, the real SplatCompanionEUM code (companion.py,
splat_link.py and its unmodified lib/ble_splat.py) runs against a fake
ubluetooth whose IRQ events arrive from a separate thread, as scheduled
BLE IRQs do on the device.

Run: python tests/test_splat_companion.py
"""

import heapq
import json
import os
import sys
import threading
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import test_sim as S  # noqa: E402  (installs fakes, starts the modem thread)

ROOT = os.path.join(HERE, "..")
COMP_DIR = os.path.join(ROOT, "SplatCompanionEUM")
BAG3_LIB = os.path.join(ROOT, "..", "..", "lib")
sys.path.insert(0, COMP_DIR)
sys.path.append(os.path.join(COMP_DIR, "lib"))

WAND_MAC = S.WAND_MAC
WAND = "11:22:33:44:55:66"
WAND2_MAC = bytes.fromhex("665544332211")
WAND2 = "66:55:44:33:22:11"
SPLAT_ADDR = bytes.fromhex("AB420000 7EB6".replace(" ", ""))
SPLAT = "AB:42:00:00:7E:B6"


# ─── Fake ubluetooth ─────────────────────────

class UUID:
    def __init__(self, v):
        self.v = v

    def __eq__(self, other):
        return isinstance(other, UUID) and other.v == self.v

    def __hash__(self):
        return hash(self.v)


H_SVC_START, H_SVC_END = 10, 20
H_WRITE, H_RECV = 13, 16            # fff3 (write), fff4 (notify)

CMD_NAMES = {
    (0x01, 0x00): "keepAlive", (0x02, 0x00): "soundOff",
    (0x03, 0x00): "allLEDsOff", (0x04, 0x00): "allTasksOff",
    (0x05, 0x00): "readSwitches", (0x00, 0x20): "playSound",
    (0x01, 0x50): "setLEDs", (0x00, 0x40): "noteOn", (0x01, 0x40): "noteOff",
    (0x00, 0x10): "identify",
}
NOISE = ("keepAlive", "readSwitches")


class BLE:
    """Singleton like ubluetooth.BLE; one fake Splat peripheral in range."""
    _inst = None

    def __new__(cls):
        if BLE._inst is None:
            BLE._inst = super().__new__(cls)
            BLE._inst._setup()
        return BLE._inst

    def _setup(self):
        self.handler = None
        self.is_active = False
        self.lock = threading.Lock()
        self.q = []
        self.seq = 0
        self.scanning = False
        self.pending_connect = False
        self.conn = None
        self.subscribed = False
        self.available = True        # Splat advertising and connectable
        self.delay_ms = 30
        self.writes = []             # (t_ms, name, bytes)
        self.next_conn = 1
        threading.Thread(target=self._dispatch, daemon=True).start()

    # event queue: delivered from a separate thread
    def _later(self, ms, event, data):
        with self.lock:
            self.seq += 1
            heapq.heappush(self.q, (time.monotonic() + ms / 1000, self.seq, event, data))

    def _dispatch(self):
        while True:
            item = None
            with self.lock:
                if self.q and self.q[0][0] <= time.monotonic():
                    item = heapq.heappop(self.q)
            if item is None:
                time.sleep(0.001)
                continue
            _, _, event, data = item
            if callable(event):
                event()
            elif self.handler is not None:
                self.handler(event, data)

    # ubluetooth API used by ble_splat.py / splat_link.py
    def active(self, v=None):
        if v is not None:
            self.is_active = bool(v)
        return self.is_active

    def irq(self, handler):
        self.handler = handler

    def gap_scan(self, duration, interval_us=None, window_us=None):
        if duration is None:
            if self.scanning:
                self.scanning = False
                self._later(1, 6, ())
            return
        if self.scanning:
            raise OSError(114)       # EALREADY
        self.scanning = True
        self._later(self.delay_ms, self._adv, None)

    def _adv(self):
        if self.scanning and self.available and self.handler:
            self.handler(5, (0, memoryview(SPLAT_ADDR), 0, -50, b"\x06\x09Splat"))
        elif self.scanning:
            self._later(self.delay_ms, self._adv, None)

    def gap_connect(self, addr_type, addr=None, *a):
        if addr_type is None:
            self.pending_connect = False
            return
        self.pending_connect = True
        self._later(self.delay_ms, self._complete_connect, None)

    def _complete_connect(self):
        if not self.pending_connect:
            return
        self.pending_connect = False
        if not self.available:
            return                   # stays pending forever: link times out
        self.conn = self.next_conn
        self.next_conn += 1
        self.handler(7, (self.conn, 0, memoryview(SPLAT_ADDR)))

    def gattc_discover_services(self, conn):
        self._later(5, 9, (conn, H_SVC_START, H_SVC_END, UUID(0xfff0)))
        self._later(6, 10, (conn, 0))

    def gattc_discover_characteristics(self, conn, start, end):
        self._later(5, 11, (conn, H_WRITE - 1, H_WRITE, 0x0C, UUID(0xfff3)))
        self._later(5, 11, (conn, H_RECV - 1, H_RECV, 0x10, UUID(0xfff4)))
        self._later(6, 12, (conn, 0))

    def gattc_write(self, conn, handle, data, mode=0):
        if conn is None or conn != self.conn:
            raise OSError(128)       # ENOTCONN
        data = bytes(data)
        if handle == H_RECV + 1:
            self.subscribed = data == b"\x01\x00"
            return
        assert handle == H_WRITE, handle
        name = CMD_NAMES.get((data[0], data[1]), "?%02X%02X" % (data[0], data[1]))
        self.writes.append((time.ticks_ms(), name, data))

    def gap_disconnect(self, conn):
        if conn == self.conn:
            self.conn = None
            self.subscribed = False
            self._later(1, 8, (conn, 0, memoryview(SPLAT_ADDR)))

    # test controls
    def button(self, pressed):
        assert self.conn is not None and self.subscribed
        self._later(1, 18, (self.conn, H_RECV, bytes([3, 0, 1 if pressed else 0])))

    def drop(self):
        conn = self.conn
        self.conn = None
        self.subscribed = False
        self._later(1, 8, (conn, 0, memoryview(SPLAT_ADDR)))

    def cmds(self, since=0, noise=False):
        return [(n, d) for t, n, d in self.writes[since:] if noise or n not in NOISE]


ubluetooth = types.ModuleType("ubluetooth")
ubluetooth.BLE = BLE
ubluetooth.UUID = UUID
sys.modules["ubluetooth"] = ubluetooth
micropython = types.ModuleType("micropython")
micropython.const = lambda x: x
sys.modules["micropython"] = micropython

import companion as C          # noqa: E402
import splat_link as L         # noqa: E402

ble = BLE()


class FakeLeds:
    def __init__(self):
        self.last = None

    def show(self, color, breathe, now):
        self.last = (color, breathe)


# ─── Helpers ─────────────────────────────────

class Runner:
    def __init__(self, comp):
        self.comp = comp
        self.max_step_ms = 0

    def run(self, ms, until=None):
        end = time.monotonic() + ms / 1000
        while time.monotonic() < end:
            t0 = time.monotonic()
            self.comp.step()
            dt = (time.monotonic() - t0) * 1000
            if dt > self.max_step_ms:
                self.max_step_ms = dt
            if until is not None and until():
                return True
            time.sleep_ms(1)
        return until is None


def inject(mac, obj):
    S.radio().inject(mac, json.dumps(obj).encode())


def air_since(n):
    return S.radio().air[n:]


def splat_events(air):
    out = []
    for mac, data, sync in air:
        if b"splat_event" in data:
            d = json.loads(data)
            out.append((mac, d["event"], d["splat"], sync))
    return out


def press_release(r, hold_ms):
    r.run(100)                       # past ble_splat's 80 ms button debounce
    ble.button(True)
    assert r.run(500, lambda: r.comp.pressed), "press not seen"
    r.run(hold_ms)
    ble.button(False)
    assert r.run(500, lambda: not r.comp.pressed), "release not seen"


# ─── Tests ───────────────────────────────────

def test_copies_match(r):
    host_lib = os.path.join(ROOT, "host", "lib")
    for name, src in (("espnow_manager.py", host_lib), ("eum_proto.py", host_lib),
                      ("ble_splat.py", BAG3_LIB), ("hubtype.py", BAG3_LIB)):
        with open(os.path.join(COMP_DIR, "lib", name), "rb") as f:
            a = f.read()
        with open(os.path.join(src, name), "rb") as f:
            b = f.read()
        assert a == b, "SplatCompanionEUM/lib/%s differs from %s" % (name, src)


def test_parse_chain(r):
    steps, errs = C.parse_chain([["turnred", "cat"], "note_c_high", ["notea"]])
    assert steps == [((255, 0, 0), 19, None), (None, None, (0, 5)),
                     (None, None, None)], steps
    assert errs == ["group 2: unknown action 'notea'"], errs
    steps, errs = C.parse_chain("turnred")
    assert steps == [] and errs, errs


def test_espnow_serviced_while_ble_connecting(r):
    ble.delay_ms = 400               # slow advertising + connect
    inject(WAND_MAC, {"type": "splat_config",
                      "actions": [["turnred", "cat"], ["turnblue", "note_c"]]})
    assert r.run(2000, lambda: r.comp.config is not None)
    assert not r.comp.link.ready, "expected config before BLE came up"
    assert r.comp.owner == WAND and WAND_MAC in S.radio().peers
    assert r.comp.leds.last == C.LED_BLE_WAIT
    assert r.run(5000, lambda: r.comp.link.ready), r.comp.link.state_name()
    ble.delay_ms = 30
    r.run(C.CONNECT_FLASH_MS + 100)
    assert ble.cmds()[:2] == [("setLEDs", bytes([1, 0x50, 0xFF, 0x3F, 0, 255, 0])),
                              ("allLEDsOff", bytes([3, 0]))], ble.cmds()
    assert r.comp.leds.last == C.LED_CONFIGURED


def test_press_plays_config_and_relays(r):
    w0, a0 = len(ble.writes), len(S.radio().air)
    press_release(r, C.GROUP_GAP_MS + 150)
    names = [n for n, _ in ble.cmds(w0)]
    assert names == ["setLEDs", "playSound", "setLEDs", "noteOn",
                     "allTasksOff", "allLEDsOff"], names
    cmds = ble.cmds(w0)
    assert cmds[0][1][4:] == bytes([255, 0, 0]) and cmds[2][1][4:] == bytes([0, 0, 255])
    assert cmds[1][1] == bytes([0, 0x20, 19, 255])
    assert cmds[3][1] == bytes([0, 0x40, 0, 4, 127, 17])
    ev = splat_events(air_since(a0))
    assert ev == [(WAND_MAC, "press", SPLAT, True),
                  (WAND_MAC, "release", SPLAT, True)], ev


def test_release_before_second_group(r):
    w0 = len(ble.writes)
    press_release(r, 100)
    r.run(C.GROUP_GAP_MS + 100)
    names = [n for n, _ in ble.cmds(w0)]
    assert names == ["setLEDs", "playSound", "allTasksOff", "allLEDsOff"], names


def test_short_tap_not_stuck(r):
    # ble_splat's own debounce drops a release < 80 ms after the press and
    # leaves the button "pressed"; SplatLink re-checks the raw state.
    w0, a0 = len(ble.writes), len(S.radio().air)
    press_release(r, 20)
    names = [n for n, _ in ble.cmds(w0)]
    assert names == ["setLEDs", "playSound", "allTasksOff", "allLEDsOff"], names
    ev = [e for _, e, _, _ in splat_events(air_since(a0))]
    assert ev == ["press", "release"], ev


def test_splat_cmd_direct(r):
    w0 = len(ble.writes)
    inject(WAND2_MAC, {"type": "splat_cmd", "actions": [["turnyellow", "note_e"]]})
    r.run(C.NOTE_HOLD_MS + 150)
    names = [n for n, _ in ble.cmds(w0)]
    assert names == ["setLEDs", "noteOn", "noteOff"], names
    assert r.comp.owner == WAND2
    assert WAND2_MAC in S.radio().peers and WAND_MAC not in S.radio().peers
    w1 = len(ble.writes)
    inject(WAND2_MAC, {"type": "splat_cmd", "off": True})
    r.run(100)
    assert [n for n, _ in ble.cmds(w1)] == ["allTasksOff", "allLEDsOff"]
    bad = r.comp.counters["bad_msgs"]
    inject(WAND2_MAC, {"type": "splat_cmd"})
    r.run(100)
    assert r.comp.counters["bad_msgs"] == bad + 1


def test_stop_clears_and_press_broadcasts(r):
    inject(WAND2_MAC, {"type": "stop"})
    assert r.run(500, lambda: r.comp.config is None and r.comp.owner is None)
    r.run(50)
    assert WAND2_MAC not in S.radio().peers
    assert r.comp.leds.last == C.LED_READY
    w0, a0 = len(ble.writes), len(S.radio().air)
    press_release(r, 100)
    r.run(50)
    assert ble.cmds(w0) == [], ble.cmds(w0)
    ev = splat_events(air_since(a0))
    assert ev == [(S.BCAST, "press", SPLAT, False),
                  (S.BCAST, "release", SPLAT, False)], ev


def test_ble_drop_espnow_keeps_flowing(r):
    rx0 = r.comp.counters["rx"]
    ble.available = False
    ble.drop()
    assert r.run(500, lambda: not r.comp.link.ready)
    for i in range(20):
        inject(WAND_MAC, ["turnred", "turnblue"])
    inject(WAND_MAC, {"type": "splat_config", "actions": [["turngreen", "dog"]]})
    assert r.run(1000, lambda: r.comp.counters["rx"] == rx0 + 21), r.comp.counters
    assert not r.comp.link.ready
    assert r.comp.owner == WAND
    ble.available = True
    assert r.run(L.CONNECT_TIMEOUT_MS + L.RETRY_BACKOFF_MS + 2000,
                 lambda: r.comp.link.ready), r.comp.link.state_name()
    r.run(C.CONNECT_FLASH_MS + 100)
    w0 = len(ble.writes)
    press_release(r, 100)
    names = [n for n, _ in ble.cmds(w0)]
    assert names == ["setLEDs", "playSound", "allTasksOff", "allLEDsOff"], names


def test_connect_timeout_retries(r):
    saved = L.CONNECT_TIMEOUT_MS, L.RETRY_BACKOFF_MS
    L.CONNECT_TIMEOUT_MS, L.RETRY_BACKOFF_MS = 300, 100
    try:
        ble.available = False
        f0 = r.comp.link.failed_attempts
        ble.drop()
        rx0 = r.comp.counters["rx"]
        inject(WAND_MAC, ["turnred"])
        r.run(1200)
        assert r.comp.link.failed_attempts >= f0 + 2, r.comp.link.failed_attempts
        assert r.comp.counters["rx"] == rx0 + 1
        ble.available = True
        assert r.run(2000, lambda: r.comp.link.ready), r.comp.link.state_name()
    finally:
        L.CONNECT_TIMEOUT_MS, L.RETRY_BACKOFF_MS = saved
    r.run(C.CONNECT_FLASH_MS + 100)


def test_burst_during_playback(r):
    c0 = r.comp.counters["configs"]
    inject(WAND_MAC, {"type": "splat_config", "actions": [
        ["turnred", "note_c"], ["turnblue", "note_d"], ["turngreen", "note_e"],
        ["turnyellow", "note_f"], ["turnwhite", "note_g"]]})
    assert r.run(500, lambda: r.comp.counters["configs"] == c0 + 1)
    rx0 = r.comp.counters["rx"]
    w0 = len(ble.writes)
    r.max_step_ms = 0
    ble.button(True)
    for i in range(60):
        inject(WAND2_MAC, {"type": "burst", "n": i})
    r.run(C.KEEPALIVE_MS * 2 + 300)
    ble.button(False)
    r.run(200)
    assert r.comp.counters["rx"] == rx0 + 60, (r.comp.counters["rx"], rx0)
    names = [n for n, _ in ble.cmds(w0)]
    assert names.count("noteOn") == 5 and names[-2:] == ["allTasksOff", "allLEDsOff"], names
    ka = [t for t, n, _ in ble.writes[w0:] if n == "keepAlive"]
    gaps = [b - a for a, b in zip(ka, ka[1:])]
    assert len(ka) >= 2 and max(gaps) <= C.KEEPALIVE_MS + 100, (ka, gaps)
    sw = [t for t, n, _ in ble.writes[w0:] if n == "readSwitches"]
    sgaps = [b - a for a, b in zip(sw, sw[1:])]
    assert max(sgaps) <= C.SWITCH_POLL_MS + 100, sgaps
    assert r.max_step_ms < 150, r.max_step_ms


def test_modem_reset_restores_owner_peer(r):
    S.radio().peers.clear()
    S.modem().peers.clear()
    S.modem().boot_id = (S.modem().boot_id + 1) & 0xFF
    r.run(50)
    assert WAND_MAC in S.radio().peers
    a0 = len(S.radio().air)
    press_release(r, 50)
    ev = splat_events(air_since(a0))
    assert ev and ev[0][:2] == (WAND_MAC, "press"), ev


def test_shutdown_does_not_stop_owner(r):
    a0 = len(S.radio().air)
    r.comp.shutdown()
    stops = [m for m, d, s in air_since(a0) if b'"stop"' in d]
    assert stops == [], stops
    assert not r.comp.mgr.is_active


if __name__ == "__main__":
    mgr = S.EM.ESPNowManager()
    mgr.init()
    link = L.SplatLink()
    comp = C.Companion(mgr, link, FakeLeds())
    r = Runner(comp)
    tests = [
        test_copies_match, test_parse_chain,
        test_espnow_serviced_while_ble_connecting,
        test_press_plays_config_and_relays, test_release_before_second_group,
        test_short_tap_not_stuck,
        test_splat_cmd_direct, test_stop_clears_and_press_broadcasts,
        test_ble_drop_espnow_keeps_flowing, test_connect_timeout_retries,
        test_burst_during_playback, test_modem_reset_restores_owner_peer,
        test_shutdown_does_not_stop_owner,
    ]
    for fn in tests:
        fn(r)
        print("ok  ", fn.__name__)
    print("counters", comp.counters)
    print("link attempts=%d connects=%d drops=%d failed=%d max_step_ms=%.1f"
          % (link.attempts, link.connects, link.drops, link.failed_attempts,
             r.max_step_ms))
    S._stop.set()
    S.t.join(1)
    print("%d passed" % len(tests))
