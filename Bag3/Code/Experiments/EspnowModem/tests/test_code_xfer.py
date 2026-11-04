"""CPython test: ESP-NOW code transfer, wand receiver <-> host sender.

Runs MockWandEUM/lib/espnow_code.receive() against host/code_sender.py over
an in-memory "air" with configurable loss, duplication and reordering. Both
fake managers mimic the espnow_manager poll() contract: JSON payloads come
back decoded as ("raw", dict, mac), anything else as ("raw", bytes, mac).

Run: python tests/test_code_xfer.py
"""

import json
import os
import random
import shutil
import sys
import tempfile
import threading
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "MockWandEUM", "lib"))
sys.path.insert(0, os.path.join(ROOT, "host"))
sys.path.insert(0, os.path.join(ROOT, "host", "lib"))

time.sleep_ms = lambda ms: time.sleep(ms / 1000)
time.ticks_ms = lambda: int(time.monotonic() * 1000)
time.ticks_add = lambda a, b: a + b
time.ticks_diff = lambda a, b: a - b

machine = types.ModuleType("machine")
machine.UART = object
sys.modules["machine"] = machine

import gc  # noqa: E402
if not hasattr(gc, "mem_free"):
    gc.mem_free = lambda: 200000

import espnow_code  # noqa: E402
import game_store  # noqa: E402
import code_sender  # noqa: E402

WAND = "A0:F2:62:87:92:CC"
HOST = "AA:BB:CC:DD:EE:10"
BIG_SRC = os.path.join(ROOT, "..", "..", "Wand Module", "main.py")


class Air:
    """Delivers frames between two fake managers with injectable faults."""

    def __init__(self):
        self.lock = threading.Lock()
        self.inbox = {WAND: [], HOST: []}
        self.loss = 0.0          # applies to CX data frames only
        self.dup = 0.0
        self.reorder = 0.0
        self.corrupt_once = False
        self.rng = random.Random(1234)
        self.sent = 0

    def deliver(self, src, dst, payload):
        payload = bytes(payload)
        targets = list(self.inbox) if dst == "FF:FF:FF:FF:FF:FF" else [dst]
        is_data = payload[:2] == b"CX"
        with self.lock:
            self.sent += 1
            for t in targets:
                if t == src:
                    continue
                if is_data and self.rng.random() < self.loss:
                    continue
                if is_data and self.corrupt_once:
                    self.corrupt_once = False
                    b = bytearray(payload)
                    b[-1] ^= 0xFF
                    payload = bytes(b)
                q = self.inbox[t]
                if is_data and q and self.rng.random() < self.reorder:
                    q.insert(len(q) - 1, (src, payload))
                else:
                    q.append((src, payload))
                if is_data and self.rng.random() < self.dup:
                    q.append((src, payload))

    def register(self, mac):
        with self.lock:
            self.inbox.setdefault(mac, [])

    def take(self, me):
        with self.lock:
            q = self.inbox[me]
            return q.pop(0) if q else None


PEER_LIMIT = 20   # ESP-NOW unencrypted peer table size
MAX_PAYLOAD = 250  # ESP-NOW payload limit


def _sized(msg):
    b = msg.encode() if isinstance(msg, str) else msg
    assert len(b) <= MAX_PAYLOAD, "payload %d B > %d" % (len(b), MAX_PAYLOAD)
    return b


