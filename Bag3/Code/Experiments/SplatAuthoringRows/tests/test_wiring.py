"""Off-device tests for main._run_games wiring and the Splat host loop.

main.py boots hardware at import, so only the named functions are extracted
from its source with ast and run against fakes. The host loop is run with
a fake clock and radio. Run: python3 -m unittest discover -s tests
"""
import ast
import os
import sys
import time
import types
import unittest

HERE = os.path.dirname(__file__)
LIB = os.path.join(HERE, "..", "wand", "lib")
MAIN = os.path.join(HERE, "..", "wand", "main.py")
sys.path.insert(0, LIB)

from test_splat_units import FakeCtl, FakeGroup, splat_host  # noqa: E402  (installs stubs)


def _extract(names):
    """Compile the named top-level functions of main.py into a namespace."""
    tree = ast.parse(open(MAIN).read())
    body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in body} == set(names), "function missing from main.py"
    ns = {}
    exec(compile(ast.Module(body=body, type_ignores=[]), MAIN, "exec"), ns)
    return ns


class FakeBuz:
    def __init__(self):
        self.rejected = 0

    def reject(self):
        self.rejected += 1


class Handle:
    """Stands in for splatpair.GameSplats."""

    def __init__(self, count):
        self.count = count
        self.closed = False

    def close(self):
        self.closed = True


class RunGamesTest(unittest.TestCase):
    def _env(self, game_attrs, pair_ctl=None, role=""):
        mod = types.ModuleType("g")
        for k, v in game_attrs.items():
            setattr(mod, k, v)
        sys.modules["gmod_g"] = mod
        self.calls = []
        self.failed = []
        self.lobby_entered = []
        ns = _extract(["_splats_local", "_run_games"])
        ns.update(
            sys=sys, is_game=lambda n: n == "g", game_module=lambda n: "gmod_g",
            _load_play=lambda n: "play",
            _StartGameCapture=lambda enow: types.SimpleNamespace(pending_name=None),
            _splat_limits=lambda n: (1, None, True, 1) if game_attrs.get("SPLAT_HOST") else None,
            _enter_lobby=lambda *a: self.lobby_entered.append(a) or types.SimpleNamespace(
                close=lambda: self.calls.append("net.close")),
            _emit=lambda m: self.calls.append(m["type"]),
            _start_play=lambda play, name, *a: self.calls.append(("play", a[-1])),
            _is_arity_error=lambda e: False,
            _game_load_failed=lambda n, e: self.failed.append(str(e)),
            _unload_game=lambda n: None,
            memprobe=types.SimpleNamespace(probe=lambda s: None),
            UNLOAD_AFTER_GAME=False, _pair_ctl=pair_ctl, _ROLE=role)
        self.ns = ns
        self.buz = FakeBuz()

    def _run(self):
        self.ns["_run_games"]("g", None, None, self.buz, None, None, None, None)

    def test_local_game_skips_lobby_and_closes_handle(self):
        handle = Handle(2)
        self._env({"SPLATS_LOCAL": 2}, types.SimpleNamespace(game_handle=lambda: handle))
        self._run()
        self.assertEqual(self.lobby_entered, [])
        self.assertIn(("play", handle), self.calls)
        self.assertTrue(handle.closed)
        self.assertEqual(self.failed, [])

    def test_local_game_refused_when_too_few_splats(self):
        handle = Handle(1)
        self._env({"SPLATS_LOCAL": 2}, types.SimpleNamespace(game_handle=lambda: handle))
        self._run()
        self.assertEqual([c for c in self.calls if isinstance(c, tuple)], [])
        self.assertTrue(handle.closed)
        self.assertEqual(len(self.failed), 1)
        self.assertIn("needs 2", self.failed[0])

    def test_local_game_refused_without_any_splats(self):
        for pair_ctl in (None, types.SimpleNamespace(game_handle=lambda: None)):
            self._env({"SPLATS_LOCAL": 1}, pair_ctl)
            self._run()
            self.assertEqual([c for c in self.calls if isinstance(c, tuple)], [])
            self.assertEqual(len(self.failed), 1)

    def test_local_mixed_with_host_is_a_load_failure(self):
        self._env({"SPLATS_LOCAL": 1, "SPLAT_HOST": True})
        self.ns["_splat_limits"] = lambda n: None
        self._run()
        self.assertEqual(len(self.failed), 1)

    def test_host_role_refuses_a_non_host_game(self):
        self._env({}, role="splat_host")
        self._run()
        self.assertEqual(self.buz.rejected, 1)
        self.assertEqual([c for c in self.calls if isinstance(c, tuple)], [])


