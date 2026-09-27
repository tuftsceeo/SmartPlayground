"""CPython simulation of the Splat Companion's idle station (ESP-NOW + BLE).

Reuses ../EspnowModem/tests/test_sim.py's harness: the real modem/main.py
runs in a thread behind a fake UART and a fake ESP-NOW radio, and the real
host espnow_manager.py talks to it. On top of that, the real SplatCompanion
code (companion.py, splat_api.py, splat_link.py and its unmodified
lib/ble_splat.py) runs
against a fake ubluetooth whose IRQ events arrive from a separate thread,
as scheduled BLE IRQs do on the device.

Run: python SplatCompanion/test_splat_companion.py
"""

import heapq
import json
import os
import sys
import threading
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
EUM_TESTS = os.path.join(HERE, "..", "EspnowModem", "tests")
sys.path.insert(0, EUM_TESTS)

import test_sim as S  # noqa: E402  (installs fakes, starts the modem thread)

EUM_ROOT = os.path.join(EUM_TESTS, "..")
COMP_DIR = HERE
BAG3_LIB = os.path.join(HERE, "..", "..", "lib")
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


class Periph:
    """One fake Splat: address, advertising/connectable flag, connection."""
    def __init__(self, addr):
        self.addr = addr
        self.name = ":".join("%02X" % x for x in addr)
        self.available = True
        self.conn = None
        self.subscribed = False


class BLE:
    """Singleton like ubluetooth.BLE; fake Splat peripherals in range.

    periphs[0] is the Splat the single-link tests use; available, conn,
    subscribed, button() and drop() default to it. Advertising cycles
    through every available, unconnected peripheral while a scan runs.
    """
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
        self.pending = None          # Periph a gap_connect is waiting on
        self.periphs = [Periph(SPLAT_ADDR)]
        self._adv_i = 0
        self.delay_ms = 30
        self.writes = []             # (t_ms, name, bytes), every peripheral
        self.writes_by = []          # (periph index, name)
        self.next_conn = 1
        threading.Thread(target=self._dispatch, daemon=True).start()

    # single-Splat shorthands (periphs[0])
    @property
    def available(self):
        return self.periphs[0].available

    @available.setter
    def available(self, v):
        self.periphs[0].available = v

    @property
    def conn(self):
        return self.periphs[0].conn

    @property
    def subscribed(self):
        return self.periphs[0].subscribed

    def _periph_by_conn(self, conn):
        for p in self.periphs:
            if p.conn is not None and p.conn == conn:
                return p
        return None

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

    # ubluetooth API used by ble_splat.py / splat_link.py / splat_hub.py
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
        if not self.scanning:
            return
        cands = [p for p in self.periphs if p.available and p.conn is None]
        if cands and self.handler:
            p = cands[self._adv_i % len(cands)]
            self._adv_i += 1
            self.handler(5, (0, memoryview(p.addr), 0, -50, b"\x06\x09Splat"))
        if self.scanning:
            self._later(self.delay_ms, self._adv, None)

    def gap_connect(self, addr_type, addr=None, *a):
        if addr_type is None:
            self.pending = None
            return
        target = bytes(addr)
        self.pending = None
        for p in self.periphs:
            if p.addr == target:
                self.pending = p
        self._later(self.delay_ms, self._complete_connect, None)

    def _complete_connect(self):
        p = self.pending
        if p is None:
            return
        self.pending = None
        if not p.available:
            return                   # stays pending forever: link times out
        p.conn = self.next_conn
        self.next_conn += 1
        self.handler(7, (p.conn, 0, memoryview(p.addr)))

    def gattc_discover_services(self, conn):
        self._later(5, 9, (conn, H_SVC_START, H_SVC_END, UUID(0xfff0)))
        self._later(6, 10, (conn, 0))

    def gattc_discover_characteristics(self, conn, start, end):
        self._later(5, 11, (conn, H_WRITE - 1, H_WRITE, 0x0C, UUID(0xfff3)))
        self._later(5, 11, (conn, H_RECV - 1, H_RECV, 0x10, UUID(0xfff4)))
        self._later(6, 12, (conn, 0))

    def gattc_write(self, conn, handle, data, mode=0):
        p = self._periph_by_conn(conn) if conn is not None else None
        if p is None:
            raise OSError(128)       # ENOTCONN
        data = bytes(data)
        if handle == H_RECV + 1:
            p.subscribed = data == b"\x01\x00"
            return
        assert handle == H_WRITE, handle
        name = CMD_NAMES.get((data[0], data[1]), "?%02X%02X" % (data[0], data[1]))
        self.writes.append((time.ticks_ms(), name, data))
        self.writes_by.append((self.periphs.index(p), name))

    def gap_disconnect(self, conn):
        p = self._periph_by_conn(conn)
        if p is not None:
            p.conn = None
            p.subscribed = False
            self._later(1, 8, (conn, 0, memoryview(p.addr)))

    # test controls
    def button(self, pressed, i=0):
        p = self.periphs[i]
        assert p.conn is not None and p.subscribed
        self._later(1, 18, (p.conn, H_RECV, bytes([3, 0, 1 if pressed else 0])))

    def drop(self, i=0):
        p = self.periphs[i]
        conn = p.conn
        p.conn = None
        p.subscribed = False
        self._later(1, 8, (conn, 0, memoryview(p.addr)))

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
import splat_api as A          # noqa: E402
import splat_link as L         # noqa: E402
import splat_hub as HUB        # noqa: E402

