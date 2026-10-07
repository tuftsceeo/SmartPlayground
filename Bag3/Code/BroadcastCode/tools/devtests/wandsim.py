"""Shared CPython harness for the MockWand pairing and party tests.

Virtual time, cooperative threads, a fake ESP-NOW bus and fake BLE Splats.
Nothing here runs on a device.

Time. Sim patches time.ticks_ms / ticks_diff / ticks_add / sleep_ms. Each
simulated wand runs in its own Python thread, but only one thread runs at a
time: a thread runs until it calls time.sleep_ms(), which parks it until
virtual time reaches its wake time. The scheduler (the thread that calls
Sim.run) always resumes the earliest sleeper, and runs timed callbacks
(radio deliveries, BLE events) at their due time. time.sleep_ms() called
from the scheduler's own thread runs the scheduler for that long. Device
code that polls in a `time.sleep_ms(1)` loop behaves as it does on a board.

Radio. FakeRadio stands in for espnow.ESPNow: unicast needs a registered
peer, a synchronous unicast send returns True only when the receiver ACKed,
broadcasts are never ACKed. Bus carries the frames and can drop frames,
drop ACKs (frame delivered, sender sees False) and duplicate frames.
Wand.enow is the real espnow_manager.ESPNowManager over a FakeRadio.

BLE. stubs/ubluetooth.py, one fake radio per Wand, with Periph Splats.
"""
import json
import os
import sys
import threading
import time

BB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STUBS = os.path.join(BB, "tools", "devtests", "stubs")
WAND_DIR = os.path.join(BB, "MockWand")
WAND_LIB = os.path.join(WAND_DIR, "lib")

BROADCAST = b"\xFF" * 6


def setup_paths():
    for p in (WAND_DIR, WAND_LIB, STUBS):
        if p in sys.path:
            sys.path.remove(p)
    # stubs first: they shadow memprobe, machine, network, espnow
    sys.path.insert(0, WAND_DIR)
    sys.path.insert(0, WAND_LIB)
    sys.path.insert(0, STUBS)


setup_paths()

SIM = None    # the installed Sim; stubs/ubluetooth.py looks it up here
CALLS = []    # ordered call names: tests append, stubs/ubluetooth.py appends BLE.*


def _ub():
    import ubluetooth
    return ubluetooth


class SimError(Exception):
    pass


class _SimThread:
    def __init__(self, sim, name, fn):
        self.sim = sim
        self.name = name
        self.fn = fn
        self.sem = threading.Semaphore(0)
        self.wake = 0
        self.done = False
        self.exc = None
        self.result = None
        self.wand = None
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        self.sem.acquire()
        self.sim._local.cur = self
        try:
            self.result = self.fn()
        except BaseException as e:      # noqa: BLE001 - re-raised by Sim.run
            self.exc = e
        self.done = True
        self.sim._parked.release()


class Sim:
    def __init__(self):
        self.now = 0
        self._seq = 0
        self._events = []                # [(due, seq, fn)]
        self._threads = []
        self._local = threading.local()
        self._parked = threading.Semaphore(0)
        self.default_wand = None
        self.in_event = False

    # ── time functions ──
    def install(self):
        time.ticks_ms = lambda: self.now
        time.ticks_diff = lambda a, b: a - b
        time.ticks_add = lambda a, b: a + b
        time.sleep_ms = self.sleep_ms
        global SIM
        SIM = self
        return self

    def current_ble(self):
        w = self.current_wand()
        if w is None:
            raise SimError("BLE() called with no current wand")
        return w.ble

    def current_wand(self):
        cur = getattr(self._local, "cur", None)
        if cur is not None and cur.wand is not None:
            return cur.wand
        return self.default_wand

    def at(self, due_ms, fn):
        self._seq += 1
        self._events.append((due_ms, self._seq, fn))

    def after(self, ms, fn):
        self.at(self.now + ms, fn)

    def sleep_ms(self, ms):
        cur = getattr(self._local, "cur", None)
        if self.in_event:
            raise SimError("time.sleep_ms() from a scheduler callback")
        if cur is None:                  # the scheduler's own thread
            self.run(self.now + max(0, ms))
            return
        cur.wake = self.now + max(0, ms)
        self._parked.release()
        cur.sem.acquire()

    # ── threads ──
    def spawn(self, name, fn, wand=None, start_ms=0):
        t = _SimThread(self, name, fn)
        t.wake = self.now + start_ms
        t.wand = wand
        self._threads.append(t)
        t.thread.start()
        return t

    def run(self, until_ms):
        """Advance virtual time to until_ms, running threads and events."""
        if getattr(self._local, "cur", None) is not None:
            raise SimError("Sim.run() from a simulated thread")
        while True:
            live = [t for t in self._threads if not t.done]
            cands = [t.wake for t in live] + [e[0] for e in self._events]
            if not cands or min(cands) > until_ms:
                self.now = max(self.now, until_ms)
                break
            nxt = min(cands)
            self.now = max(self.now, nxt)
            due = sorted(e for e in self._events if e[0] <= self.now)
            if due:
                ev = due[0]
                self._events.remove(ev)
                self.in_event = True
                try:
                    ev[2]()
                finally:
                    self.in_event = False
                continue
            t = min((t for t in live if t.wake <= self.now), key=lambda t: t.wake)
            t.sem.release()
            self._parked.acquire()
            if t.exc is not None:
                exc, t.exc = t.exc, None
                raise exc

    def run_until(self, cond, timeout_ms, step_ms=1):
        """Run until cond() is true; False if timeout_ms of virtual time passed."""
        end = self.now + timeout_ms
        while self.now < end:
            if cond():
                return True
            self.run(min(end, self.now + step_ms))
        return cond()

    def join(self, thread, timeout_ms):
        ok = self.run_until(lambda: thread.done, timeout_ms)
        if thread.exc is not None:
            exc, thread.exc = thread.exc, None
            raise exc
        return ok


