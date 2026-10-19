"""
CPython tests for MockWand pairing (PLAN A1-A5): card parsing, the store,
LocalSplats, PairIdle card / ESP-NOW / serial handling, and the PEER copies.

Run: python3 Bag3/Code/BroadcastCode/MockWand/tests/test_pairing.py
     (or pytest on this file)
"""
import json
import os
import shutil
import sys
import tempfile
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
WAND = os.path.dirname(HERE)
BC = os.path.dirname(WAND)
sys.path.insert(0, os.path.join(WAND, "lib"))

_now = [0]
time.sleep_ms = lambda ms: _now.__setitem__(0, _now[0] + ms)
time.ticks_ms = lambda: _now[0]
time.ticks_diff = lambda a, b: a - b
time.ticks_add = lambda a, b: a + b

import pairing
import pair_idle


# ─── Fakes ───────────────────────────────────

class FakeLink:
    def __init__(self):
        self.ready = False
        self.closed = 0
        self.scan_gate = None
        self.leds = []

    def close(self):
        self.closed += 1
        self.ready = False

    def setLEDsON(self, rgb):
        self.leds.append(rgb)
        return True


class FakeUnit:
    def __init__(self, link):
        self.link = link
        self.colors = []
        self.offs = 0

    @property
    def connected(self):
        return self.link.ready

    def color(self, name):
        self.colors.append(name)
        return True

    def off(self):
        self.offs += 1
        return True

    def _check(self, ok, what):
        return ok


class FakeHub:
    def __init__(self, n):
        self.links = [FakeLink() for _ in range(n)]


class FakeGroup:
    def __init__(self, hub):
        self.units = [FakeUnit(l) for l in hub.links]
        self.queue = []
        self.last_index = None

    def poll(self):
        if not self.queue:
            return None
        self.last_index, ev = self.queue.pop(0)
        return ev


class FakeEnow:
    def __init__(self, answers=()):
        self.is_active = True
        self.sent = []
        self.inbox = list(answers)
        self.peers = []

    def broadcast(self, d):
        self.sent.append(("bc", d))
        return True

    def send_to(self, mac, d):
        self.sent.append((mac, d))
        return True

    def add_peer(self, m):
        self.peers.append(m)

    def remove_peer(self, m):
        self.peers.remove(m)

    def poll(self, timeout_ms=0):
        _now[0] += max(timeout_ms, 1)
        if self.inbox:
            return self.inbox.pop(0)
        return None, None, None


class FakeNp(list):
    def write(self):
        pass


class FakeLeds:
    def __init__(self):
        self.np = FakeNp([(0, 0, 0)] * 25)
        self.shapes = []

    def show_shape(self, s, c):
        self.shapes.append((s, c))

    def fill(self, c):
        pass

    def off(self):
        pass


class FakeBuz:
    def __init__(self):
        self.beeps = []

    def beep(self, f, ms):
        self.beeps.append(f)


class Reset(Exception):
    pass


class FakeMachine:
    PWRON_RESET = 1
    SOFT_RESET = 5

    def __init__(self, cause=5):
        self.cause = cause
        self.resets = 0

    def reset_cause(self):
        return self.cause

    def reset(self):
        self.resets += 1
        raise Reset()


def _tmp():
    d = tempfile.mkdtemp(prefix="pair-")
    return d, os.path.join(d, "pairing.json")


def _use(path):
    pairing.PAIR_FILE = path


def _local(n, path, own="AA:BB:CC:DD:EE:02"):
    hub = FakeHub(n)
    macs = ["AB:42:00:00:7E:B%d" % i for i in range(n)]
    ls = pairing.LocalSplats(hub, FakeGroup(hub), macs, own, path)
    pairing._local = ls
    return ls


def _idle(enow=None, machine=None):
    pi = pair_idle.PairIdle(enow or FakeEnow(), FakeLeds(), FakeBuz(), machine or FakeMachine())
    pi._stdin = None
    return pi


# ─── A2: card parsing ────────────────────────