ble = BLE()


class FakeLeds:
    n = 3

    def __init__(self):
        self.last = None

    def show(self, color, breathe, now):
        self.last = (color, breathe)

    def show_each(self, colors):
        self.last = ("each", tuple(colors))


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


def press_release(r, hold_ms):
    """Press and release the fake Splat's button; wait for SplatLink to
    accept both edges."""
    link = r.comp.link
    r.run(100)                       # past the 80 ms button debounce
    ble.button(True)
    assert r.run(500, lambda: link.splat_pressed), "press not seen"
    r.run(hold_ms)
    ble.button(False)
    assert r.run(500, lambda: not link.splat_pressed), "release not seen"


# ─── Tests ───────────────────────────────────

def test_copies_match(r):
    # hubtype.py is deliberately NOT checked here: this tree's entry now
    # differs from MockWand's/Bag3/Code/lib's by design (nfc_addr, has_nfc,
    # i2c_freq) -- see the device-tree README.
    host_lib = os.path.join(EUM_ROOT, "host", "lib")
    for name, src in (("espnow_manager.py", host_lib), ("eum_proto.py", host_lib),
                      ("ble_splat.py", BAG3_LIB)):
        with open(os.path.join(COMP_DIR, "lib", name), "rb") as f:
            a = f.read()
        with open(os.path.join(src, name), "rb") as f:
            b = f.read()
        assert a == b, "SplatCompanion/lib/%s differs from %s" % (name, src)


def test_no_bridge_left(r):
    with open(os.path.join(COMP_DIR, "companion.py")) as f:
        src = f.read()
    code = src[src.index('"""', 3) + 3:]        # past the module docstring
    for word in ("splat_config", "splat_cmd", "splat_event", "add_peer",
                 "send_to"):
        assert word not in code, "companion.py still handles %s" % word


def test_espnow_serviced_while_ble_connecting(r):
    ble.delay_ms = 400               # slow advertising + connect
    rx0 = r.comp.counters["rx"]
    inject(WAND_MAC, {"type": "score", "n": 1})
    assert r.run(2000, lambda: r.comp.counters["rx"] == rx0 + 1)
    assert not r.comp.link.ready, "expected the message before BLE came up"
    assert r.comp.leds.last == C.LED_BLE_WAIT
    assert r.run(5000, lambda: r.comp.link.ready), r.comp.link.state_name()
    ble.delay_ms = 30
    r.run(100)
    assert r.comp.leds.last == C.LED_READY
    assert r.comp.counters["ble_up"] == 1
    assert ble.cmds() == [], ble.cmds()