# ── ESP-NOW ──────────────────────────────────────────────────────────

def mac_bytes(mac_str):
    return bytes(int(p, 16) for p in mac_str.split(":"))


def mac_str(mac_b):
    return ":".join("%02X" % b for b in mac_b)


class Bus:
    """The air. Latencies are virtual ms."""

    def __init__(self, sim):
        self.sim = sim
        self.radios = {}                 # mac bytes -> FakeRadio
        self.latency_ms = 2
        self.send_ms = 2                 # time a synchronous unicast blocks
        self.drop_frame = None           # fn(src, dst, obj) -> True to drop
        self.drop_ack = None             # fn(src, dst, obj) -> True to lose the ACK
        self.dup_frame = None            # fn(src, dst, obj) -> True to deliver twice
        self.log = []                    # (ms, src, dst or "*", obj, outcome)

    def _decode(self, msg):
        try:
            return json.loads(msg)
        except (ValueError, UnicodeError):
            return bytes(msg)

    def transmit(self, src, dst_mac, msg, sync):
        obj = self._decode(msg)
        src_s = mac_str(src.mac)
        if dst_mac == BROADCAST:
            for mb, r in list(self.radios.items()):
                if r is src:
                    continue
                dst_s = mac_str(mb)
                if self.drop_frame and self.drop_frame(src_s, dst_s, obj):
                    self.log.append((self.sim.now, src_s, dst_s, obj, "dropped"))
                    continue
                self._deliver(src, r, msg)
                self.log.append((self.sim.now, src_s, dst_s, obj, "bcast"))
            return True
        dst_s = mac_str(dst_mac)
        r = self.radios.get(dst_mac)
        delivered = False
        if r is not None and not (self.drop_frame and self.drop_frame(src_s, dst_s, obj)):
            self._deliver(src, r, msg)
            delivered = True
            if self.dup_frame and self.dup_frame(src_s, dst_s, obj):
                self._deliver(src, r, msg)
        acked = delivered and not (self.drop_ack and self.drop_ack(src_s, dst_s, obj))
        self.log.append((self.sim.now, src_s, dst_s, obj,
                         "acked" if acked else ("ack-lost" if delivered else "dropped")))
        if sync:
            time.sleep_ms(self.send_ms)
        return acked

    def _deliver(self, src, dst, msg):
        data = bytes(msg) if not isinstance(msg, bytes) else msg
        self.sim.after(self.latency_ms, lambda: dst._rx(src.mac, data))

    def sent(self, src=None, typ=None):
        """Logged frames, optionally filtered by sender MAC string and message type."""
        out = []
        for ms, s, d, obj, outcome in self.log:
            if src is not None and s != src:
                continue
            if typ is not None and not (isinstance(obj, dict) and obj.get("type") == typ):
                continue
            out.append((ms, s, d, obj, outcome))
        return out


class FakeRadio:
    """Stands in for espnow.ESPNow."""
    MAX_PEERS = 20

    def __init__(self, bus, mac_b):
        self.bus = bus
        self.mac = mac_b
        self.rx = []
        self.peers = set()
        self.is_active = False
        bus.radios[mac_b] = self

    def active(self, v=None):
        if v is not None:
            self.is_active = bool(v)
        return self.is_active

    def add_peer(self, mac, *a, **k):
        mac = bytes(mac)
        if mac in self.peers:
            raise OSError("ESP_ERR_ESPNOW_EXIST")
        if mac != BROADCAST and len([p for p in self.peers if p != BROADCAST]) >= self.MAX_PEERS:
            raise OSError("ESP_ERR_ESPNOW_FULL")
        self.peers.add(mac)

    def del_peer(self, mac):
        mac = bytes(mac)
        if mac not in self.peers:
            raise OSError("ESP_ERR_ESPNOW_NOT_FOUND")
        self.peers.discard(mac)

    def send(self, mac, msg, sync=True):
        mac = bytes(mac)
        if mac not in self.peers:
            raise OSError("ESP_ERR_ESPNOW_NOT_FOUND")
        if isinstance(msg, str):
            msg = msg.encode()
        return self.bus.transmit(self, mac, msg, sync and mac != BROADCAST)

    def _rx(self, src_mac, data):
        self.rx.append((src_mac, data))

    def irecv(self, timeout_ms=0):
        if not self.rx and timeout_ms:
            end = time.ticks_ms() + timeout_ms
            while not self.rx and time.ticks_ms() < end:
                time.sleep_ms(1)
        if self.rx:
            return self.rx.pop(0)
        return (None, None)

    @property
    def peers_table(self):
        return {}