class _Stop(Exception):
    pass


class HostLoopTest(unittest.TestCase):
    def setUp(self):
        self.t = 0
        self.sent = []
        self.raw = []
        self.ticks = []
        time.ticks_ms = lambda: self.t
        time.ticks_diff = lambda a, b: a - b
        time.sleep_ms = self._sleep
        self.saved = dict(splat_host.__dict__)
        splat_host.HostScreen = lambda: types.SimpleNamespace(
            button=lambda *a: (None, 0.0, 0), draw=lambda *a: None, reload=lambda: None)
        splat_host.print = lambda *a: None

    def tearDown(self):
        del splat_host.print
        splat_host.HostScreen = self.saved["HostScreen"]

    def _sleep(self, ms):
        self.t += 100
        if len(self.ticks) >= self.rounds:
            raise _Stop
        self.ticks.append(self.t)

    def _loop(self, ctl, rounds, raw_msgs=(), presses=()):
        self.rounds = rounds
        msgs = list(raw_msgs)
        enow = types.SimpleNamespace(
            broadcast=lambda m: self.sent.append(m),
            poll=lambda: ("raw", msgs.pop(0), "peer") if msgs else (None, None, None))
        ctl.on_press = lambda i: None
        ctl.refresh_glow = lambda: None
        ctl.identity = "turnred"
        ctl.on_msg = lambda d, s: self.raw.append(d)
        pending = list(presses)
        ctl.poll = lambda: [pending.pop(0)] if pending else []
        read = lambda nfc, timeout=0: (None, None)
        try:
            splat_host._loop(enow, None, None, None, lambda: ctl, None, None, None,
                             lambda n: False, None, read, lambda t: None, lambda t: (None, None, None))
        except _Stop:
            pass

    def test_splat_message_reaches_station_cmd(self):
        ctl = FakeCtl(FakeGroup(2))
        self._loop(ctl, 2, raw_msgs=[{"type": "splat", "s": 0, "a": ["turnred"]}])
        self.assertEqual(ctl.group.units[0].played, [["turnred"]])
        self.assertEqual(self.raw, [])

    def test_other_raw_message_goes_to_the_pairing_handler(self):
        ctl = FakeCtl(FakeGroup(1))
        self._loop(ctl, 2, raw_msgs=[{"type": "pw_x"}])
        self.assertEqual(self.raw, [{"type": "pw_x"}])
        self.assertEqual(ctl.group.units[0].played, [])

    def test_press_broadcast_is_rate_limited_per_splat(self):
        ctl = FakeCtl(FakeGroup(2))
        # Rounds are 100 ms apart: Splat 0 pressed at 100, 200 (dropped), 300, 400 (dropped);
        # Splat 1 pressed at 200 is sent.
        presses = [(0, "press"), (0, "press"), (1, "press"), (0, "press"), (0, "press")]
        self._loop(ctl, 5, presses=presses)
        self.assertEqual([(m["s"], m["c"]) for m in self.sent],
                         [(0, "turnred"), (1, "turnred"), (0, "turnred")])

    def test_press_due_helper(self):
        last = {}
        self.assertTrue(splat_host._press_due(last, 0, 1000))
        self.assertFalse(splat_host._press_due(last, 0, 1000 + splat_host.PRESS_GAP_MS - 1))
        self.assertTrue(splat_host._press_due(last, 0, 1000 + splat_host.PRESS_GAP_MS))


if __name__ == "__main__":
    unittest.main()