class FakeMgr:
    def __init__(self, air, me):
        self.air = air
        self.me = me
        air.register(me)
        self.max_peers = 0
        self.peers = set()
        self._peers = {}
        self.enow = None
        self.is_active = True

    def poll(self, timeout_ms=0):
        item = self.air.take(self.me)
        if item is None:
            return None, None, None
        src, payload = item
        try:
            return "raw", json.loads(payload), src
        except (ValueError, UnicodeError):
            return "raw", payload, src

    def add_peer(self, mac_str):
        self.peers.add(mac_str)
        if len(self.peers) > PEER_LIMIT:
            raise OSError("ESP_ERR_ESPNOW_FULL (%d peers)" % len(self.peers))
        self.max_peers = max(self.max_peers, len(self.peers))

    def remove_peer(self, mac_str):
        self.peers.discard(mac_str)

    def broadcast(self, data):
        msg = json.dumps(data) if not isinstance(data, (str, bytes)) else data
        self.air.deliver(self.me, "FF:FF:FF:FF:FF:FF", _sized(msg))
        return True

    def send_to(self, mac_str, data):
        if mac_str not in self.peers:
            raise AssertionError("send_to %s without add_peer" % mac_str)
        msg = json.dumps(data) if not isinstance(data, (str, bytes)) else data
        self.air.deliver(self.me, mac_str, _sized(msg))
        return True

    def send_raw(self, mac_bytes, raw):
        mac_str = ":".join("%02X" % b for b in mac_bytes)
        self.air.deliver(self.me, mac_str, _sized(raw))
        return True


class HostThread:
    def __init__(self, mgr, sender):
        self.mgr = mgr
        self.sender = sender
        self.run = threading.Event()
        self.run.set()
        self.stop = False
        self.t = threading.Thread(target=self._loop, daemon=True)
        self.t.start()

    def _loop(self):
        while not self.stop:
            if self.run.is_set():
                mt, data, mac = self.mgr.poll()
                if mt is not None:
                    self.sender.handle(mt, data, mac)
                    continue
            time.sleep(0.0005)


def setup():
    tmp = tempfile.mkdtemp()
    host_games = os.path.join(tmp, "host_games")
    wand_games = os.path.join(tmp, "wand_games")
    os.mkdir(host_games)
    shutil.copy(BIG_SRC, os.path.join(host_games, "bigtest.py"))
    with open(os.path.join(host_games, "tiny.py"), "w") as f:
        f.write("def play(*a):\n    return 1\n")
    with open(os.path.join(host_games, "broken.py"), "w") as f:
        f.write("def play(:\n")
    # Display game: goalrace_icon.py plus more icons than one offer holds.
    with open(os.path.join(host_games, "goalrace_icon.py"), "w") as f:
        f.write("def play(*a):\n    return 2\n")
    with open(os.path.join(host_games, "goalrace.py"), "w") as f:
        f.write("def play(*a):\n    return 1\n")
    icons = os.path.join(host_games, "goalrace_icons")
    os.mkdir(icons)
    for name in ICON_NAMES:
        with open(os.path.join(icons, name + ".py"), "w") as f:
            f.write("NAME = %r\nDATA = %r\n" % (name, bytes(range(256)) * 3))
    with open(os.path.join(icons, "notes.txt"), "w") as f:
        f.write("not an icon\n")
    game_store.GAMES_DIR = wand_games
    air = Air()
    wand = FakeMgr(air, WAND)
    host = FakeMgr(air, HOST)
    sender = code_sender.CodeSender(host, games_dir=host_games, verbose=False)
    ht = HostThread(host, sender)
    return tmp, air, wand, sender, ht, host_games, wand_games, host


ICON_NAMES = ["icon_%02d_%s" % (i, "x" * (i % 7)) for i in range(23)]


def host_result(sender, timeout=2.0):
    """Wait for the sender to process code_done; returns its result dict."""
    deadline = time.monotonic() + timeout
    while sender.last_result is None and time.monotonic() < deadline:
        time.sleep(0.005)
    assert sender.last_result is not None, "sender never saw code_done"
    r = sender.last_result
    sender.last_result = None
    return r


def same(a, b):
    with open(a, "rb") as fa, open(b, "rb") as fb:
        return fa.read() == fb.read()


def test_clean_big_file(ctx):
    tmp, air, wand, sender, ht, hg, wg, host = ctx
    air.loss = air.dup = air.reorder = 0
    sender.last_result = None
    assert espnow_code.receive(wand, "bigtest", "wand", verbose=False) is True
    assert same(os.path.join(hg, "bigtest.py"), os.path.join(wg, "bigtest.py"))
    st = espnow_code.LAST_STATS
    assert st["chunks"] == (st["bytes"] + 244) // 245 and st["dup"] == 0
    assert st["pre_compile_gc_free"] > 0 and "pre_compile_idf_largest" in st
    r = host_result(sender)
    assert r["ok"] and r["frames"] == st["chunks"] and r["send_fail"] == 0


