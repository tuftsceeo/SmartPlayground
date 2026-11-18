"""Off-device unit tests for the experiment's Splat logic.

Covers splatpair.GameSplats (type 2 handle) and splat_host._station_cmd
(station mode). Radio and display modules are stubbed; no Simulator needed.
Run: python3 -m unittest discover -s tests
"""
import os
import sys
import types
import unittest

LIB = os.path.join(os.path.dirname(__file__), "..", "wand", "lib")
sys.path.insert(0, LIB)


def _stub(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod
    return mod


_stub("pairing", MAX_SPLATS=2, HOST_MAX_SPLATS=4)
_stub("pwire")
_stub("leds", **{n: 0 for n in (
    "SHAPE_X", "SHAPE_CHECK", "RED", "GREEN", "BLUE", "MAGENTA", "AMBER", "WHITE")})

import splatpair  # noqa: E402
import splat_host  # noqa: E402


class FakeUnit:
    def __init__(self, connected=True):
        self.connected = connected
        self.played = []

    def play(self, names):
        self.played.append(list(names))


class FakeGroup:
    def __init__(self, n, connected=None):
        self.units = [FakeUnit(connected is None or i in connected) for i in range(n)]
        self.count = n

    def unit(self, i):
        return self.units[i]


class FakeCtl:
    def __init__(self, group, events=()):
        self.group = group
        self.count = group.count if group else 0
        self._events = list(events)
        self.paused = False

    def pause_search(self):
        self.paused = True

    def resume_search(self):
        self.paused = False

    def poll(self):
        ev, self._events = self._events, []
        return ev


class GameSplatsTest(unittest.TestCase):
    def test_pauses_search_and_resumes_on_close(self):
        ctl = FakeCtl(FakeGroup(2))
        gs = splatpair.GameSplats(ctl)
        self.assertTrue(ctl.paused)
        gs.close()
        self.assertFalse(ctl.paused)

    def test_count_and_unit(self):
        ctl = FakeCtl(FakeGroup(2))
        gs = splatpair.GameSplats(ctl)
        self.assertEqual(gs.count, 2)
        self.assertIs(gs.unit(1), ctl.group.units[1])

    def test_poll_yields_events_in_order_then_none(self):
        ctl = FakeCtl(FakeGroup(2), [(0, "press"), (1, "press"), (0, "release")])
        gs = splatpair.GameSplats(ctl)
        self.assertEqual(gs.poll(), ("press", 0))
        self.assertEqual(gs.poll(), ("press", 1))
        self.assertEqual(gs.poll(), ("release", 0))
        self.assertIsNone(gs.poll())


class StationCmdTest(unittest.TestCase):
    def setUp(self):
        self.out = []
        self._print = splat_host.print if hasattr(splat_host, "print") else None
        splat_host.print = lambda *a: self.out.append(" ".join(str(x) for x in a))

    def tearDown(self):
        del splat_host.print

    def test_all_connected_units_when_s_absent(self):
        ctl = FakeCtl(FakeGroup(3, connected={0, 2}))
        splat_host._station_cmd(ctl, {"type": "splat", "a": ["turnred"]})
        self.assertEqual([u.played for u in ctl.group.units],
                         [[["turnred"]], [], [["turnred"]]])

    def test_single_unit_when_s_given(self):
        ctl = FakeCtl(FakeGroup(2))
        splat_host._station_cmd(ctl, {"type": "splat", "s": 1, "a": ["turnblue"]})
        self.assertEqual([u.played for u in ctl.group.units], [[], [["turnblue"]]])

    def test_unknown_action_is_reported_and_nothing_plays(self):
        ctl = FakeCtl(FakeGroup(1))
        splat_host._station_cmd(ctl, {"a": ["turnred", "bogus"]})
        self.assertEqual(ctl.group.units[0].played, [])
        self.assertTrue(any("[ERR]" in line and "bogus" in line for line in self.out))

    def test_bad_index_and_bad_shape_are_reported(self):
        ctl = FakeCtl(FakeGroup(2))
        for data in ({"s": 2, "a": ["turnred"]}, {"s": -1, "a": ["turnred"]},
                     {"a": "turnred"}, {}):
            splat_host._station_cmd(ctl, data)
        self.assertEqual(len(self.out), 4)
        self.assertTrue(all("[ERR]" in line for line in self.out))

    def test_no_group_is_reported(self):
        splat_host._station_cmd(FakeCtl(None), {"a": ["turnred"]})
        self.assertEqual(len(self.out), 1)


if __name__ == "__main__":
    unittest.main()
