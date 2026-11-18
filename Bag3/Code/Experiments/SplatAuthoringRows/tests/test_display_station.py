"""Off-device tests for Stations/IconDisplay/lib/display_station.py (D2, D3, M3).

Runs the real module against a fake panel, a fake radio and a fake clock.
Icons come from the real Stations/IconDisplay/icons/ via the real icon_store
(icon_matrix is stubbed: it only supplies W and H there).
Run: python3 -m unittest discover -s tests
"""
import os
import sys
import time
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
DISPLAY = os.path.normpath(os.path.join(HERE, "..", "..", "..", "Stations", "IconDisplay"))

_now = [0]
time.ticks_ms = lambda: _now[0]
time.ticks_diff = lambda a, b: a - b

sys.modules.setdefault("icon_matrix", types.SimpleNamespace(W=16, H=16))
sys.path.insert(0, os.path.join(DISPLAY, "lib"))
sys.path.insert(0, DISPLAY)
_cwd = os.getcwd()
os.chdir(DISPLAY)          # icon_store reads the relative path icons/<name>.py
import display_station  # noqa: E402
os.chdir(_cwd)


class FakePanel:
    def __init__(self):
        self.src = bytearray(768)
        self.draws = 0
        self.cleared = 0

    def draw_bytes(self, src):
        self.draws += 1

    def set_intensity(self, v):
        pass

    def clear(self):
        self.cleared += 1


class FakeEnow:
    def _is_for_me(self, mac):
        return mac.replace(":", "").upper() == "AABBCCDDEEFF"


def lit(src):
    return sum(1 for i in range(0, 768, 3) if src[i] or src[i + 1] or src[i + 2])


class StationTest(unittest.TestCase):
    def setUp(self):
        _now[0] = 1000
        self.panel = FakePanel()
        self.st = display_station.Station(FakeEnow())
        os.chdir(DISPLAY)

    def tearDown(self):
        os.chdir(_cwd)

    def test_show_icon_and_unknown(self):
        self.assertTrue(self.st.handle({"type": "show", "icon": "circle"}, self.panel))
        self.assertGreater(lit(self.panel.src), 50)
        self.assertTrue(self.st.tick(self.panel))
        self.assertFalse(self.st.handle({"type": "show", "icon": "nope"}, self.panel))
        _now[0] += display_station.SHOW_HOLD_MS
        self.assertFalse(self.st.tick(self.panel))

    def test_show_px_and_text(self):
        self.assertTrue(self.st.handle({"type": "show", "px": [[0, 0, [9, 9, 9]], [15, 15, [1, 2, 3]]]}, self.panel))
        self.assertEqual(lit(self.panel.src), 2)
        self.assertTrue(self.st.handle({"type": "show", "text": "12"}, self.panel))
        self.assertGreater(lit(self.panel.src), 5)

    def test_target(self):
        self.assertFalse(self.st.handle({"type": "show", "icon": "circle", "to": "11:22:33:44:55:66"}, self.panel))
        self.assertTrue(self.st.handle({"type": "show", "icon": "circle", "to": "aa:bb:cc:dd:ee:ff"}, self.panel))

    def test_not_station_message(self):
        self.assertFalse(self.st.handle({"type": "goal"}, self.panel))
        self.assertFalse(self.st.handle([1, 2], self.panel))

    def test_dance_loops_and_queue(self):
        st, p = self.st, self.panel
        self.assertTrue(st.handle({"type": "dance", "s": ["jump", "spin"]}, p))
        st.tick(p)
        self.assertEqual(st._dance_n, 2)
        # newer dances wait; only the newest is kept
        st.handle({"type": "dance", "s": ["wave"]}, p)
        st.handle({"type": "dance", "s": ["freeze", "freeze", "bogus"]}, p)
        self.assertEqual(len(st._waiting), 2)
        # 1 loop (2 steps) done: still the first dance
        for _ in range(2):
            _now[0] += display_station.STEP_MS
            st.tick(p)
        self.assertEqual(st._dance_n, 2)
        self.assertIsNotNone(st._waiting)
        # second loop done: switch to the newest waiting dance
        for _ in range(2):
            _now[0] += display_station.STEP_MS
            st.tick(p)
        self.assertIsNone(st._waiting)
        self.assertEqual(st._step, 0)
        self.assertEqual(st._loops, 0)
        # beat bar and step dots drawn
        self.assertTrue(any(p.src[(14 * 16) * 3:(14 * 16 + 1) * 3]))
        # ends after DANCE_MAX_MS with nothing new
        _now[0] += display_station.DANCE_MAX_MS
        self.assertFalse(st.tick(p))

    def test_repeat_share_ignored(self):
        st, p = self.st, self.panel
        for _ in range(3):
            st.handle({"type": "dance", "s": ["jump", "spin"]}, p)
        self.assertIsNone(st._waiting)
        st.handle({"type": "dance", "s": ["wave"]}, p)
        st.handle({"type": "dance", "s": ["wave"]}, p)
        self.assertEqual(len(st._waiting), 1)

    def test_bad_dance(self):
        self.assertFalse(self.st.handle({"type": "dance", "s": []}, self.panel))
        self.assertFalse(self.st.handle({"type": "dance", "s": ["bogus"]}, self.panel))


if __name__ == "__main__":
    unittest.main()
