"""
Fakes for the MockWand CPython tests (party.py, solo.py, solo games).

    clock                 fake millisecond clock; install() patches time.*
    Bus / BusEnow         shared ESP-NOW medium with loss, lost ACKs and a
                          frame log (the transcript source)
    FakeSplatLink         stands in for splat_link.SplatLink under the real
                          splat_api.SplatAPI / SplatGroup
    make_local(...)       a real pairing.LocalSplats over FakeSplatLinks
    install_espnow_stub() espnow_manager.get_own_mac() returning own_mac[0]
    install_game_stubs()  machine / leds / nfc_reader modules for running a
                          game's play() off-device

Import this before party, solo or a game module.
"""
import json
import os
import random
import sys
import tempfile
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
WAND = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(WAND, "lib"))
sys.path.insert(0, WAND)

# One clock list per process, shared with test_pairing.py under pytest.
now = getattr(time, "_fake_now", None) or [0]
time._fake_now = now


def install():
    time.sleep_ms = lambda ms: now.__setitem__(0, now[0] + ms)
    time.ticks_ms = lambda: now[0]
    time.ticks_diff = lambda a, b: a - b
    time.ticks_add = lambda a, b: a + b


install()

BROADCAST = "*"


# ─── ESP-NOW ─────────────────────────────────

class Bus:
    """Every BusEnow on one medium. Delivery is immediate.

    bc_loss   probability a broadcast misses each receiver
    uni_loss  probability a unicast attempt is lost (no delivery, no ACK)
    ack_loss  probability a delivered unicast's ACK is lost (sender retries,
              receiver gets a duplicate)
    down      MACs that neither send nor receive
    """

    def __init__(self, seed=1, bc_loss=0.0, uni_loss=0.0, ack_loss=0.0):
        self.rng = random.Random(seed)
        self.bc_loss = bc_loss
        self.uni_loss = uni_loss
        self.ack_loss = ack_loss
        self.nodes = {}
        self.down = set()
        self.frames = []

    def node(self, mac):
        e = BusEnow(self, mac)
        self.nodes[mac] = e
        return e

    def _log(self, src, dst, data, delivered, acked):
        self.frames.append({"t": now[0], "src": src, "dst": dst, "msg": data,
                            "delivered": delivered, "acked": acked})

    def broadcast(self, src, data):
        if src in self.down:
            return
        got = []
        for mac, n in self.nodes.items():
            if mac == src or mac in self.down:
                continue
            if self.rng.random() < self.bc_loss:
                continue
            n.inbox.append((json.dumps(data), src))
            got.append(mac)
        self._log(src, BROADCAST, data, got, None)

    def unicast(self, src, dst, data):
        n = self.nodes.get(dst)
        if src in self.down or n is None or dst in self.down:
            self._log(src, dst, data, False, False)
            return False
        if self.rng.random() < self.uni_loss:
            self._log(src, dst, data, False, False)
            return False
        n.inbox.append((json.dumps(data), src))
        acked = self.rng.random() >= self.ack_loss
        self._log(src, dst, data, True, acked)
        return acked


class BusEnow:
    """espnow_manager.ESPNowManager surface used by party.py."""

    is_active = True

    def __init__(self, bus, mac):
        self.bus = bus
        self.mac = mac
        self.inbox = []
        self.peers = []

    def add_peer(self, mac):
        if mac not in self.peers:
            self.peers.append(mac)

    def remove_peer(self, mac):
        if mac in self.peers:
            self.peers.remove(mac)

    def broadcast(self, data):
        self.bus.broadcast(self.mac, json.loads(json.dumps(data)))
        return True

    def send_to(self, mac, data):
        assert mac in self.peers, "unicast to %s without add_peer" % mac
        return self.bus.unicast(self.mac, mac, json.loads(json.dumps(data)))

    def poll(self, timeout_ms=0):
        if not self.inbox:
            return None, None, None
        raw, src = self.inbox.pop(0)
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("type") in ("stop", "start_game"):
            return data["type"], data, src
        return "raw", data, src


def inject(enow, data, src):
    """Queue a message on one BusEnow as if src sent it (not logged)."""
    enow.inbox.append((json.dumps(data), src))


class ScriptEnow:
    """Single-wand enow for game tests: poll() returns scripted messages
    from at_ms onward, one per call; otherwise nothing."""

    is_active = True

    def __init__(self, script=()):
        self.script = list(script)       # [(at_ms, msg_type, data)]

    def poll(self, timeout_ms=0):
        if self.script and now[0] >= self.script[0][0]:
            _, mt, data = self.script.pop(0)
            return mt, data, "AA:AA:AA:AA:AA:AA"
        return None, None, None

    def broadcast(self, data):
        raise AssertionError("a solo game sent ESP-NOW: %r" % (data,))

    def send_to(self, mac, data):
        raise AssertionError("a solo game sent ESP-NOW: %r" % (data,))


# ─── Splats ──────────────────────────────────

