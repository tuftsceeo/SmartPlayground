"""test_station.py -- host-side tests for the NFC Station logic (CPython).

Covers text_entry, tag_catalog and the station mode machine with fake UI,
input, reader and card modules. No LVGL, no hardware.

    cd "Bag3/Code/Stations/NFC Station" && python3 tools/test_station.py
"""

import os
import sys
import tempfile
import time
import types
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

# MicroPython shims: dial_input imports M5; station uses time.*_ms.
sys.modules.setdefault("M5", types.ModuleType("M5"))
time.sleep_ms = lambda ms: None
time.ticks_ms = lambda: int(time.monotonic() * 1000)
time.ticks_diff = lambda a, b: a - b

import station                                  # noqa: E402
import tag_catalog                              # noqa: E402
import text_entry as te                         # noqa: E402
from dial_input import NEXT, PREV, ACT, EXIT    # noqa: E402


class FakeUI:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def rec(*args):
            self.calls.append((name,) + args)
        return rec

    def last(self, name):
        for c in reversed(self.calls):
            if c[0] == name:
                return c
        return None


class FakeInputs:
    def __init__(self):
        self.q = []

    def update(self):
        pass

    def pop(self):
        return self.q.pop(0) if self.q else None

    def clear(self):
        pass


class FakeNfc:
    def __init__(self):
        self.cards = []         # tags returned by successive detect_tag()
        self.field = False

    def detect_tag(self, timeout=0):
        return self.cards.pop(0) if self.cards else None

    def antenna_on(self):
        self.field = True

    def antenna_off(self):
        self.field = False

    def stop_crypto1(self):
        pass


def tag(uid="01:02"):
    return {"uid_hex": uid, "tag_type": "NTAG", "is_ntag": True}


class FakeCard:
    def __init__(self):
        self.store = {}
        self.fail = False
        self.writes = []

    def existing_text(self, nfc, t):
        return self.store.get(t["uid_hex"])

    def write_text(self, nfc, t, text):
        self.writes.append(text)
        if self.fail:
            return False
        self.store[t["uid_hex"]] = text
        return True


class FakeLink:
    def __init__(self):
        self.sent = []

    def send(self, obj):
        self.sent.append(obj)


def make(tmp):
    ui, inp, nfc, card, link = FakeUI(), FakeInputs(), FakeNfc(), FakeCard(), FakeLink()
    st = station.Station(ui, inp, link, make_nfc=lambda: nfc, card=card,
                         catalog_path=os.path.join(tmp, "catalog.json"),
                         words_path=os.path.join(tmp, "words.json"))
    st.begin()
    return st, ui, inp, nfc, card, link


def run(st, inp, *intents):
    for i in intents:
        inp.q.append(i)
        st.step()


class TextEntryTests(unittest.TestCase):
    def test_type_word(self):
        e = te.TextEntry(54)
        # "hi": h is group 1 ("fghij") index 2; i is index 3.
        for i in ("tap:1", "tap:2", "tap:1", "tap:3"):
            e.handle(i)
        self.assertEqual(e.text, "hi")
        self.assertEqual(e.handle(te.DONE), ("done", "hi"))

    def test_encoder_only(self):
        e = te.TextEntry(54)
        e.handle(NEXT)          # fghij
        e.handle(ACT)
        e.handle(ACT)           # f
        self.assertEqual(e.text, "f")
        self.assertEqual(e.mode, te.M_GROUPS)
        for _ in range(len(e.choices()) - 1):
            e.handle(NEXT)      # last item is done
        self.assertEqual(e.selected(), te.DONE)
        self.assertEqual(e.handle(ACT), ("done", "f"))

    def test_space_and_strip(self):
        e = te.TextEntry(54, text=" a ")
        self.assertEqual(e.handle(te.DONE), ("done", "a"))
        self.assertEqual(te.TextEntry(54).handle(te.DONE), ("empty",))

    def test_delete(self):
        e = te.TextEntry(54, text="ab")
        e.handle("tap:%d" % e.choices().index(te.DEL))
        self.assertEqual(e.text, "a")

    def test_full(self):
        e = te.TextEntry(2, text="ab")
        self.assertEqual(e.handle("tap:0"), None)       # open group
        self.assertEqual(e.handle("tap:0"), ("full",))  # 'a' would overflow
        self.assertEqual(e.text, "ab")

    def test_words(self):
        e = te.TextEntry(54, words=["melody", "stop"], text="go")
        e.handle("tap:%d" % e.choices().index(te.WORDS_ITEM))
        self.assertEqual(e.mode, te.M_WORDS)
        e.handle("tap:2")       # back, melody, stop
        self.assertEqual(e.text, "go stop")

    def test_no_words_item_without_words(self):
        self.assertNotIn(te.WORDS_ITEM, te.TextEntry(54).choices())

    def test_cancel(self):
        self.assertEqual(te.TextEntry(54).handle(EXIT), ("cancel",))
        e = te.TextEntry(54, text="x")
        self.assertIsNone(e.handle(EXIT))
        self.assertEqual(e.mode, te.M_CANCEL)
        e.handle(NEXT)                       # any other intent keeps text
        self.assertEqual(e.mode, te.M_GROUPS)
        e.handle(EXIT)
        self.assertEqual(e.handle(EXIT), ("cancel",))

    def test_exit_from_chars_returns_to_groups(self):
        e = te.TextEntry(54)
        e.handle("tap:0")
        self.assertIsNone(e.handle(EXIT))
        self.assertEqual(e.mode, te.M_GROUPS)

    def test_tap_out_of_range_ignored(self):
        e = te.TextEntry(54)
        self.assertIsNone(e.handle("tap:40"))
        self.assertEqual(e.mode, te.M_GROUPS)


