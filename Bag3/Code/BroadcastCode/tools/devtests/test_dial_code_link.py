"""CPython test: BDialFirmware/code_link.CodeLink serving the real wand receiver.

The Dial's code_link.py and its code_sender.py copy, over the fake `espnow`
air from EspnowModem/tests, against MockWandEUM/lib/espnow_code.receive().
Checks the interface bdial_server uses: arm/disarm, the radio off after
disarm, on_event ordering, last_result, stats_log, abort and idle expiry.

Run: python3 tools/devtests/test_dial_code_link.py
"""

import os
import shutil
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BC = os.path.join(HERE, "..", "..")
sys.path.insert(0, os.path.join(BC, "EspnowModem", "tests"))

import test_code_xfer as T  # noqa: E402  (time/machine stubs, Air)
import test_espnow_serve as S  # noqa: E402  (fake espnow/network)
import espnow_code  # noqa: E402
import game_store  # noqa: E402

T.machine.unique_id = lambda: b"\x10\x51\xdb\x56\x00\x4c"
sys.modules.pop("code_sender", None)
sys.path.insert(0, os.path.join(BC, "BroadcastDial", "BDialFirmware"))

import code_link  # noqa: E402

PULLS = []
stats_log = type(sys)("stats_log")
stats_log.record_pull = lambda slug, ok: PULLS.append((slug, ok))
sys.modules["stats_log"] = stats_log


class Loop:
    """bdial_server's SERVE loop: poll() every iteration, events recorded."""

    def __init__(self, link):
        self.link, self.events, self.abort = link, [], False
        self.stop = False
        self.t = threading.Thread(target=self._run, daemon=True)
        self.t.start()

    def _run(self):
        while not self.stop:
            if self.link.armed:
                r = self.link.poll(on_event=self.events.append,
                                   should_abort=lambda: self.abort)
                if r == 'abort':
                    self.events.append('abort')
            time.sleep(0.0005)


def setup():
    tmp = tempfile.mkdtemp()
    hg, wg = os.path.join(tmp, "h"), os.path.join(tmp, "w")
    os.mkdir(hg)
    shutil.copy(T.BIG_SRC, os.path.join(hg, "bigtest.py"))
    with open(os.path.join(hg, "tiny.py"), "w") as f:
        f.write("def play(*a):\n    return 1\n")
    with open(os.path.join(tmp, "active.txt"), "w") as f:
        f.write("tiny")
    code_link.GAMES_DIR = hg
    code_link.ACTIVE_PATH = os.path.join(tmp, "active.txt")
    game_store.GAMES_DIR = wg
    air = T.Air()
    holder = S.install_fakes(air)
    link = code_link.CodeLink()
    return tmp, air, link, holder, hg, wg


def wait(pred, timeout=3.0):
    deadline = time.monotonic() + timeout
    while not pred() and time.monotonic() < deadline:
        time.sleep(0.005)
    return pred()


def test_host_id_from_unique_id():
    assert code_link.HOST_ID == "004c", code_link.HOST_ID


def test_arm_refused_without_game(ctx):
    tmp, air, link = ctx[0], ctx[1], ctx[2]
    os.remove(code_link.ACTIVE_PATH)
    assert link.arm() is False and not link.armed
    with open(code_link.ACTIVE_PATH, "w") as f:
        f.write("tiny")


def test_resolve_reads_active(ctx):
    link = ctx[2]
    assert link.resolve() == "tiny" and link.active_slug == "tiny"
    assert link.resolve("nosuch") is None


def test_serve_transfer_events_and_stats(ctx):
    tmp, air, link, holder, hg, wg = ctx
    link.set_game("bigtest")
    assert link.arm() is True and holder["e"].on
    loop = Loop(link)
    wand = T.FakeMgr(air, T.WAND)
    del PULLS[:]
    assert espnow_code.receive(wand, "bigtest", "wand", verbose=False) is True
    assert T.same(os.path.join(hg, "bigtest.py"), os.path.join(wg, "bigtest.py"))
    assert wait(lambda: 'ok' in loop.events), loop.events
    assert loop.events == ['serving', 'ok'], loop.events
    r = link.last_result
    assert r["ok"] and r["mac"] == T.WAND and r["path"].endswith("bigtest.py")
    assert PULLS == [("bigtest", True)], PULLS
    loop.stop = True
    loop.t.join()


def test_refusal_is_not_a_pull(ctx):
    tmp, air, link, holder = ctx[:4]
    loop = Loop(link)
    wand = T.FakeMgr(air, T.WAND)
    del PULLS[:]
    assert espnow_code.receive(wand, "nosuch", "wand", verbose=False) == "norequest"
    time.sleep(0.1)
    assert loop.events == [] and PULLS == [], (loop.events, PULLS)
    loop.stop = True
    loop.t.join()


def test_idle_session_reports_fail(ctx):
    tmp, air, link = ctx[:3]
    sender_mod = sys.modules["code_sender"]
    saved = sender_mod.SESSION_IDLE_MS
    sender_mod.SESSION_IDLE_MS = 50
    loop = Loop(link)
    other = "A0:F2:62:87:92:DD"
    air.register(other)
    air.deliver(other, T.HOST, b'{"type": "code_req", "id": 7, "slug": "tiny", "hub": "wand"}')
    assert wait(lambda: 'fail' in loop.events), loop.events
    assert loop.events == ['serving', 'fail'], loop.events
    assert link.last_result["why"] == "idle" and link.serving_count == 0
    sender_mod.SESSION_IDLE_MS = saved
    loop.stop = True
    loop.t.join()


def test_abort_disarms_and_radio_off(ctx):
    tmp, air, link, holder = ctx[:4]
    loop = Loop(link)
    loop.abort = True
    assert wait(lambda: 'abort' in loop.events)
    assert not link.armed and not holder["e"].on and not link.mgr.is_active
    loop.stop = True
    loop.t.join()


def test_rearm_cycles(ctx):
    tmp, air, link, holder = ctx[:4]
    for _ in range(3):
        assert link.arm() is True and holder["e"].on
        link.disarm()
        assert not holder["e"].on and not link.armed


def test_prewarm_leaves_radio_off(ctx):
    holder = ctx[3]
    code_link.prewarm()
    assert not holder["e"].on


if __name__ == "__main__":
    espnow_code.GET_WAIT_MS = 60
    espnow_code.OFFER_WAIT_MS = 150
    espnow_code.REQ_JITTER_MS = 30
    test_host_id_from_unique_id()
    print("ok   test_host_id_from_unique_id")
    ctx = setup()
    tests = [test_arm_refused_without_game, test_resolve_reads_active,
             test_serve_transfer_events_and_stats, test_refusal_is_not_a_pull,
             test_idle_session_reports_fail, test_abort_disarms_and_radio_off,
             test_rearm_cycles, test_prewarm_leaves_radio_off]
    for fn in tests:
        fn(ctx)
        print("ok  ", fn.__name__)
    shutil.rmtree(ctx[0])
    print("%d passed" % (len(tests) + 1))