def test_idle_press_does_nothing(r):
    w0, a0 = len(ble.writes), len(S.radio().air)
    p0 = r.comp.counters["idle_presses"]
    press_release(r, 100)
    r.run(50)
    assert r.comp.counters["idle_presses"] == p0 + 1
    assert ble.cmds(w0) == [], ble.cmds(w0)
    assert air_since(a0) == [], air_since(a0)


def test_bridge_messages_ignored(r):
    w0, a0 = len(ble.writes), len(S.radio().air)
    i0 = r.comp.counters["ignored"]
    inject(WAND_MAC, {"type": "splat_config", "actions": [["turnred", "cat"]]})
    inject(WAND2_MAC, {"type": "splat_cmd", "actions": [["turnyellow"]]})
    assert r.run(500, lambda: r.comp.counters["ignored"] == i0 + 2), r.comp.counters
    press_release(r, 100)
    r.run(50)
    assert ble.cmds(w0) == [], ble.cmds(w0)
    assert air_since(a0) == [], air_since(a0)
    assert WAND_MAC not in S.radio().peers and WAND2_MAC not in S.radio().peers


def test_idle_stop_silences(r):
    w0 = len(ble.writes)
    s0 = r.comp.counters["stops"]
    inject(WAND2_MAC, {"type": "stop"})
    assert r.run(500, lambda: r.comp.counters["stops"] == s0 + 1)
    r.run(50)
    assert [n for n, _ in ble.cmds(w0)] == ["allTasksOff", "allLEDsOff"], ble.cmds(w0)


def test_ble_drop_espnow_keeps_flowing(r):
    rx0 = r.comp.counters["rx"]
    ble.available = False
    ble.drop()
    assert r.run(500, lambda: not r.comp.link.ready)
    for i in range(20):
        inject(WAND_MAC, ["turnred", "turnblue"])
    inject(WAND_MAC, {"type": "stop"})
    assert r.run(1000, lambda: r.comp.counters["rx"] == rx0 + 21), r.comp.counters
    assert not r.comp.link.ready
    assert r.comp.leds.last == C.LED_BLE_WAIT
    ble.available = True
    assert r.run(L.CONNECT_TIMEOUT_MS + L.RETRY_BACKOFF_MS + 2000,
                 lambda: r.comp.link.ready), r.comp.link.state_name()
    r.run(50)
    w0 = len(ble.writes)
    inject(WAND_MAC, {"type": "stop"})
    r.run(200)
    assert [n for n, _ in ble.cmds(w0)] == ["allTasksOff", "allLEDsOff"], ble.cmds(w0)


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
    r.run(100)


def test_keepalive_under_burst(r):
    rx0 = r.comp.counters["rx"]
    w0 = len(ble.writes)
    r.max_step_ms = 0
    for i in range(60):
        inject(WAND2_MAC, {"type": "burst", "n": i})
    r.run(A.KEEPALIVE_MS * 2 + 300)
    assert r.comp.counters["rx"] == rx0 + 60, (r.comp.counters["rx"], rx0)
    ka = [t for t, n, _ in ble.writes[w0:] if n == "keepAlive"]
    gaps = [b - a for a, b in zip(ka, ka[1:])]
    assert len(ka) >= 2 and max(gaps) <= A.KEEPALIVE_MS + 100, (ka, gaps)
    sw = [t for t, n, _ in ble.writes[w0:] if n == "readSwitches"]
    sgaps = [b - a for a, b in zip(sw, sw[1:])]
    assert max(sgaps) <= A.SWITCH_POLL_MS + 100, sgaps
    assert r.max_step_ms < 150, r.max_step_ms


