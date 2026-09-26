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
BIG_SRC = os.path.join(ROOT, "..", "MockWand", "main.py")


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
        targets = [WAND, HOST] if dst == "FF:FF:FF:FF:FF:FF" else [dst]
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

    def take(self, me):
        with self.lock:
            q = self.inbox[me]
            return q.pop(0) if q else None


class FakeMgr:
    def __init__(self, air, me):
        self.air = air
        self.me = me
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

    def broadcast(self, data):
        msg = json.dumps(data) if not isinstance(data, (str, bytes)) else data
        self.air.deliver(self.me, "FF:FF:FF:FF:FF:FF",
                         msg.encode() if isinstance(msg, str) else msg)
        return True

    def send_to(self, mac_str, data):
        if mac_str not in self.peers:
            raise AssertionError("send_to %s without add_peer" % mac_str)
        msg = json.dumps(data) if not isinstance(data, (str, bytes)) else data
        self.air.deliver(self.me, mac_str,
                         msg.encode() if isinstance(msg, str) else msg)
        return True

    def send_raw(self, mac_bytes, raw):
        mac_str = ":".join("%02X" % b for b in mac_bytes)
        self.air.deliver(self.me, mac_str, raw)
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
    game_store.GAMES_DIR = wand_games
    air = Air()
    wand = FakeMgr(air, WAND)
    host = FakeMgr(air, HOST)
    sender = code_sender.CodeSender(host, games_dir=host_games, verbose=False)
    ht = HostThread(host, sender)
    return tmp, air, wand, sender, ht, host_games, wand_games


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
    tmp, air, wand, sender, ht, hg, wg = ctx
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
    tmp, air, wand, sender, ht, hg, wg = ctx
    air.loss, air.dup, air.reorder = 0.25, 0.05, 0.10
    os.remove(os.path.join(wg, "bigtest.py"))
    assert espnow_code.receive(wand, "bigtest", "wand", verbose=False) is True
    assert same(os.path.join(hg, "bigtest.py"), os.path.join(wg, "bigtest.py"))
    st = espnow_code.LAST_STATS
    assert st["gets"] > (st["chunks"] + 7) // 8     # re-requests happened
    air.loss = air.dup = air.reorder = 0


def test_old_game_kept_as_bak(ctx):
    tmp, air, wand, sender, ht, hg, wg = ctx
    assert espnow_code.receive(wand, "bigtest", "wand", verbose=False) is True
    assert os.path.exists(os.path.join(wg, "bigtest.py.bak"))


def test_refusals(ctx):
    tmp, air, wand, sender, ht, hg, wg = ctx
    assert espnow_code.receive(wand, "nosuch", "wand", verbose=False) == "norequest"
    assert espnow_code.receive(wand, "tiny", "icon_display", verbose=False) == "norequest"


def test_no_host(ctx):
    tmp, air, wand, sender, ht, hg, wg = ctx
    ht.run.clear()
    assert espnow_code.receive(wand, "tiny", "wand", verbose=False) == "nohost"
    ht.run.set()
    while air.take(HOST) is not None:      # drop the unanswered requests
        pass


def test_broken_file_rejected_old_kept(ctx):
    tmp, air, wand, sender, ht, hg, wg = ctx
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
    tmp, air, wand, sender, ht, hg, wg = ctx
    air.corrupt_once = True
    assert espnow_code.receive(wand, "tiny", "wand", verbose=False) is False
    assert espnow_code.LAST_STATS["why"] == "sha256 mismatch"


def test_active_slug(ctx):
    tmp, air, wand, sender, ht, hg, wg = ctx
    code_sender.ACTIVE_PATH = os.path.join(tmp, "active.txt")
    with open(code_sender.ACTIVE_PATH, "w") as f:
        f.write("tiny\n")
    assert espnow_code.receive(wand, "", "wand", verbose=False) is True
    assert same(os.path.join(hg, "tiny.py"), os.path.join(wg, "tiny.py"))


if __name__ == "__main__":
    espnow_code.GET_WAIT_MS = 60
    espnow_code.OFFER_WAIT_MS = 150
    ctx = setup()
    tests = [test_clean_big_file, test_lossy_link, test_old_game_kept_as_bak,
             test_refusals, test_no_host, test_broken_file_rejected_old_kept,
             test_corruption_detected, test_active_slug]
    for fn in tests:
        fn(ctx)
        print("ok  ", fn.__name__)
    ctx[4].stop = True
    shutil.rmtree(ctx[0])
    print("%d passed" % len(tests))