def test_parse_splat_card():
    p = pairing.parse_splat_card
    assert p("splat-AB4200007EB6") == "AB:42:00:00:7E:B6"
    assert p("splat-ab4200007eb6") == "AB:42:00:00:7E:B6"
    assert p("SPLAT-aB4200007eB6") == "AB:42:00:00:7E:B6"
    assert p("splat-AB4200007EB") is None          # 11 digits
    assert p("splat-AB4200007EB61") is None        # 13 digits
    assert p("splat-AB4200007EBG") is None         # non-hex
    assert p("splat-AB:42:00:00:7E:B6") is None    # colons
    assert p("AB4200007EB6") is None               # no prefix
    assert p("splat-AB4200007EB6:slug") is None
    assert p("splat-AB4200007EB6@7a3f") is None
    assert p(None) is None


def test_unpair_tag():
    import game_tags
    assert "unpair" in game_tags.CONTROL_TAGS
    assert "unpair" not in game_tags.EXIT_TAGS


# ─── A3: store ───────────────────────────────

def test_store():
    d, path = _tmp()
    try:
        assert pairing.load(path) == []
        assert pairing.add("ab:42:00:00:7e:b6", path)
        assert not pairing.add("AB:42:00:00:7E:B6", path)            # duplicate
        assert pairing.add("AB:42:00:00:7E:B7", path)
        assert not pairing.add("AB:42:00:00:7E:B8", path)            # full at MAX_SPLATS=2
        assert pairing.load(path) == ["AB:42:00:00:7E:B6", "AB:42:00:00:7E:B7"]
        assert not pairing.remove("AB:42:00:00:7E:B9", path)         # absent
        assert pairing.remove("AB:42:00:00:7E:B6", path)
        assert pairing.load(path) == ["AB:42:00:00:7E:B7"]
        assert pairing.remove("AB:42:00:00:7E:B7", path)
        assert not os.path.exists(path)
        with open(path, "w") as f:
            f.write("{not json")
        assert pairing.load(path) == []                               # corrupt
        with open(path, "w") as f:
            json.dump({"splats": "x"}, f)
        assert pairing.load(path) == []
    finally:
        shutil.rmtree(d)


def test_rename_failure_keeps_old_file():
    d, path = _tmp()
    try:
        pairing.add("AB:42:00:00:7E:B6", path)
        real = os.rename

        def boom(a, b):
            raise OSError("rename")
        os.rename = boom
        try:
            pairing.add("AB:42:00:00:7E:B7", path)
            raise AssertionError("rename failure did not raise")
        except OSError:
            pass
        finally:
            os.rename = real
        assert pairing.load(path) == ["AB:42:00:00:7E:B6"]
    finally:
        shutil.rmtree(d)


def test_identity():
    name, rgb = pairing.identity("AA:BB:CC:DD:EE:07")
    assert name == pairing.IDENTITY[7 % len(pairing.IDENTITY)][0]
    from splat_api import COLOR_RGB
    for n, _ in pairing.IDENTITY:
        assert n in COLOR_RGB


# ─── LocalSplats (party-library API) ─────────

def test_local_events_and_release():
    d, path = _tmp()
    try:
        _use(path)
        pairing.add("AB:42:00:00:7E:B0", path)
        pairing.add("AB:42:00:00:7E:B1", path)
        ls = _local(2, path)
        assert ls.count == 2 and ls.ready() == []
        ls.hub.links[1].ready = True
        assert ls.poll() == ("splat_back", 1)
        assert ls.ready() == [1]
        ls.group.queue.append((1, "press"))
        assert ls.poll() == ("press", 1)
        ls.hub.links[1].ready = False
        assert ls.poll() == ("splat_lost", 1)
        assert ls.poll() is None
        assert ls.release("ab:42:00:00:7e:b0")
        assert ls.hub.links[0].closed == 1 and ls.hub.links[0].scan_gate(None) is False
        assert ls.macs == ["AB:42:00:00:7E:B1"]
        ls.group.queue.append((1, "release"))
        assert ls.poll() == ("release", 0)                 # index shifted down
        ls.group.queue.append((0, "press"))
        assert ls.poll() is None                           # released unit ignored
        assert pairing.load(path) == ["AB:42:00:00:7E:B1"]
        assert ls.splat(0) is ls.group.units[1]
    finally:
        pairing._local = None
        shutil.rmtree(d)