def test_start_game_bubbles_to_pending(r):
    # No is_game_fn wired (the simulation's Companion is built with the
    # default None, matching a bench that never dispatches games): unknown
    # by construction, counted, and never queued.
    n0 = r.comp.counters["start_games_unknown"]
    inject(WAND_MAC, {"type": "start_game", "name": "splatwhack"})
    assert r.run(500, lambda: r.comp.counters["start_games_unknown"] == n0 + 1)
    assert r.comp.pending_start_game is None

    # Wire a fake game table for this one check, as main.py's is_game() does.
    r.comp.is_game_fn = lambda name: name == "splatwhack"
    try:
        inject(WAND_MAC, {"type": "start_game", "name": "splatwhack"})
        assert r.run(500, lambda: r.comp.pending_start_game == "splatwhack")
        assert r.comp.counters["start_games"] == 1

        n1 = r.comp.counters["start_games_unknown"]
        inject(WAND_MAC, {"type": "start_game", "name": "nosuchgame"})
        assert r.run(500, lambda: r.comp.counters["start_games_unknown"] == n1 + 1)
        assert r.comp.pending_start_game == "splatwhack", "must not clear itself"
        r.comp.pending_start_game = None    # as main.py's dispatch would
    finally:
        r.comp.is_game_fn = None


# ─── Driver (lib/ble_splat.py) fixes, IRQ handler driven directly ─────

import ble_splat as BS          # noqa: E402

ADV_SPLAT = b"\x06\x09Splat"
ADDR_A, ADDR_B = (bytes.fromhex("AB4200007EB6"),
                                    bytes.fromhex("AB4200007EB7"))


class StubRadio:
    """Records calls; delivers nothing on its own."""
    def __init__(self):
        self.calls = []
        self.is_active = True

    def active(self, v=None):
        if v is not None:
            self.is_active = bool(v)
            self.calls.append(("active", bool(v)))
        return self.is_active

    def gap_scan(self, *a):
        self.calls.append(("gap_scan",) + a)

    def gap_connect(self, addr_type, addr=None, *a):
        self.calls.append(("gap_connect", None if addr is None else bytes(addr)))

    def gap_disconnect(self, conn):
        self.calls.append(("gap_disconnect", conn))

    def gattc_discover_services(self, conn):
        self.calls.append(("discover", conn))

    def gattc_write(self, *a):
        self.calls.append(("write",) + a)


def driver(mac=None):
    o = BS.OpenSplat(mac_address=mac)
    o._ble = StubRadio()
    return o


def adv(o, addr):
    o._irq_handler(5, (0, memoryview(addr), 0, -50, ADV_SPLAT))


def test_driver_locks_onto_first_splat(r):
    o = driver()
    o._start_scan()
    adv(o, ADDR_A)
    assert o.mac_address == "AB:42:00:00:7E:B6" and not o._scanning
    o._start_scan()
    adv(o, ADDR_B)                   # another Splat advertises first
    assert o.mac_address == "AB:42:00:00:7E:B6", o.mac_address
    assert ("gap_connect", ADDR_B) not in o._ble.calls
    adv(o, ADDR_A)
    assert o._ble.calls[-1] == ("gap_connect", ADDR_A), o._ble.calls[-1]
    assert isinstance(o.addr, bytes), type(o.addr)


def test_driver_pinned_mac_never_replaced(r):
    o = driver("AB:42:00:00:7E:B7")
    o._start_scan()
    adv(o, ADDR_A)
    assert o.mac_address == "AB:42:00:00:7E:B7" and o._scanning
    adv(o, ADDR_B)
    assert o._ble.calls[-1] == ("gap_connect", ADDR_B), o._ble.calls[-1]


def test_driver_ignores_other_connections(r):
    o = driver("AB:42:00:00:7E:B6")
    o._irq_handler(7, (5, 0, memoryview(ADDR_A)))
    assert o.connected and o._conn_handle == 5
    o._irq_handler(9, (6, 10, 20, BS.UUID_SERVICE))      # conn 6's service
    assert o._start_handle is None, o._start_handle
    o._irq_handler(8, (6, 0, memoryview(ADDR_B)))        # conn 6 drops
    assert o.connected and o._conn_handle == 5
    o._irq_handler(8, (5, 0, memoryview(ADDR_A)))
    assert not o.connected and o._conn_handle is None


