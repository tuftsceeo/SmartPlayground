"""test_dial_station.py -- host tests for the Dial's screens (CPython).

Drives bdial_server.BdialServer as station.py's host, with fake UI, input,
reader, card module, radio and serial link. No LVGL, no hardware.

    python3 Bag3/Code/TeacherTools/BroadcastDial/BDialFirmware/tools/test_dial_station.py
"""

import os
import sys
import time
import types
import unittest

BD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BD)

for name in ("M5", "machine", "network", "espnow", "hardware"):
    sys.modules.setdefault(name, types.ModuleType(name))
sys.modules["machine"].unique_id = lambda: b"\x01\x02\x03\x04\x00\x4c"
_stats = types.ModuleType("stats_log")
_stats.record_tag = lambda label: None
sys.modules["stats_log"] = _stats
time.sleep_ms = lambda ms: None
time.ticks_ms = lambda: int(time.monotonic() * 1000)
time.ticks_diff = lambda a, b: a - b
time.ticks_add = lambda a, b: a + b

import bdial_server as BS                       # noqa: E402
import station                                  # noqa: E402
from dial_input import NEXT, PREV, ACT, EXIT, TURN_SETTLE_MS   # noqa: E402


class FakeUI:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def rec(*args, **kw):
            self.calls.append((name,) + args + tuple(kw.values()))
        return rec

    def last(self, name):
        for c in reversed(self.calls):
            if c[0] == name:
                return c
        return None


class FakeInputs:
    def __init__(self):
        self.q = []
        self.settle_ms = TURN_SETTLE_MS

    def update(self):
        pass

    def pop(self):
        return self.q.pop(0) if self.q else None

    def peek(self):
        return self.q[0] if self.q else None

    def clear(self):
        pass

    def hold_fraction(self):
        return None


class FakeCode:
    """Radio: records when it was up while the field was on."""
    def __init__(self, nfc):
        self.nfc = nfc
        self.armed = False
        self.overlap = False
        self.last_result = None

    def arm(self):
        self.armed = True
        return True

    def disarm(self):
        self.armed = False

    def poll(self, on_event=None, on_msg=None):
        if self.nfc.field:
            self.overlap = True

    def set_game(self, slug):
        pass

    def resolve(self):
        return None


class FakeNfc:
    def __init__(self):
        self.cards = []
        self.field = False
        self.code = None
        self.overlap = False

    def detect_tag(self, timeout=0):
        return self.cards.pop(0) if self.cards else None

    def antenna_on(self):
        if self.code is not None and self.code.armed:
            self.overlap = True
        self.field = True

    def antenna_off(self):
        self.field = False

    def stop_crypto1(self):
        pass


class FakeCard:
    def __init__(self):
        self.store = {}
        self.fail = False

    def existing_text(self, nfc, t):
        return self.store.get(t["uid_hex"])

    def write_text(self, nfc, t, text):
        if self.fail:
            return False
        self.store[t["uid_hex"]] = text
        return True


class FakeLink:
    def __init__(self):
        self.sent = []

    def send(self, obj):
        self.sent.append(obj)


def tag(uid):
    return {"uid_hex": uid, "tag_type": "NTAG", "sak": 0}


def make(games=None):
    srv = BS.BdialServer()
    srv.link = FakeLink()
    srv.nfc = FakeNfc()
    srv.code = FakeCode(srv.nfc)
    srv.nfc.code = srv.code
    srv._index = dict((k, dict(v)) for k, v in (games or {}).items())
    srv._active = next(iter(srv._index), None)
    srv._mode = BS.MODE_WRITE if srv._index else BS.MODE_IDLE
    srv.ui = FakeUI()
    srv._input = FakeInputs()
    srv.card = FakeCard()
    srv.st = station.Station(srv.ui, srv._input, srv, srv.card)
    srv._rebuild_entries()
    srv.st.go_home()
    return srv


def run(srv, *intents):
    for i in intents:
        srv._input.q.append(i)
        srv.st.step()
        srv._serve()


def idle(srv, n=1):
    for _ in range(n):
        srv.st.step()
        srv._serve()


def finish_wait(srv):
    srv.st._wait_until = time.ticks_ms() - 1
    idle(srv)


MELODY = {"melody": {"name": "Melody", "tags": ["note_c", "note_d"]}}


class Menus(unittest.TestCase):
    def test_no_game(self):
        srv = make()
        run(srv, NEXT, ACT)                         # Tags
        self.assertEqual(srv.ui.last("show_list")[1:], ("No Game", ["Utility Tags"], 0))
        self.assertFalse(srv.code.armed)

    def test_game_rows(self):
        srv = make(MELODY)
        run(srv, NEXT, ACT, ACT)                    # Tags -> Melody
        self.assertEqual(srv.ui.last("show_list")[1:],
                         ("Melody", ["All", "Code", "Play", "note_c", "note_d"], 0))

    def test_utility_has_no_all(self):
        srv = make(MELODY)
        run(srv, NEXT, ACT, NEXT, ACT)
        self.assertEqual(srv.ui.last("show_list")[2], ["stop", "battery"])

    def test_settle_only_on_long_lists(self):
        games = dict(("g%d" % i, {"name": "G%d" % i}) for i in range(12))
        srv = make(games)
        self.assertEqual(srv._input.settle_ms, 0)          # home ring
        run(srv, NEXT, ACT)                                 # 13 groups
        self.assertEqual(srv._input.settle_ms, TURN_SETTLE_MS)
        run(srv, ACT)                                       # 3 rows
        self.assertEqual(srv._input.settle_ms, 0)

    def test_games_select_refreshes_list(self):
        srv = make(MELODY)
        run(srv, NEXT, ACT)
        srv._index["jump"] = {"name": "Jump"}
        srv._rebuild_entries()
        self.assertEqual(srv.ui.last("show_list")[2], ["Melody", "Jump", "Utility Tags"])