def test_overdue_drop():
    d, path = _tmp()
    try:
        _use(path)
        pairing.add("AB:42:00:00:7E:B0", path)
        ls = _local(1, path)
        pi = _idle()
        _now[0] += pairing.PAIR_CONNECT_MS + 1
        pi.tick()
        assert ls.count == 0 and pairing.load(path) == []
        assert pi.leds.shapes, "no error feedback"
    finally:
        pairing._local = None
        shutil.rmtree(d)


def test_pair_flash_once_then_glow():
    d, path = _tmp()
    try:
        _use(path)
        ls = _local(1, path)
        pi = _idle()
        ls.hub.links[0].ready = True
        pi.tick()
        assert ls.group.units[0].colors == [ls.identity[0]]   # success flash
        pi.tick()
        assert len(ls.hub.links[0].leds) == 1                 # glow written once
        ls.hub.links[0].ready = False
        pi.tick()
        ls.hub.links[0].ready = True
        pi.tick()
        pi.tick()
        assert ls.group.units[0].colors == [ls.identity[0]]   # no second flash
        assert len(ls.hub.links[0].leds) == 2                 # glow after reconnect
        pi.after_game()
        pi.tick()
        assert len(ls.hub.links[0].leds) == 3
        pi.paint()
        assert pi.leds.np[pair_idle.CORNER_PIXEL] == ls.identity[1]
    finally:
        pairing._local = None
        shutil.rmtree(d)


# ─── A5: cards and ESP-NOW ───────────────────

def test_card_unclaimed_adds_and_resets():
    d, path = _tmp()
    try:
        _use(path)
        pairing._local = None
        m = FakeMachine()
        enow = FakeEnow()
        pi = _idle(enow, m)
        try:
            pi.card("splat-ab4200007eb6")
            raise AssertionError("no reset")
        except Reset:
            pass
        assert enow.sent[0] == ("bc", {"type": "pw_who", "m": "AB:42:00:00:7E:B6"})
        assert pairing.load(path) == ["AB:42:00:00:7E:B6"] and m.resets == 1
    finally:
        shutil.rmtree(d)


def test_card_claimed_refused():
    d, path = _tmp()
    try:
        _use(path)
        pairing._local = None
        m = FakeMachine()
        held = ("raw", {"type": "pw_held", "m": "AB:42:00:00:7E:B6"}, "11:22:33:44:55:66")
        other = ("stop", {"type": "stop"}, "11:22:33:44:55:77")
        pi = _idle(FakeEnow([other, held]), m)
        assert pi.card("splat-AB4200007EB6") is True
        assert m.resets == 0 and pairing.load(path) == []
        assert pi.leds.shapes
    finally:
        shutil.rmtree(d)


def test_card_full_refused():
    d, path = _tmp()
    try:
        _use(path)
        pairing.add("AB:42:00:00:7E:B0", path)
        pairing.add("AB:42:00:00:7E:B1", path)
        _local(2, path)
        m = FakeMachine()
        enow = FakeEnow()
        pi = _idle(enow, m)
        assert pi.card("splat-AB4200007EB6") is True
        assert m.resets == 0 and enow.sent == []
    finally:
        pairing._local = None
        shutil.rmtree(d)


def test_card_held_releases_without_reset():
    d, path = _tmp()
    try:
        _use(path)
        pairing.add("AB:42:00:00:7E:B0", path)
        ls = _local(1, path)
        m = FakeMachine()
        pi = _idle(machine=m)
        assert pi.card("splat-AB4200007EB0") is True
        assert m.resets == 0 and ls.count == 0 and pairing.load(path) == []
    finally:
        pairing._local = None
        shutil.rmtree(d)