def test_driver_short_tap_release_not_lost(r):
    o = driver()
    o._handle_button(1)
    assert o.splat_pressed
    o._handle_button(0)              # inside the 80 ms window: rejected
    assert o.splat_pressed
    o._last_button_change_ms = time.ticks_ms() - BS._DEBOUNCE_MS - 1
    o._handle_button(0)              # e.g. the next readSwitches response
    assert not o.splat_pressed


def test_driver_late_scan_done_keeps_new_scan(r):
    o = driver()
    o._start_scan()
    o._stop_scan()
    o._start_scan()                  # new scan before the old DONE arrives
    o._irq_handler(6, ())            # the stopped scan's late DONE
    assert o._scanning, "late SCAN_DONE cleared the running scan"
    o._irq_handler(6, ())
    assert not o._scanning and o._scans_pending == 0


def test_driver_disconnect_keeps_radio(r):
    o = driver("AB:42:00:00:7E:B6")
    o._irq_handler(7, (5, 0, memoryview(ADDR_A)))
    o.disconnect()
    assert ("active", False) not in o._ble.calls, o._ble.calls


DRIVER_TESTS = [
    test_driver_locks_onto_first_splat, test_driver_pinned_mac_never_replaced,
    test_driver_ignores_other_connections, test_driver_short_tap_release_not_lost,
    test_driver_late_scan_done_keeps_new_scan, test_driver_disconnect_keeps_radio,
]


# ─── Several Splats on one companion (splat_hub.SplatHub) ───────

MULTI_ADDRS = [SPLAT_ADDR, bytes.fromhex("AB4200007EB7"), bytes.fromhex("AB4200007EB8")]


def retire(r):
    """Disconnect a runner's links and stop servicing them."""
    for link in r.comp.links:
        link.close()
    r.run(50)


def multi_runner(mgr, count, macs=None):
    hub = HUB.SplatHub(count, macs)
    return Runner(C.Companion(mgr, A.SplatGroup(hub), FakeLeds()))


def all_ready(r):
    return all(link.ready for link in r.comp.links)


def unit_for(r, periph_i):
    name = ble.periphs[periph_i].name
    for i, link in enumerate(r.comp.links):
        if link.mac_address == name:
            return i
    raise AssertionError("no link owns %s" % name)


def poll_until_event(splat, ms):
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        ev = splat.poll()
        if ev is not None:
            return ev
        time.sleep_ms(1)
    return None


def test_multi_all_ready(r):
    assert r.run(5000, lambda: all_ready(r)), [l.state_name() for l in r.comp.links]
    macs = sorted(l.mac_address for l in r.comp.links)
    assert macs == sorted(p.name for p in ble.periphs), macs
    assert r.comp.splat.count == 3 and r.comp.splat.connected_count == 3
    r.run(50)
    px = C.PIXEL_READY
    assert r.comp.leds.last == ("each", (px, px, px)), r.comp.leds.last


def test_multi_press_reports_index(r):
    splat = r.comp.splat
    r.run(100)
    ble.button(True, 2)
    assert poll_until_event(splat, 500) == "press"
    assert splat.last_index == unit_for(r, 2), (splat.last_index, unit_for(r, 2))
    ble.button(False, 2)
    assert poll_until_event(splat, 500) == "release"
    r.run(100)
    ble.button(True, 0)
    ble.button(True, 1)
    evs = [(poll_until_event(splat, 500), splat.last_index) for _ in range(2)]
    assert sorted(i for _, i in evs) == sorted([unit_for(r, 0), unit_for(r, 1)]), evs
    assert all(e == "press" for e, _ in evs), evs
    ble.button(False, 0)
    ble.button(False, 1)
    r.run(200)