def test_lossy_link(ctx):
    tmp, air, wand, sender, ht, hg, wg, host = ctx
    air.loss, air.dup, air.reorder = 0.25, 0.05, 0.10
    os.remove(os.path.join(wg, "bigtest.py"))
    assert espnow_code.receive(wand, "bigtest", "wand", verbose=False) is True
    assert same(os.path.join(hg, "bigtest.py"), os.path.join(wg, "bigtest.py"))
    st = espnow_code.LAST_STATS
    assert st["gets"] > (st["chunks"] + 7) // 8     # re-requests happened
    air.loss = air.dup = air.reorder = 0


def test_old_game_kept_as_bak(ctx):
    tmp, air, wand, sender, ht, hg, wg, host = ctx
    assert espnow_code.receive(wand, "bigtest", "wand", verbose=False) is True
    assert os.path.exists(os.path.join(wg, "bigtest.py.bak"))


def test_refusals(ctx):
    tmp, air, wand, sender, ht, hg, wg, host = ctx
    assert espnow_code.receive(wand, "nosuch", "wand", verbose=False) == "norequest"
    assert espnow_code.receive(wand, "tiny", "icon_display", verbose=False) == "norequest"


def test_no_host(ctx):
    tmp, air, wand, sender, ht, hg, wg, host = ctx
    ht.run.clear()
    assert espnow_code.receive(wand, "tiny", "wand", verbose=False) == "nohost"
    ht.run.set()
    while air.take(HOST) is not None:      # drop the unanswered requests
        pass


def test_broken_file_rejected_old_kept(ctx):
    tmp, air, wand, sender, ht, hg, wg, host = ctx
    with open(os.path.join(wg, "broken.py"), "w") as f:
        f.write("# previous good copy\n")
    sender.last_result = None
    assert espnow_code.receive(wand, "broken", "wand", verbose=False) is False
    assert espnow_code.LAST_STATS["why"].startswith("does not compile")
    with open(os.path.join(wg, "broken.py")) as f:
        assert f.read() == "# previous good copy\n"
    assert not os.path.exists(os.path.join(wg, "broken.py.part"))
    assert host_result(sender)["ok"] is False


def test_corruption_detected(ctx):
    tmp, air, wand, sender, ht, hg, wg, host = ctx
    air.corrupt_once = True
    assert espnow_code.receive(wand, "tiny", "wand", verbose=False) is False
    assert espnow_code.LAST_STATS["why"] == "sha256 mismatch"


def test_active_slug(ctx):
    tmp, air, wand, sender, ht, hg, wg, host = ctx
    code_sender.ACTIVE_PATH = os.path.join(tmp, "active.txt")
    with open(code_sender.ACTIVE_PATH, "w") as f:
        f.write("tiny\n")
    assert espnow_code.receive(wand, "", "wand", verbose=False) is True
    assert same(os.path.join(hg, "tiny.py"), os.path.join(wg, "tiny.py"))


def _wand_mac(i):
    return "02:00:00:00:%02X:%02X" % (i >> 8, i & 0xFF)


