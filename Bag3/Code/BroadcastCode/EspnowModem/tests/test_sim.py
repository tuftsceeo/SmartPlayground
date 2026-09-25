"""CPython end-to-end simulation of modem + host over a fake UART.

Runs the real modem/main.py in a thread and the real host espnow_manager.py
in the test thread. machine, network and espnow are replaced with fakes;
the "air" is a list of frames the fake radio sent.

Run: python tests/test_sim.py
"""

import os
import sys
import threading
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "modem", "lib"))
sys.path.insert(0, os.path.join(ROOT, "host", "lib"))

MODEM_MAC = bytes.fromhex("AABBCCDDEE10")
WAND_MAC = bytes.fromhex("112233445566")
BCAST = b"\xff" * 6


# ─── MicroPython time shims ──────────────────

class _Stop(Exception):
    pass


_stop = threading.Event()
_modem_thread = []


def _sleep_ms(ms):
    if _stop.is_set() and threading.current_thread() in _modem_thread:
        raise _Stop()
    time.sleep(ms / 1000)


time.sleep_ms = _sleep_ms
time.ticks_ms = lambda: int(time.monotonic() * 1000)
time.ticks_add = lambda a, b: a + b
time.ticks_diff = lambda a, b: a - b


# ─── Fake UART pair ──────────────────────────

class _Pipe:
    def __init__(self):
        self.buf = bytearray()
        self.lock = threading.Lock()


_a_to_b = _Pipe()
_b_to_a = _Pipe()
_uarts = []


class UART:
    def __init__(self, uid, baudrate, tx, rx, rxbuf):
        first = not _uarts
        self.out = _a_to_b if first else _b_to_a
        self.inp = _b_to_a if first else _a_to_b
        _uarts.append(self)

    def any(self):
        with self.inp.lock:
            return len(self.inp.buf)

    def readinto(self, buf):
        with self.inp.lock:
            n = min(len(buf), len(self.inp.buf))
            buf[:n] = self.inp.buf[:n]
            del self.inp.buf[:n]
            return n

    def write(self, data):
        with self.out.lock:
            self.out.buf += bytes(data)
        return len(data)


machine = types.ModuleType("machine")
machine.UART = UART
sys.modules["machine"] = machine


# ─── Fake network / espnow ───────────────────

class WLAN:
    def __init__(self, iface):
        pass

    def active(self, v=None):
        return True

    def disconnect(self):
        pass

    def config(self, key):
        assert key == "mac"
        return MODEM_MAC


network = types.ModuleType("network")
network.WLAN = WLAN
network.STA_IF = 0
sys.modules["network"] = network


class ESPNow:
    instance = None

    def __init__(self):
        ESPNow.instance = self
        self.inbox = []
        self.lock = threading.Lock()
        self.air = []
        self.peers = set()
        self.peers_table = {}
        self.cfg = {}

    def config(self, **kw):
        self.cfg.update(kw)

    def active(self, v):
        pass

    def add_peer(self, mac):
        if mac in self.peers:
            raise OSError(-12395)
        self.peers.add(mac)

    def del_peer(self, mac):
        self.peers.discard(mac)

    def send(self, mac, data, sync=True):
        if mac != BCAST and mac not in self.peers:
            raise OSError(-12389)
        if isinstance(data, str):
            data = data.encode()
        self.air.append((bytes(mac), bytes(data), sync))
        return True

    def irecv(self, timeout):
        with self.lock:
            if not self.inbox:
                return None, None
            return self.inbox.pop(0)

    def inject(self, mac, msg, rssi=-40):
        with self.lock:
            self.peers_table[mac] = [rssi, 0]
            self.inbox.append((mac, bytearray(msg)))


espnow = types.ModuleType("espnow")
espnow.ESPNow = ESPNow
sys.modules["espnow"] = espnow


# ─── Start modem ─────────────────────────────

_modem_globals = {"__name__": "__main__"}


def _run_modem():
    path = os.path.join(ROOT, "modem", "main.py")
    with open(path) as f:
        code = compile(f.read(), path, "exec")
    try:
        exec(code, _modem_globals)
    except _Stop:
        pass


t = threading.Thread(target=_run_modem, daemon=True)
_modem_thread.append(t)
t.start()
while "_modem" not in _modem_globals:
    time.sleep(0.01)
modem = _modem_globals["_modem"]
radio = ESPNow.instance

import espnow_manager as EM  # noqa: E402  (after fakes are installed)


def drain_all(mgr, timeout_ms=200):
    out = []
    while True:
        r = mgr.poll(timeout_ms)
        if r[0] is None:
            return out
        out.append(r)


# ─── Tests ───────────────────────────────────

def test_init_and_mac(mgr):
    assert radio.cfg["rxbuf"] == 8192
    assert EM.get_own_mac() == "AA:BB:CC:DD:EE:10"
    assert mgr.is_active