def test_multi_color_all_and_unit(r):
    splat = r.comp.splat
    w0 = len(ble.writes_by)
    assert splat.color("turnred")
    hit = sorted(i for i, n in ble.writes_by[w0:] if n == "setLEDs")
    assert hit == [0, 1, 2], hit
    w1 = len(ble.writes_by)
    u = unit_for(r, 1)
    assert splat.unit(u).color("turnblue")
    hit = [i for i, n in ble.writes_by[w1:] if n == "setLEDs"]
    assert hit == [1], hit
    try:
        splat.unit(3)
        raise AssertionError("unit(3) must raise with 3 Splats")
    except IndexError:
        pass
    splat.off()


def test_multi_drop_one(r):
    u = unit_for(r, 1)
    ble.periphs[1].available = False
    ble.drop(1)
    assert r.run(500, lambda: not r.comp.links[u].ready)
    r.run(50)
    others = [l.ready for i, l in enumerate(r.comp.links) if i != u]
    assert all(others), others
    assert r.comp.leds.last[1][u] == C.PIXEL_WAIT, r.comp.leds.last
    assert r.comp.splat.connected and r.comp.splat.connected_count == 2
    ble.periphs[1].available = True
    assert r.run(L.CONNECT_TIMEOUT_MS + L.RETRY_BACKOFF_MS + 2000,
                 lambda: all_ready(r)), [l.state_name() for l in r.comp.links]
    assert r.comp.links[u].mac_address == ble.periphs[1].name


def test_hub_caps_connections(r):
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        extra = HUB.SplatHub(HUB.BLE_MAX_CONNECTIONS + 1)
    assert extra.count == HUB.BLE_MAX_CONNECTIONS, extra.count
    assert "[ERR]" in buf.getvalue(), buf.getvalue()
    ble.irq(r.comp.splat.hub._irq)       # hand the IRQ back to the live hub


def test_pinned_macs_order(r):
    want = [ble.periphs[2].name, ble.periphs[0].name]
    r2 = multi_runner(r.comp.mgr, 3, want)
    assert r2.comp.splat.count == 2, r2.comp.splat.count
    assert r2.run(5000, lambda: all_ready(r2)), [l.state_name() for l in r2.comp.links]
    got = [l.mac_address for l in r2.comp.links]
    assert got == want, got
    assert ble.periphs[1].conn is None, "an unpinned Splat was connected"
    retire(r2)


if __name__ == "__main__":
    for fn in DRIVER_TESTS:
        fn(None)
        print("ok  ", fn.__name__)
    mgr = S.EM.ESPNowManager()
    mgr.init()
    hub = HUB.SplatHub(1)
    link = hub.links[0]
    comp = C.Companion(mgr, A.SplatGroup(hub), FakeLeds())
    r = Runner(comp)
    tests = [
        test_copies_match, test_no_bridge_left,
        test_espnow_serviced_while_ble_connecting,
        test_idle_press_does_nothing, test_bridge_messages_ignored,
        test_idle_stop_silences,
        test_ble_drop_espnow_keeps_flowing, test_connect_timeout_retries,
        test_keepalive_under_burst, test_start_game_bubbles_to_pending,
    ]
    for fn in tests:
        fn(r)
        print("ok  ", fn.__name__)
    print("counters", comp.counters)
    print("link attempts=%d connects=%d drops=%d failed=%d max_step_ms=%.1f"
          % (link.attempts, link.connects, link.drops, link.failed_attempts,
             r.max_step_ms))

    retire(r)
    ble.periphs = [Periph(a) for a in MULTI_ADDRS]
    rm = multi_runner(mgr, 3)
    multi_tests = [
        test_multi_all_ready, test_multi_press_reports_index,
        test_multi_color_all_and_unit, test_multi_drop_one,
        test_hub_caps_connections,
    ]
    for fn in multi_tests:
        fn(rm)
        print("ok  ", fn.__name__)
    retire(rm)
    test_pinned_macs_order(rm)
    print("ok  ", test_pinned_macs_order.__name__)
    tests += multi_tests + [test_pinned_macs_order] + DRIVER_TESTS
    S._stop.set()
    S.t.join(1)
    print("%d passed" % len(tests))