# ── Fake wand peripherals ────────────────────────────────────────────

class FakeLeds:
    """Records what the wand matrix was told; no pixels."""
    num = 25

    def __init__(self):
        self.calls = []
        self.pixels = {}
        self.np = self

    def _rec(self, name, *a):
        self.calls.append((name,) + a)

    def off(self):
        self._rec("off")
        self.pixels = {}

    def fill(self, color):
        self._rec("fill", color)

    def solid(self, r, g, b):
        self._rec("solid", (r, g, b))

    def flash_color(self, color, times=2, on_ms=120, off_ms=80):
        self._rec("flash_color", color)

    def show_shape(self, indices, color, bg=(0, 0, 0)):
        self._rec("show_shape", tuple(indices), color)

    def idle_default(self, soc):
        self._rec("idle_default", soc)

    def idle_low_blink(self, frame):
        self._rec("idle_low_blink", frame)

    def idle_sleep(self):
        self._rec("idle_sleep")

    def show_pixel(self, i, color):
        self._rec("show_pixel", i, color)
        self.pixels[i] = color

    def __setitem__(self, i, color):
        self.pixels[i] = color

    def __getitem__(self, i):
        return self.pixels.get(i, (0, 0, 0))

    def write(self):
        self._rec("write")

    def names(self):
        return [c[0] for c in self.calls]


class FakeBuzzer:
    def __init__(self):
        self.calls = []

    def _rec(self, name, *a):
        self.calls.append((name,) + a)

    def beep(self, freq=1000, ms=100):
        self._rec("beep", freq, ms)
        time.sleep_ms(ms)

    def play_note(self, freq, ms=400):
        self._rec("play_note", freq, ms)
        time.sleep_ms(ms)

    def play(self, name):
        self._rec("play", name)
        time.sleep_ms(50)

    def start(self):
        self._rec("start")

    def stop(self):
        self._rec("stop")

    def names(self):
        return [c[0] if c[0] != "play" else "play:" + c[1] for c in self.calls]

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        if name in ("confirm", "success", "celebrate", "start", "info", "tick", "question",
                    "stop", "reject", "warn", "error"):
            return lambda: self.play(name)
        return lambda *a, **k: self._rec(name, *a)


class Wand:
    """One simulated wand: radio, ESPNowManager, BLE, Splats in range."""

    def __init__(self, sim, bus, mac_str_, name=None):
        import espnow_manager
        self.sim = sim
        self.mac = mac_str_
        self.name = name or mac_str_
        self.radio = FakeRadio(bus, mac_bytes(mac_str_))
        self.radio.active(True)
        self.radio.add_peer(BROADCAST)
        self.enow = espnow_manager.ESPNowManager()
        self.enow.enow = self.radio
        self.enow._active = True
        self.enow._own_mac_str = mac_str_
        self._ble = None
        self._in_range = []
        self.ble_fail_active = None     # exception BLE().active(True) raises
        self.leds = FakeLeds()
        self.buz = FakeBuzzer()

    @property
    def ble(self):
        """This wand's fake BLE radio, created (and ubluetooth imported) on
        first use."""
        if self._ble is None:
            ub = _ub()
            self._ble = ub.BLE.make()
            self._ble.fail_active = self.ble_fail_active
            for mac in self._in_range:
                self._ble.periphs.append(ub.Periph(mac_bytes(mac)))
        return self._ble

    def splat(self, mac_str_):
        """Put a fake Splat in range of this wand's BLE radio. Returns its
        Periph (creating the radio, and importing ubluetooth, if needed)."""
        if self._ble is None:
            self._in_range.append(mac_str_)
            return None
        p = _ub().Periph(mac_bytes(mac_str_))
        self._ble.periphs.append(p)
        return p

    def periph(self, mac_str_):
        return self.ble.periph(mac_str_)

    def ctx(self):
        return _WandCtx(self.sim, self)


class _WandCtx:
    def __init__(self, sim, wand):
        self.sim, self.wand = sim, wand

    def __enter__(self):
        self.prev = self.sim.default_wand
        self.sim.default_wand = self.wand

    def __exit__(self, *a):
        self.sim.default_wand = self.prev


def new_sim():
    """Fresh Sim with time patched and BLE stubs reset."""
    sim = Sim()
    sim.install()
    return sim, Bus(sim)


class Checker:
    """check()/summary for the plain-script tests."""

    def __init__(self):
        self.failures = []

    def __call__(self, label, ok, detail=""):
        print("%-4s %s%s" % ("ok" if ok else "FAIL", label, (" -- " + detail) if detail else ""))
        if not ok:
            self.failures.append(label)

    def finish(self, ok_message):
        print()
        if self.failures:
            print("FAILED: %d" % len(self.failures))
            for f in self.failures:
                print("  -", f)
            sys.exit(1)
        print(ok_message)