def test_unpair_card_and_release_all():
    d, path = _tmp()
    try:
        _use(path)
        pairing.add("AB:42:00:00:7E:B0", path)
        pairing.add("AB:42:00:00:7E:B1", path)
        ls = _local(2, path)
        m = FakeMachine()
        pi = _idle(machine=m)
        assert pi.card("unpair") is True
        assert ls.count == 0 and not os.path.exists(path) and m.resets == 0
        assert all(u.offs == 1 for u in ls.group.units)
        pairing.add("AB:42:00:00:7E:B0", path)
        assert pi.espnow({"type": "pw_release_all"}, "11:22:33:44:55:66") is True
        assert not os.path.exists(path)
    finally:
        pairing._local = None
        shutil.rmtree(d)


def test_other_cards_not_consumed():
    pairing._local = None
    pi = _idle()
    for c in ("stop", "jumpin", "getcode:jumpin", "splat-xyz"):
        assert pi.card(c) is False


def test_pw_who_responder():
    d, path = _tmp()
    try:
        _use(path)
        _local(1, path)
        enow = FakeEnow()
        pi = _idle(enow)
        asker = "11:22:33:44:55:66"
        assert pi.espnow({"type": "pw_who", "m": "ab:42:00:00:7e:b0"}, asker)
        assert enow.sent == [(asker, {"type": "pw_held", "m": "AB:42:00:00:7E:B0"})]
        assert enow.peers == []
        enow.sent = []
        pi.espnow({"type": "pw_who", "m": "AB:42:00:00:7E:FF"}, asker)
        assert enow.sent == []
        assert pi.espnow({"type": "pw_find", "g": "x"}, asker) is False
        assert pi.espnow(b"raw", asker) is False
    finally:
        pairing._local = None
        shutil.rmtree(d)


# ─── A2.4: scan_splats serial command ────────

def test_scan_splats_command():
    out = []
    import builtins
    real = builtins.print
    builtins.print = lambda *a, **k: out.append(" ".join(str(x) for x in a))
    fake = types.ModuleType("splat_scan")
    fake.scan = lambda: [{"mac": "AB:42:00:00:7E:B6", "rssi": -50}]
    sys.modules["splat_scan"] = fake
    try:
        pairing._local = None
        pi = _idle()
        pi._command('{"cmd":"scan_splats"}')
        pi._command('{"cmd":"nope"}')
        pi._command('garbage')
        d, path = _tmp()
        _local(1, path)
        pi._command('{"cmd":"scan_splats"}')
        shutil.rmtree(d)
    finally:
        builtins.print = real
        pairing._local = None
        del sys.modules["splat_scan"]
    msgs = [json.loads(l) for l in out if l.startswith("{")]
    assert msgs[0] == {"type": "splats", "macs": [{"mac": "AB:42:00:00:7E:B6", "rssi": -50}]}
    assert msgs[1]["code"] == "unknown_cmd"
    assert msgs[2]["code"] == "bad_json"
    assert msgs[3]["code"] == "busy"


# ─── A1: PEER copies ─────────────────────────

def test_copies_match():
    comp = os.path.join(BC, "SplatCompanion", "Companion")
    pairs = (
        ("splat_hub.py", os.path.join(comp, "splat_hub.py")),
        ("splat_link.py", os.path.join(comp, "splat_link.py")),
        ("splat_api.py", os.path.join(comp, "splat_api.py")),
        ("ble_splat.py", os.path.join(comp, "lib", "ble_splat.py")),
        ("ble_splat.py", os.path.join(os.path.dirname(BC), "lib", "ble_splat.py")),
    )
    for name, other in pairs:
        with open(os.path.join(WAND, "lib", name), "rb") as f:
            a = f.read()
        with open(other, "rb") as f:
            b = f.read()
        assert a == b, "MockWand/lib/%s differs from %s" % (name, other)


if __name__ == "__main__":
    n = 0
    for k, fn in sorted(globals().items()):
        if k.startswith("test_") and callable(fn):
            fn()
            print("ok  ", k)
            n += 1
    print("ALL %d PAIRING TESTS PASSED" % n)