def test_many_wands_concurrent_with_busy(ctx):
    """More wands than MAX_SESSIONS at once: all finish, some wait busy."""
    tmp, air, wand, sender, ht, hg, wg, host = ctx
    n = 8
    code_sender.MAX_SESSIONS = 3
    for i in range(n):
        shutil.copy(os.path.join(hg, "bigtest.py"), os.path.join(hg, "w%d.py" % i))
    wands = [FakeMgr(air, _wand_mac(i)) for i in range(n)]
    results = [None] * n

    def run(i):
        results[i] = espnow_code.receive(wands[i], "w%d" % i, "wand",
                                         verbose=False)

    busy_before = sender.busy_replies
    host.max_peers = 0
    threads = [threading.Thread(target=run, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(120)
    assert results == [True] * n, results
    for i in range(n):
        assert same(os.path.join(hg, "w%d.py" % i), os.path.join(wg, "w%d.py" % i))
    assert sender.busy_replies > busy_before, "cap never reached"
    assert host.max_peers <= code_sender.MAX_SESSIONS + 1, host.max_peers
    deadline = time.monotonic() + 2
    while host.peers and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not host.peers, host.peers
    code_sender.MAX_SESSIONS = 6


def test_peer_table_never_fills(ctx):
    """25 different wands in a row stay under the 20-entry peer table."""
    tmp, air, wand, sender, ht, hg, wg, host = ctx
    host.max_peers = 0
    for i in range(25):
        w = FakeMgr(air, _wand_mac(0x100 + i))
        assert espnow_code.receive(w, "tiny", "wand", verbose=False) is True
    deadline = time.monotonic() + 2
    while host.peers and time.monotonic() < deadline:
        time.sleep(0.01)
    assert host.max_peers <= 2 and not host.peers, (host.max_peers, host.peers)


def test_busy_gives_up_after_budget(ctx):
    tmp, air, wand, sender, ht, hg, wg, host = ctx
    code_sender.MAX_SESSIONS = 0
    espnow_code.BUSY_WAIT_MAX_MS = 400
    r = espnow_code.receive(wand, "tiny", "wand", verbose=False)
    assert r == "busy", r
    assert espnow_code.LAST_STATS["busy_waits"] >= 1
    code_sender.MAX_SESSIONS = 6
    espnow_code.BUSY_WAIT_MAX_MS = 120000
    assert not host.peers, host.peers


def _icon_dir(tmp):
    d = os.path.join(tmp, "icons_rx")
    shutil.rmtree(d, ignore_errors=True)
    return d


def test_display_pull_with_icons(ctx):
    """icon_display gets <slug>_icon.py as <slug>.py, then every icon,
    paging the name list past the offer; counters stay on game files."""
    tmp, air, wand, sender, ht, hg, wg, host = ctx
    d = _icon_dir(tmp)
    served, failed = sender.served, sender.failed
    i_served = sender.icons_served
    sender.last_result = None
    assert espnow_code.receive(wand, "goalrace", "icon_display",
                               verbose=False, icon_dir=d) is True
    assert same(os.path.join(hg, "goalrace_icon.py"),
                os.path.join(wg, "goalrace.py"))
    got = sorted(os.listdir(d))
    assert got == sorted(n + ".py" for n in ICON_NAMES), got
    for n in got:
        assert same(os.path.join(hg, "goalrace_icons", n), os.path.join(d, n))
    assert espnow_code.LAST_STATS["icons"] == len(ICON_NAMES)
    deadline = time.monotonic() + 2
    while sender.icons_served - i_served < len(ICON_NAMES) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert sender.icons_served - i_served == len(ICON_NAMES)
    assert sender.served == served + 1 and sender.failed == failed
    r = host_result(sender)
    assert r["slug"] == "goalrace" and r["hub"] == "icon_display"
    assert r["path"].endswith("goalrace_icon.py")
    assert sender.last_result is None


def test_offer_icons_list_fits_frame(ctx):
    tmp, air, wand, sender, ht, hg, wg, host = ctx
    names = sender._icon_names("goalrace")
    assert names == sorted(n + ".py" for n in ICON_NAMES)
    offer = {"type": "code_offer", "id": 255, "name": "goalrace.py",
             "size": 99999, "sha": "f" * 64, "chunks": 409, "chunk": 245,
             "icons_n": len(names)}
    sender._fill_names(offer, names, 0)
    assert 0 < len(offer["icons"]) < len(names)
    assert offer["icons"] == names[:len(offer["icons"])]
    assert len(json.dumps(offer)) <= MAX_PAYLOAD
    # Wands get no icons fields.
    assert sender._icon_names("tiny") == []


def test_icon_failure_keeps_game(ctx):
    """A corrupted icon is skipped; the game and other icons still land."""
    tmp, air, wand, sender, ht, hg, wg, host = ctx
    d = _icon_dir(tmp)
    real = espnow_code._fetch
    calls = {"n": 0}

    def flaky(enow, snd, rid, offer, dest, *a):
        calls["n"] += 1
        if calls["n"] == 3:          # the second icon
            air.corrupt_once = True
        return real(enow, snd, rid, offer, dest, *a)

    espnow_code._fetch = flaky
    try:
        assert espnow_code.receive(wand, "goalrace", "icon_display",
                                   verbose=False, icon_dir=d) is True
    finally:
        espnow_code._fetch = real
    assert espnow_code.LAST_STATS["icons"] == len(ICON_NAMES) - 1
    assert len(os.listdir(d)) == len(ICON_NAMES) - 1
    assert not any(n.endswith(".part") for n in os.listdir(d))


def _ask(wand, req, timeout=1.0):
    wand.add_peer(HOST)
    wand.send_to(HOST, req)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        mt, data, mac = wand.poll()
        if isinstance(data, dict) and data.get("id") == req["id"]:
            return data
        time.sleep(0.002)
    raise AssertionError("no answer to %r" % (req,))


def test_icon_file_refusals(ctx):
    tmp, air, wand, sender, ht, hg, wg, host = ctx
    base = {"type": "code_req", "slug": "goalrace", "hub": "icon_display"}
    for i, extra in enumerate([
            {"file": "../goalrace.py"},
            {"file": "sub/a.py"},
            {"file": "notes.txt"},
            {"file": "nosuch.py"},
            {"file": ICON_NAMES[0] + ".py", "hub": "wand"},
            {"file": ICON_NAMES[0] + ".py", "slug": ""}]):
        req = dict(base, id=200 + i, **extra)
        r = _ask(wand, req)
        assert r["type"] == "code_offer" and r["size"] == 0, (extra, r)
    r = _ask(wand, dict(base, id=210, file=ICON_NAMES[0] + ".py"))
    assert r["size"] > 0 and r["name"] == ICON_NAMES[0] + ".py"
    wand.send_to(HOST, {"type": "code_done", "id": 210, "ok": False,
                        "why": "test"})
    # Wand role: no icons in the offer; list_from pages report nothing.
    r = _ask(wand, {"type": "code_req", "id": 211, "slug": "goalrace",
                    "hub": "wand"})
    assert "icons" not in r and "icons_n" not in r
    wand.send_to(HOST, {"type": "code_done", "id": 211, "ok": True})
    r = _ask(wand, {"type": "code_req", "id": 212, "slug": "goalrace",
                    "hub": "wand", "list_from": 0})
    assert r["type"] == "code_icons" and r["n"] == 0 and r["icons"] == []
    time.sleep(0.05)
    while wand.poll()[0] is not None:
        pass
    sender.last_result = None
    deadline = time.monotonic() + 1
    while host.peers and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not host.peers, host.peers


if __name__ == "__main__":
    espnow_code.GET_WAIT_MS = 60
    espnow_code.OFFER_WAIT_MS = 150
    espnow_code.REQ_JITTER_MS = 30
    code_sender.BUSY_RETRY_MS = 100
    ctx = setup()
    tests = [test_clean_big_file, test_lossy_link, test_old_game_kept_as_bak,
             test_refusals, test_no_host, test_broken_file_rejected_old_kept,
             test_corruption_detected, test_active_slug,
             test_many_wands_concurrent_with_busy, test_peer_table_never_fills,
             test_busy_gives_up_after_budget, test_display_pull_with_icons,
             test_offer_icons_list_fits_frame, test_icon_failure_keeps_game,
             test_icon_file_refusals]
    for fn in tests:
        fn(ctx)
        print("ok  ", fn.__name__)
    ctx[4].stop = True
    shutil.rmtree(ctx[0])
    print("%d passed" % len(tests))
