"""Stub: MicroPython ubluetooth with fake Splat peripherals.

BLE is a singleton, as on the device. Every call lands in LOG as
(name, args). Fake Splats are Periph objects in BLE().periphs; events reach
the registered IRQ handler through pump(), which a test clock calls (see
wandsim.Clock). With no clock driving pump(), nothing connects.

Run inside a test that has patched time.ticks_ms (wandsim does).

When wandsim.SIM is set, events are scheduled on it and BLE() returns the
running wand's own radio (wandsim.Wand.ble), so several simulated wands each
get one. This module never imports wandsim: a test that must show a boot did
not import ubluetooth can run with wandsim loaded.
"""
import sys
import time

LOG = []


def _log(name, args=()):
    LOG.append((name, args))
    m = sys.modules.get("wandsim")
    if m is not None and hasattr(m, "CALLS"):
        m.CALLS.append(name)


def _sim():
    m = sys.modules.get("wandsim")
    return getattr(m, "SIM", None) if m is not None else None

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


class UUID:
    def __init__(self, v):
        self.v = v

    def __eq__(self, other):
        return isinstance(other, UUID) and other.v == self.v

    def __hash__(self):
        return hash(self.v)


class Periph:
    """One fake Splat."""
    def __init__(self, addr):
        self.addr = bytes(addr)
        self.mac = ":".join("%02X" % x for x in addr)
        self.available = True        # advertising and connectable
        self.conn = None
        self.subscribed = False
        self.writes = []             # (ms, name, data)

    def cmds(self, noise=False):
        return [(n, d) for _, n, d in self.writes if noise or n not in NOISE]

    def colors(self):
        """RGB triples of every setLEDs write, oldest first."""
        return [tuple(d[-3:]) if len(d) >= 3 else None
                for _, n, d in self.writes if n == "setLEDs"]


class BLE:
    _inst = None

    def __new__(cls):
        sim = _sim()
        if sim is not None:
            return sim.current_ble()
        if BLE._inst is None:
            BLE._inst = BLE.make()
        return BLE._inst

    @staticmethod
    def make():
        """A separate radio (one per simulated wand)."""
        obj = object.__new__(BLE)
        obj._setup()
        return obj

    def _setup(self):
        self.handler = None
        self.is_active = False
        self.activations = 0
        self.fail_active = None      # an exception to raise from active(True)
        self.scanning = False
        self.pending = None
        self.periphs = []
        self.delay_ms = 30
        self.next_conn = 1
        self._q = []                 # (due_ms, seq, event|callable, data)
        self._seq = 0
        self._adv_i = 0

    def _later(self, ms, event, data=None):
        due = time.ticks_ms() + ms
        sim = _sim()
        if sim is not None:
            sim.at(due, lambda: self._deliver(event, data))
            return
        self._seq += 1
        self._q.append((due, self._seq, event, data))

    def _deliver(self, event, data):
        if callable(event):
            event()
        elif self.handler is not None:
            self.handler(event, data)

    def pump(self):
        """Deliver every event that is due, oldest first."""
        while True:
            now = time.ticks_ms()
            due = [e for e in self._q if e[0] <= now]
            if not due:
                return
            due.sort()
            item = due[0]
            self._q.remove(item)
            self._deliver(item[2], item[3])

    def periph(self, mac):
        for p in self.periphs:
            if p.mac == mac:
                return p
        return None

    def _by_conn(self, conn):
        for p in self.periphs:
            if p.conn is not None and p.conn == conn:
                return p
        return None

    # ── ubluetooth API used by ble_splat / splat_link / splat_hub ──
    def active(self, v=None):
        if v is not None:
            _log("BLE.active" if v else "BLE.deactivate", (v,))
            if v and self.fail_active is not None:
                raise self.fail_active
            if v:
                self.activations += 1
            self.is_active = bool(v)
        return self.is_active

    def irq(self, handler):
        _log("BLE.irq")
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
        self._later(self.delay_ms, self._adv)

    def _adv(self):
        if not self.scanning:
            return
        cands = [p for p in self.periphs if p.available and p.conn is None]
        if cands and self.handler:
            p = cands[self._adv_i % len(cands)]
            self._adv_i += 1
            self.handler(5, (0, memoryview(p.addr), 0, -50, b"\x06\x09Splat"))
        if self.scanning:
            self._later(self.delay_ms, self._adv)

    def gap_connect(self, addr_type, addr=None, *a):
        if addr_type is None:
            self.pending = None
            return
        target = bytes(addr)
        self.pending = None
        for p in self.periphs:
            if p.addr == target:
                self.pending = p
        self._later(self.delay_ms, self._complete_connect)

    def _complete_connect(self):
        p = self.pending
        if p is None:
            return
        self.pending = None
        if not p.available or p.conn is not None:
            return                   # stays pending: the link times out
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
        p = self._by_conn(conn) if conn is not None else None
        if p is None:
            raise OSError(128)       # ENOTCONN
        data = bytes(data)
        if handle == H_RECV + 1:
            p.subscribed = data == b"\x01\x00"
            return
        assert handle == H_WRITE, handle
        name = CMD_NAMES.get((data[0], data[1]), "?%02X%02X" % (data[0], data[1]))
        p.writes.append((time.ticks_ms(), name, data))

    def gap_disconnect(self, conn):
        p = self._by_conn(conn)
        if p is not None:
            p.conn = None
            p.subscribed = False
            self._later(1, 8, (conn, 0, memoryview(p.addr)))

    # ── test controls ──
    def button(self, mac, pressed):
        p = self.periph(mac)
        assert p.conn is not None and p.subscribed, "Splat %s not connected" % mac
        self._later(1, 18, (p.conn, H_RECV, bytes([3, 0, 1 if pressed else 0])))

    def drop(self, mac):
        p = self.periph(mac)
        conn = p.conn
        p.conn = None
        p.subscribed = False
        if conn is not None:
            self._later(1, 8, (conn, 0, memoryview(p.addr)))


def reset_fake():
    """Forget the singleton and the call log (a fresh power-on)."""
    BLE._inst = None
    del LOG[:]