class CatalogTests(unittest.TestCase):
    def test_builtin(self):
        with tempfile.TemporaryDirectory() as d:
            g = tag_catalog.load_groups(os.path.join(d, "none.json"))
        names = [n for n, _ in g]
        self.assertIn("Melody", names)
        self.assertEqual(names[-1], "Controls")

    def test_index_drops_getcode_and_lowercases(self):
        g = tag_catalog.groups_from_index(
            {"goalrace": {"name": "Goalrace",
                          "tags": ["getcode:goalrace", "GoalRace", "goal", "goal"]}})
        self.assertEqual(g, [("Goalrace", ["goalrace", "goal"])])

    def test_bad_index_raises(self):
        with self.assertRaises(ValueError):
            tag_catalog.groups_from_index(["x"])

    def test_words_include_tags(self):
        w = tag_catalog.load_words([("G", ["a", "b"])], "/nonexistent/words.json")
        self.assertEqual(w, ["a", "b"])


class StationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.st, self.ui, self.inp, self.nfc, self.card, self.link = make(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_text_max(self):
        self.assertEqual(station.TEXT_MAX, 54)

    def test_text_max_fits_reader_window(self):
        # card_writer.existing_text reads NTAG pages 4-19 (64 bytes).
        import card_writer
        fits = card_writer.build_ndef_text("x" * station.TEXT_MAX)
        self.assertEqual(len(fits), station.READ_WINDOW)
        self.assertEqual(card_writer._decode_ndef_text(fits), "x" * station.TEXT_MAX)
        # Two past the limit, the record itself is cut by the read window
        # and reads back truncated (a write would then fail verify).
        over = card_writer.build_ndef_text("x" * (station.TEXT_MAX + 2))
        self.assertNotEqual(card_writer._decode_ndef_text(over[:station.READ_WINDOW]),
                            "x" * (station.TEXT_MAX + 2))

    def test_boot_home(self):
        self.assertEqual(self.st.mode, station.HOME)
        self.assertEqual(self.link.sent[0]["type"], "identity")
        self.assertFalse(self.nfc.field)

    def test_tag_write_flow(self):
        run(self.st, self.inp, NEXT, ACT)               # Tags
        self.assertEqual(self.st.mode, station.GAMES)
        run(self.st, self.inp, ACT)                     # first game
        self.assertEqual(self.st.mode, station.TAGS)
        target = self.st.groups[0][1][0]
        run(self.st, self.inp, ACT)
        self.assertEqual(self.st.mode, station.SCAN)
        self.assertTrue(self.nfc.field)
        self.nfc.cards.append(tag())
        self.st.step()
        self.assertEqual(self.card.store["01:02"], target)
        self.assertEqual(self.st.mode, station.TAGS)
        self.assertFalse(self.nfc.field)
        self.assertEqual(self.link.sent[-1]["type"], "card_written")

    def test_already_written_not_rewritten(self):
        self.card.store["01:02"] = "stop"
        self.st.go_scan("stop", station.HOME)
        self.nfc.cards.append(tag())
        self.st.step()
        self.assertEqual(self.card.writes, [])
        self.assertEqual(self.ui.last("show_result")[2], "Already Set")

    def test_failed_write_rearms(self):
        self.card.fail = True
        self.st.go_scan("stop", station.HOME)
        self.nfc.cards.append(tag())
        self.st.step()
        self.assertEqual(self.st.mode, station.SCAN)
        self.assertEqual(self.link.sent[-1]["type"], "write_failed")

    def test_scan_exit_returns(self):
        self.st.go_scan("stop", station.READ)
        run(self.st, self.inp, EXIT)
        self.assertEqual(self.st.mode, station.READ)

    def test_read_then_copy(self):
        self.card.store["AA"] = "melody"
        run(self.st, self.inp, ACT)                     # Read
        self.assertEqual(self.st.mode, station.READ)
        self.nfc.cards.append(tag("AA"))
        self.st.step()
        self.assertEqual(self.ui.last("show_reader")[1], "melody")
        self.nfc.cards.append(tag("AA"))                # same card resting
        self.st.step()
        self.assertEqual(sum(1 for c in self.ui.calls if c[0] == "show_reader" and c[1]), 1)
        run(self.st, self.inp, ACT)                     # copy
        self.assertEqual(self.st.mode, station.SCAN)
        self.nfc.cards.append(tag("BB"))
        self.st.step()
        self.assertEqual(self.card.store["BB"], "melody")
        self.assertEqual(self.st.mode, station.READ)

    def test_text_flow(self):
        run(self.st, self.inp, PREV, ACT)               # Text
        self.assertEqual(self.st.mode, station.TEXT)
        run(self.st, self.inp, "tap:0", "tap:0")        # 'a'
        run(self.st, self.inp, "tap:%d" % self.st.entry.choices().index(te.DONE))
        self.assertEqual(self.st.mode, station.SCAN)
        self.assertEqual(self.st.scan_text, "a")
        run(self.st, self.inp, EXIT)                    # back keeps text
        self.assertEqual(self.st.mode, station.TEXT)
        self.assertEqual(self.st.entry.text, "a")
        run(self.st, self.inp, EXIT, EXIT)              # discard
        self.assertEqual(self.st.mode, station.HOME)

    def test_serial_catalog_and_write(self):
        self.st.dispatch({"cmd": "catalog.set", "id": 1,
                          "index": {"g": {"name": "G", "tags": ["x", "y"]}}})
        self.assertEqual(self.st.groups[0], ("G", ["x", "y"]))
        self.assertEqual(self.st.groups[-1][0], "Controls")
        self.st.dispatch({"cmd": "write", "id": 2, "text": "Hello"})
        self.assertEqual(self.st.scan_text, "hello")
        self.st.dispatch({"cmd": "write", "id": 3, "text": "x" * 60})
        self.assertEqual(self.link.sent[-1]["code"], "bad_text")
        self.st.dispatch({"cmd": "nope"})
        self.assertEqual(self.link.sent[-1]["code"], "unknown_cmd")

    def test_reader_init_failure_raises(self):
        def boom():
            raise OSError("no ack")
        st = station.Station(FakeUI(), FakeInputs(), FakeLink(), make_nfc=boom,
                             card=FakeCard(),
                             catalog_path=os.path.join(self.tmp.name, "c.json"),
                             words_path=os.path.join(self.tmp.name, "w.json"))
        with self.assertRaises(OSError):
            st.begin()


class _Stub:
    """Accepts any attribute access or call; stands in for lvgl / m5ui."""

    def __getattr__(self, name):
        return _Stub()

    def __call__(self, *a, **k):
        return _Stub()


class PainterSmokeTests(unittest.TestCase):
    """Runs every station_ui painter against stubbed lvgl/m5ui/M5.

    Catches Python errors in station_ui's own logic (indexing, arguments,
    text formatting). Says nothing about whether the LVGL calls are right.
    """

    def setUp(self):
        for name in ("lvgl", "m5ui"):
            sys.modules[name] = _Stub()
        m5 = sys.modules["M5"]
        m5.Speaker = _Stub()
        import importlib
        import station_fonts
        import station_ui
        importlib.reload(station_fonts)
        self.mod = importlib.reload(station_ui)

    def test_painters(self):
        ui = self.mod.StationUI(FakeInputs())
        ui.begin()
        ui.show_ring(["Read", "Tags", "Text"], 2)
        ui.show_list("Games", ["a"], 0)
        ui.show_list("Games", ["a", "b", "c"], 2)
        ui.show_reader(None)
        ui.show_reader("melody", "NTAG")
        ui.show_reader(None, "NTAG")
        ui.show_scan("stop")
        for kind in self.mod.KIND_STYLE:
            ui.show_result(kind, "T", "b")
        e = te.TextEntry(54, words=["melody"], text="x" * 20)
        ui.show_keyboard(e.view())
        e.handle("tap:0")
        ui.show_keyboard(e.view())
        e.handle(EXIT)
        e.handle("tap:%d" % e.choices().index(te.WORDS_ITEM))
        ui.show_keyboard(e.view())
        e.handle(EXIT)
        e.handle(EXIT)
        self.assertEqual(e.mode, te.M_CANCEL)
        ui.show_keyboard(e.view())
        self.assertLessEqual(len(te.TextEntry(54, words=["w"]).choices()),
                             self.mod.RING_SLOTS)
        ui.beep_success()
        ui.beep_fail()


if __name__ == "__main__":
    unittest.main()