class Radio(unittest.TestCase):
    def test_serves_on_menus_only(self):
        srv = make(MELODY)
        idle(srv)
        self.assertTrue(srv.code.armed)             # home
        run(srv, NEXT, ACT)
        self.assertTrue(srv.code.armed)             # games
        run(srv, ACT)
        self.assertTrue(srv.code.armed)             # tags
        run(srv, NEXT, ACT)                         # Code -> scan
        self.assertEqual(srv.st.mode, station.SCAN)
        self.assertFalse(srv.code.armed)
        run(srv, EXIT)
        self.assertTrue(srv.code.armed)
        run(srv, EXIT, EXIT, NEXT, ACT)             # home (on Tags) -> Text
        self.assertEqual(srv.st.mode, station.TEXT)
        self.assertFalse(srv.code.armed)
        self.assertFalse(srv.nfc.overlap or srv.code.overlap)

    def test_off_during_result_hold(self):
        srv = make(MELODY)
        run(srv, NEXT, ACT, ACT, NEXT, NEXT, ACT)   # Play -> scan
        srv.nfc.cards.append(tag("AA"))
        idle(srv)
        self.assertEqual(srv.st.mode, station.SCAN)  # result held
        self.assertFalse(srv.code.armed)
        finish_wait(srv)
        self.assertEqual(srv.st.mode, station.TAGS)
        self.assertTrue(srv.code.armed)

    def test_read_is_off(self):
        srv = make(MELODY)
        idle(srv)
        run(srv, ACT)
        self.assertEqual(srv.st.mode, station.READ)
        self.assertFalse(srv.code.armed)
        self.assertFalse(srv.nfc.overlap)


class Writes(unittest.TestCase):
    def test_write_all_code_first_pinned(self):
        srv = make(MELODY)
        run(srv, NEXT, ACT, ACT, ACT)               # All
        uids = ["A1", "A2", "A3", "A4"]
        for i, u in enumerate(uids):
            srv.nfc.cards.append(tag(u))
            idle(srv)
            finish_wait(srv)
            if i < len(uids) - 1:
                self.assertEqual(srv.st.mode, station.ALLNEXT)
                idle(srv, station.ABSENT_POLLS)     # card lifted
        finish_wait(srv)
        self.assertEqual([srv.card.store[u] for u in uids],
                         ["getcode:melody@" + BS.HOST_ID, "melody", "note_c", "note_d"])
        labels = [m["label"] for m in srv.link.sent if m["type"] == "card_written"]
        self.assertEqual(labels, ["getcode:melody", "melody", "note_c", "note_d"])
        self.assertEqual(srv._written["note_c"], 1)

    def test_already_set_not_rewritten(self):
        srv = make(MELODY)
        srv.card.store["AA"] = "getcode:melody@" + BS.HOST_ID
        run(srv, NEXT, ACT, ACT, NEXT, ACT)
        srv.nfc.cards.append(tag("AA"))
        idle(srv)
        self.assertEqual(srv.ui.last("show_result")[1:3], ("ok", "Already Set"))
        self.assertEqual([m for m in srv.link.sent if m["type"] == "card_written"], [])

    def test_failed_write_rearms(self):
        srv = make(MELODY)
        srv.card.fail = True
        run(srv, NEXT, ACT, ACT, NEXT, NEXT, ACT)
        srv.nfc.cards.append(tag("AA"))
        idle(srv)
        self.assertEqual(srv.ui.last("show_result")[1], "fail")
        finish_wait(srv)
        self.assertEqual((srv.st.mode, srv.st.scan_tag), (station.SCAN, "melody"))

    def test_read_copy_keeps_pin(self):
        srv = make(MELODY)
        pinned = "getcode:melody@" + BS.HOST_ID
        srv.card.store["AA"] = pinned
        run(srv, ACT)
        srv.nfc.cards.append(tag("AA"))
        idle(srv)
        self.assertEqual(srv.ui.last("show_reader")[1], pinned)
        run(srv, ACT)                               # copy
        srv.nfc.cards.append(tag("BB"))
        idle(srv)
        self.assertEqual(srv.card.store["BB"], pinned)

    def test_text_write(self):
        srv = make(MELODY)
        run(srv, PREV, ACT)                         # Text
        run(srv, "tap:0", "tap:1")                  # "ab"
        run(srv, "done")
        self.assertEqual(srv.st.mode, station.SCAN)
        srv.nfc.cards.append(tag("CC"))
        idle(srv)
        self.assertEqual(srv.card.store["CC"], "ab")

    def test_games_cleared_mid_scan(self):
        srv = make(MELODY)
        run(srv, NEXT, ACT, ACT, NEXT, NEXT, ACT)   # Play -> scan
        srv._index = {}
        srv._rebuild_entries()
        self.assertEqual(srv.st.mode, station.GAMES)
        run(srv, EXIT, ACT, ACT)                    # home (on Tags) -> Tags -> Utility
        self.assertEqual(srv.ui.last("show_list")[2], ["stop", "battery"])

    def test_copied_code_card_counts_as_code(self):
        srv = make(MELODY)
        srv.on_written("getcode:melody@" + BS.HOST_ID, "BB", True)
        self.assertEqual(srv._written, {"getcode:melody": 1})

    def test_words_from_games(self):
        srv = make(MELODY)
        self.assertEqual(srv.words()[:4], ["melody", "note_c", "note_d", "stop"])


if __name__ == "__main__":
    unittest.main()