class FakeSplatLink:
    """splat_link.SplatLink surface used by splat_api, pairing and pair_idle.
    writes: [(op, arg or args tuple)] for every BLE write."""

    def __init__(self, ready=True):
        self.ready = ready
        self.events = []
        self.writes = []
        self.scan_gate = None
        self.closed = 0
        self.fail = False

    def service(self, now_ms):
        pass

    def take_events(self):
        ev, self.events = self.events, []
        return ev

    def _w(self, op, *args):
        self.writes.append((op, args[0] if len(args) == 1 else args))
        return not self.fail

    def keepAlive(self):
        return True

    def readSwitches(self):
        return True

    def setLEDsON(self, rgb):
        return self._w("leds", tuple(rgb))

    def playSound(self, idx, vol):
        return self._w("sound", idx)

    def noteOn(self, v, vel, octave, inst):
        return self._w("noteOn", v, octave)

    def noteOff(self, v, vel, octave, inst):
        return self._w("noteOff", v, octave)

    def allTasksOff(self):
        return self._w("tasksOff")

    def allLEDsOff(self):
        return self._w("ledsOff")

    def close(self):
        self.closed += 1
        self.ready = False

    # test controls
    def press(self):
        self.events.append(1)

    def release(self):
        self.events.append(0)


class FakeHub:
    def __init__(self, n, ready=True):
        self.links = [FakeSplatLink(ready) for _ in range(n)]


def make_local(own_mac, n, ready=True):
    """Real pairing.LocalSplats + splat_api.SplatGroup over n FakeSplatLinks,
    polled once so the boot-time splat_back events are consumed (as the
    idle loop does)."""
    import pairing
    from splat_api import SplatGroup
    d = tempfile.mkdtemp(prefix="party-")
    path = os.path.join(d, "pairing.json")
    macs = ["5A:00:00:00:%02X:%02X" % (int(own_mac[-2:], 16), i) for i in range(n)]
    hub = FakeHub(n, ready)
    ls = pairing.LocalSplats(hub, SplatGroup(hub), macs, own_mac, path)
    while ls.poll() is not None:
        pass
    return ls


def offs(link):
    """Number of complete off() calls seen on a link."""
    return sum(1 for op, _ in link.writes if op == "ledsOff")


# ─── Game stubs ──────────────────────────────

class FakePin:
    IN = 0
    PULL_UP = 1
    level = [1]          # shared button level; 0 = pressed

    def __init__(self, *a, **k):
        pass

    def value(self):
        return FakePin.level[0]


class FakeNp(list):
    def __init__(self):
        list.__init__(self, [(0, 0, 0)] * 25)
        self.writes = 0
        self.seen = set()            # every color shown since creation

    def write(self):
        self.writes += 1
        self.seen.update(self)


class FakeLeds:
    def __init__(self):
        self.np = FakeNp()
        self.shapes = []
        self.fills = []

    def show_shape(self, s, c, bg=(0, 0, 0)):
        self.shapes.append((tuple(s), c))

    def fill(self, c):
        self.fills.append(c)

    def off(self):
        self.fills.append("off")


class FakeBuz:
    def __init__(self):
        self.beeps = []

    def beep(self, f=1000, ms=100):
        self.beeps.append(f)

    def celebrate(self):
        self.beeps.append("celebrate")

    def error(self):
        self.beeps.append("error")


class FakeAccel:
    def __init__(self):
        self.xyz = (0.0, 0.0, 1.0)

    def read(self):
        return self.xyz


nfc_script = []      # [(at_ms, text)]: read_tag_command returns text from at_ms


def _read_tag_command(nfc, timeout=500):
    if nfc_script and now[0] >= nfc_script[0][0]:
        return nfc_script.pop(0)[1], None
    return None, None


own_mac = ["AA:00:00:00:00:09"]


def install_espnow_stub():
    """espnow_manager with get_own_mac() only (solo.prepare uses it)."""
    e = types.ModuleType("espnow_manager")
    e.get_own_mac = lambda: own_mac[0]
    sys.modules["espnow_manager"] = e


def install_game_stubs():
    m = types.ModuleType("machine")
    m.Pin = FakePin
    sys.modules["machine"] = m
    n = types.ModuleType("nfc_reader")
    n.read_tag_command = _read_tag_command
    sys.modules["nfc_reader"] = n
    lm = types.ModuleType("leds")
    for k, v in (("RED", (130, 0, 0)), ("BLUE", (0, 20, 255)), ("YELLOW", (110, 120, 0)),
                 ("PURPLE", (50, 0, 250)), ("OFF", (0, 0, 0))):
        setattr(lm, k, v)
    lm.SHAPE_HOURGLASS = (0, 1, 2, 3, 4, 6, 8, 12, 16, 18, 20, 21, 22, 23, 24)
    lm.SHAPE_PLUS = (2, 7, 10, 11, 12, 13, 14, 17, 22)
    sys.modules["leds"] = lm