def test_classified_receive(mgr):
    radio.inject(WAND_MAC, b'["turnred","turnblue"]')
    radio.inject(WAND_MAC, b'{"type":"stop"}')
    radio.inject(WAND_MAC, b'\x01\x02')
    radio.inject(WAND_MAC, b'{"type":"find_device","mac":"00:00:00:00:00:01"}')
    radio.inject(WAND_MAC, b'{"type":"find_device","mac":"aa:bb:cc:dd:ee:10"}')
    got = drain_all(mgr)
    ms = "11:22:33:44:55:66"
    assert got == [
        ("colors", ["turnred", "turnblue"], ms),
        ("stop", {"type": "stop"}, ms),
        ("raw", b"\x01\x02", ms),
        ("start_game", {"name": "finddevice", "mac": "aa:bb:cc:dd:ee:10"}, ms),
    ], got
    assert mgr.get_rssi(ms) == -40


def test_send_paths(mgr):
    radio.air.clear()
    assert mgr.broadcast(["turnred"])
    assert not mgr.send_to("11:22:33:44:55:66", {"type": "x"})   # not a peer
    mgr.add_peer("11:22:33:44:55:66")
    assert mgr.send_to("11:22:33:44:55:66", {"type": "x"})
    assert mgr.send_raw(EM.BROADCAST_MAC, b"\x09")
    assert radio.air == [
        (BCAST, b'["turnred"]', False),
        (WAND_MAC, b'{"type": "x"}', True),
        (BCAST, b"\x09", False),
    ], radio.air


def test_status_poll_passthrough(mgr):
    radio.inject(WAND_MAC, b'{"type":"status_poll"}')
    got = drain_all(mgr)
    assert got and got[0][0] == "status_poll", got


def test_status_auto_reply(mgr):
    mgr.set_status_provider(lambda: 77)
    radio.air.clear()
    radio.inject(WAND_MAC, b'{"type":"status_poll"}')
    assert drain_all(mgr) == []
    slot = MODEM_MAC[5] % EM_SLOTS
    time.sleep((400 + slot * 180 + 120 + 300) / 1000)
    reports = [d for m, d, s in radio.air if b"status_report" in d]
    assert len(reports) == 2, radio.air
    assert b'"battery": 77' in reports[0] and b'"rssi": -40' in reports[0]
    mgr.set_status_provider(None)


def test_burst_no_loss(mgr):
    mgr.drain()
    for i in range(100):
        radio.inject(WAND_MAC, b'{"type":"burst","n":%d}' % i)
    time.sleep(0.3)            # host busy; modem holds the burst
    got = drain_all(mgr)
    assert [d["n"] for _, d, _ in got] == list(range(100))


def test_burst_overflow_reported(mgr):
    base = mgr.link_stats()["modem_rx_overflow"]
    for i in range(200):
        radio.inject(WAND_MAC, b'{"type":"burst","n":%d}' % i)
    time.sleep(0.3)
    got = drain_all(mgr)
    ring = _modem_globals["RING_SLOTS"]
    assert [d["n"] for _, d, _ in got] == list(range(200 - ring, 200))
    assert mgr.link_stats()["modem_rx_overflow"] - base == 200 - ring


def test_drain_flushes(mgr):
    for i in range(10):
        radio.inject(WAND_MAC, b'["turnred"]')
    time.sleep(0.05)
    mgr.drain()
    assert mgr.poll() == (None, None, None)


def test_corrupt_link_recovers(mgr):
    with _a_to_b.lock:
        _a_to_b.buf += b"\xA5\x5A\x87\x01\x05\x00garbage"   # bad frame to host
    radio.inject(WAND_MAC, b'["turnblue"]')
    got = drain_all(mgr)
    assert got and got[0][1] == ["turnblue"], got


def test_modem_reset_restores_state(mgr):
    radio.peers.clear()
    modem.peers.clear()
    modem.boot_id = (modem.boot_id + 1) & 0xFF
    modem.accepting = False
    mgr.poll()                  # sees new boot_id, restores
    assert WAND_MAC in radio.peers
    assert modem.accepting
    assert mgr.send_to("11:22:33:44:55:66", ["ok"])


def test_shutdown(mgr):
    radio.air.clear()
    mgr.shutdown()
    assert not mgr.is_active
    assert (WAND_MAC, b'{"type": "stop"}', True) in radio.air
    assert not modem.peers and not modem.accepting
    assert mgr.poll() == (None, None, None)


EM_SLOTS = 16

if __name__ == "__main__":
    mgr = EM.ESPNowManager()
    mgr.init()
    tests = [
        test_init_and_mac, test_classified_receive, test_send_paths,
        test_status_poll_passthrough, test_status_auto_reply,
        test_burst_no_loss, test_burst_overflow_reported, test_drain_flushes,
        test_corrupt_link_recovers, test_modem_reset_restores_state,
        test_shutdown,
    ]
    for fn in tests:
        fn(mgr)
        print("ok  ", fn.__name__)
    print(mgr.link_stats())
    _stop.set()
    t.join(1)
    print("%d passed" % len(tests))
