"""test_station.py -- host-side tests for the NFC Station logic (CPython).

Covers text_entry, tag_catalog and the station mode machine with fake UI,
input, reader and card modules. No LVGL, no hardware.

    cd "Bag3/Code/Stations/NFC Station" && python3 tools/test_station.py
"""

import math
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
    def tap(self, e, item):
        return e.handle("tap:%d" % e.choices().index(item))

    def test_type_word_by_tap(self):
        e = te.TextEntry(54)
        self.tap(e, "h")
        self.tap(e, "i")
        self.assertEqual(e.text, "hi")
        self.assertEqual(e.handle(te.DONE), ("done", "hi"))

    def test_encoder_one_detent_per_letter(self):
        e = te.TextEntry(54)
        for _ in range(7):
            e.handle(NEXT)
        self.assertEqual(e.selected(), "h")
        e.handle(ACT)
        e.handle(NEXT)
        e.handle(ACT)
        self.assertEqual(e.text, "hi")
        e.handle(ACT)                       # highlight stays: "i" again
        self.assertEqual(e.text, "hii")
        for _ in range(9):
            e.handle(PREV)                  # 'i' (8) wraps back to done (29)
        self.assertEqual(e.selected(), te.DONE)
        self.assertEqual(e.handle(ACT), ("done", "hii"))

    def test_letters_ring_segments(self):
        self.assertEqual(len(te.LETTERS), 30)
        self.assertEqual(len(te.LETTERS) % te.SEGMENT, 0)

    def test_space_and_strip(self):
        e = te.TextEntry(54, text=" a ")
        self.assertEqual(e.handle(te.DONE), ("done", "a"))
        self.assertEqual(te.TextEntry(54).handle(te.DONE), ("empty",))

    def test_delete(self):
        e = te.TextEntry(54, text="ab")
        self.tap(e, te.DEL)
        self.assertEqual(e.text, "a")

    def test_full(self):
        e = te.TextEntry(2, text="ab")
        self.assertEqual(self.tap(e, "a"), ("full",))
        self.assertEqual(e.text, "ab")

    def test_more_ring_and_return(self):
        e = te.TextEntry(54)
        for _ in range(4):
            e.handle(NEXT)                  # 'e'
        self.tap(e, te.MORE_ITEM)
        self.assertEqual(e.mode, te.M_MORE)
        self.tap(e, "7")
        self.assertEqual(e.text, "7")
        self.tap(e, te.LETTERS_ITEM)
        self.assertEqual(e.mode, te.M_LETTERS)
        self.assertEqual(e.selected(), te.MORE_ITEM)   # where it was left

    def test_words(self):
        e = te.TextEntry(54, words=["melody", "stop"], text="go")
        self.tap(e, te.MORE_ITEM)
        self.tap(e, te.WORDS_ITEM)
        self.assertEqual(e.mode, te.M_WORDS)
        self.tap(e, "stop")
        self.assertEqual(e.text, "go stop")
        self.assertEqual(e.mode, te.M_LETTERS)

    def test_no_words_item_without_words(self):
        e = te.TextEntry(54)
        self.tap(e, te.MORE_ITEM)
        self.assertNotIn(te.WORDS_ITEM, e.choices())

    def test_cancel(self):
        self.assertEqual(te.TextEntry(54).handle(EXIT), ("cancel",))
        e = te.TextEntry(54, text="x")
        self.assertIsNone(e.handle(EXIT))
        self.assertEqual(e.mode, te.M_CANCEL)
        e.handle(NEXT)                       # any other intent keeps text
        self.assertEqual(e.mode, te.M_LETTERS)
        e.handle(EXIT)
        self.assertEqual(e.handle(EXIT), ("cancel",))

    def test_written_flag(self):
        e = te.TextEntry(54, text="go")
        self.assertFalse(e.view()["written"])
        e.mark_written("go")
        self.assertTrue(e.view()["written"])
        self.tap(e, "a")                    # edited after writing
        self.assertFalse(e.view()["written"])
        self.tap(e, te.DEL)
        self.assertTrue(e.view()["written"])
        self.assertEqual(e.handle(EXIT), ("cancel",))   # no confirm needed

    def test_exit_from_more_returns_to_letters(self):
        e = te.TextEntry(54)
        self.tap(e, te.MORE_ITEM)
        self.assertIsNone(e.handle(EXIT))
        self.assertEqual(e.mode, te.M_LETTERS)

    def test_tap_out_of_range_ignored(self):
        e = te.TextEntry(54)
        self.assertIsNone(e.handle("tap:40"))
        self.assertEqual(e.text, "")


class DialInputTests(unittest.TestCase):
    """dial_input button logic with a fake M5.BtnA and clock."""

    def setUp(self):
        import dial_input
        self.di = dial_input
        self.down = False
        self.now = 0
        btn = types.SimpleNamespace(isPressed=lambda: self.down)
        sys.modules["M5"].BtnA = btn
        sys.modules["M5"].update = lambda: None
        self._ticks = time.ticks_ms
        time.ticks_ms = lambda: self.now
        self.inp = dial_input.DialInput()

    def tearDown(self):
        time.ticks_ms = self._ticks

    def press(self, ms):
        self.down = True
        self.inp.update()
        for _ in range(ms // 10):
            self.now += 10
            self.inp.update()

    def release(self, after_ms=0):
        self.now += after_ms
        self.down = False
        self.inp.update()

    def drain(self):
        out = []
        while True:
            i = self.inp.pop()
            if i is None:
                return out
            out.append(i)

    def test_press_lengths(self):
        import dial_input
        cases = ((100, [ACT]),                      # quick
                 (300, [ACT]),                      # kind of quick
                 (dial_input.HOLD_MAYBE_MS, []),    # ring showing: failed hold
                 (800, []),
                 (1000, [EXIT]))                    # ring full: hold
        for ms, want in cases:
            self.press(ms)
            self.release()
            self.assertEqual(self.drain(), want, ms)

    def test_short_click(self):
        self.press(100)
        self.release()
        self.assertEqual(self.drain(), [ACT])

    def test_hold_then_clear_then_late_release_is_silent(self):
        self.press(1000)
        self.assertEqual(self.drain(), [EXIT])
        self.inp.clear()                    # screen change while still held
        self.assertIsNone(self.inp.hold_fraction())
        self.now += 1500                    # user keeps holding
        self.inp.update()
        self.release(after_ms=800)
        self.assertEqual(self.drain(), [])  # no stray click, no second EXIT

    def test_short_click_across_slow_redraw_is_a_click(self):
        # Press seen, then the loop blocks 1.2 s in a redraw; the button was
        # released in the meantime but the next poll still reads it down.
        self.down = True
        self.inp.update()
        self.now += 1200
        self.inp.update()                   # stale "down" after the redraw
        self.release(after_ms=10)
        self.assertEqual(self.drain(), [ACT])

    def test_real_hold_with_normal_polling_exits(self):
        self.down = True
        self.inp.update()
        for _ in range(100):                # 100 polls x 10 ms
            self.now += 10
            self.inp.update()
        self.assertEqual(self.drain(), [EXIT])

    def test_hold_through_blocking_read_exits(self):
        # Button held throughout; the loop blocks 2 s twice (NFC reads).
        self.down = True
        self.inp.update()
        for gap in (10, 2000, 10, 2000, 10):
            self.now += gap
            self.inp.update()
        self.assertEqual(self.drain(), [EXIT])

    def test_next_press_after_spent_hold_works(self):
        self.press(1000)
        self.inp.clear()
        self.release(after_ms=500)
        self.press(100)
        self.release()
        self.assertEqual(self.drain(), [ACT])


class CatalogTests(unittest.TestCase):
    def test_builtin(self):
        with tempfile.TemporaryDirectory() as d:
            g = tag_catalog.load_groups(os.path.join(d, "none.json"))
        names = [n for n, _ in g]
        self.assertIn("Melody", names)
        self.assertEqual(dict(g)["Melody"][0], "melody")
        self.assertIn("note_c_high", dict(g)["Melody"])
        self.assertEqual(names[-1], "Utilities")

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

    def test_hold_ring_hidden_on_home(self):
        self.inp.hold_fraction = lambda: 0.5
        self.st.step()
        self.assertEqual(self.ui.last("show_hold"), ("show_hold", None))
        run(self.st, self.inp, ACT)                     # Read
        self.st.step()
        self.assertEqual(self.ui.last("show_hold"), ("show_hold", 0.5))
        self.inp.hold_fraction = lambda: None

    def test_boot_home(self):
        self.assertEqual(self.st.mode, station.HOME)
        self.assertEqual(self.link.sent[0]["type"], "identity")
        self.assertFalse(self.nfc.field)

    def _open_game(self, name):
        run(self.st, self.inp, NEXT, ACT)               # Tags -> GAMES
        self.st.game_sel = [n for n, _ in self.st.groups].index(name)
        run(self.st, self.inp, ACT)

    def test_single_tag_game_scans_directly(self):
        self._open_game("Jump")
        self.assertEqual(self.st.mode, station.SCAN)
        self.assertEqual(self.st.scan_text, "jump")
        self.nfc.cards.append(tag())
        self.st.step()
        self.assertEqual(self.card.store["01:02"], "jump")
        self.assertEqual(self.st.mode, station.GAMES)
        self.assertFalse(self.nfc.field)
        self.assertEqual(self.link.sent[-1]["type"], "card_written")

    def test_multi_tag_game_options(self):
        self._open_game("Goalrace")
        self.assertEqual(self.st.mode, station.TAGS)
        rows = self.st.tag_options()
        self.assertEqual(rows, [("All", None), ("Start Goalrace", "goalrace"),
                                ("teamgreen", "teamgreen"), ("teamblue", "teamblue"),
                                ("goal", "goal")])
        run(self.st, self.inp, NEXT, NEXT, ACT)         # teamgreen
        self.assertEqual(self.st.scan_text, "teamgreen")
        self.nfc.cards.append(tag())
        self.st.step()
        self.assertEqual(self.st.mode, station.TAGS)

    def test_write_all_waits_for_card_removal(self):
        self._open_game("Goalrace")
        run(self.st, self.inp, ACT)                     # All
        written = []
        for i, want in enumerate(["goalrace", "teamgreen", "teamblue", "goal"]):
            self.assertEqual(self.st.mode, station.SCAN)
            self.assertEqual(self.st.scan_text, want)
            self.nfc.cards.append(tag("C%d" % i))
            self.st.step()
            written.append(self.card.store["C%d" % i])
            if i < 3:
                self.assertEqual(self.st.mode, station.ALLNEXT)
                self.nfc.cards.append(tag("C%d" % i))   # still on the reader
                self.st.step()
                self.assertEqual(self.st.mode, station.ALLNEXT)
                for _ in range(station.ABSENT_POLLS):   # lifted
                    self.st.step()
        self.assertEqual(written, ["goalrace", "teamgreen", "teamblue", "goal"])
        self.assertEqual(self.st.mode, station.TAGS)
        self.assertEqual(self.ui.last("show_result")[2], "All Done")

    def test_read_returns_to_hold_card_after_lift(self):
        clock = [0]
        time.ticks_ms = lambda: clock[0]
        try:
            self.card.store["AA"] = "melody"
            run(self.st, self.inp, ACT)                 # Read
            self.nfc.cards.append(tag("AA"))
            self.st.step()
            self.assertEqual(self.ui.last("show_reader")[1], "melody")
            for _ in range(station.ABSENT_POLLS):       # lifted
                self.st.step()
            clock[0] += station.READ_CLEAR_MS - 1
            self.st.step()
            self.assertEqual(self.ui.last("show_reader")[1], "melody")
            self.assertEqual(self.st.read_text, "melody")   # Copy still works
            clock[0] += 1
            self.st.step()
            self.assertEqual(self.ui.last("show_reader"), ("show_reader", None, False))
            self.assertIsNone(self.st.read_text)
        finally:
            time.ticks_ms = lambda: int(time.monotonic() * 1000)

    def test_read_clear_waits_while_button_held(self):
        clock = [0]
        time.ticks_ms = lambda: clock[0]
        try:
            self.card.store["AA"] = "melody"
            run(self.st, self.inp, ACT)
            self.nfc.cards.append(tag("AA"))
            self.st.step()
            for _ in range(station.ABSENT_POLLS):
                self.st.step()
            self.inp.hold_fraction = lambda: 0.5        # hold in progress
            clock[0] += station.READ_CLEAR_MS + 10
            self.st.step()
            self.assertEqual(self.st.read_text, "melody")
            self.inp.hold_fraction = lambda: None
        finally:
            time.ticks_ms = lambda: int(time.monotonic() * 1000)

    def test_read_single_hold_exits_home(self):
        run(self.st, self.inp, ACT, EXIT)
        self.assertEqual(self.st.mode, station.HOME)

    def test_utilities_has_no_all(self):
        self.st.game_sel = [n for n, _ in self.st.groups].index("Utilities")
        rows = self.st.tag_options()
        self.assertEqual([r[1] for r in rows], ["start", "stop", "battery"])

    def test_read_ignores_single_missed_poll(self):
        self.card.store["AA"] = "melody"
        run(self.st, self.inp, ACT)                     # Read
        reads = []
        self.card.existing_text = lambda nfc, t: (reads.append(1), "melody")[1]
        for present in (1, 0, 1, 0, 0, 1):              # flicker, no lift
            if present:
                self.nfc.cards.append(tag("AA"))
            self.st.step()
        self.assertEqual(len(reads), 1)
        for _ in range(station.ABSENT_POLLS):           # real lift
            self.st.step()
        self.nfc.cards.append(tag("AA"))
        self.st.step()
        self.assertEqual(len(reads), 2)

    def test_write_all_exit_returns_to_options(self):
        self._open_game("Goalrace")
        run(self.st, self.inp, ACT, EXIT)               # All, then back out
        self.assertEqual(self.st.mode, station.TAGS)

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
        run(self.st, self.inp, "tap:0")                 # 'a'
        run(self.st, self.inp, "tap:%d" % self.st.entry.choices().index(te.DONE))
        self.assertEqual(self.st.mode, station.SCAN)
        self.assertEqual(self.st.scan_text, "a")
        self.assertFalse(self.st.entry.view()["written"])
        self.nfc.cards.append(tag())
        self.st.step()                                  # written -> back to TEXT
        self.assertEqual(self.st.mode, station.TEXT)
        self.assertTrue(self.st.entry.view()["written"])
        run(self.st, self.inp, EXIT)                    # written: one hold leaves
        self.assertEqual(self.st.mode, station.HOME)

    def test_text_unwritten_needs_second_hold(self):
        run(self.st, self.inp, PREV, ACT, "tap:0")      # Text, 'a'
        run(self.st, self.inp, EXIT)
        self.assertEqual(self.st.mode, station.TEXT)
        self.assertEqual(self.st.entry.mode, te.M_CANCEL)
        run(self.st, self.inp, EXIT)                    # discard
        self.assertEqual(self.st.mode, station.HOME)

    def test_fast_turn_one_repaint(self):
        run(self.st, self.inp, PREV, ACT)               # Text
        before = sum(1 for c in self.ui.calls if c[0] == "show_keyboard")
        self.inp.q.extend([NEXT] * 5 + [PREV])
        self.st.step()
        after = sum(1 for c in self.ui.calls if c[0] == "show_keyboard")
        self.assertEqual(after - before, 1)
        self.assertEqual(self.st.entry.selected(), "e")  # +5 -1 from 'a'

    def test_fast_turn_in_list(self):
        run(self.st, self.inp, NEXT, ACT)               # Games
        self.inp.q.extend([NEXT] * 3)
        self.st.step()
        self.assertEqual(self.st.game_sel, 3)
        self.assertEqual(self.inp.q, [])

    def test_cancel_prompt_times_out(self):
        clock = [0]
        time.ticks_ms = lambda: clock[0]
        run(self.st, self.inp, PREV, ACT, "tap:0")      # Text, 'a'
        run(self.st, self.inp, EXIT)
        self.assertEqual(self.st.entry.mode, te.M_CANCEL)
        self.st.step()                                  # idle: timer starts
        clock[0] += station.CANCEL_PROMPT_MS - 1
        self.st.step()
        self.assertEqual(self.st.entry.mode, te.M_CANCEL)
        clock[0] += 1
        self.st.step()
        self.assertEqual(self.st.entry.mode, te.M_LETTERS)
        self.assertEqual(self.st.entry.text, "a")
        time.ticks_ms = lambda: int(time.monotonic() * 1000)

    def test_repl_command_stops_loop(self):
        self.st.dispatch({"cmd": "repl", "id": 9})
        self.assertFalse(self.st.running)
        self.assertEqual(self.link.sent[-1]["type"], "bye")

    def test_serial_catalog_and_write(self):
        self.st.dispatch({"cmd": "catalog.set", "id": 1,
                          "index": {"g": {"name": "G", "tags": ["x", "y"]}}})
        self.assertEqual(self.st.groups[0], ("G", ["x", "y"]))
        self.assertEqual(self.st.groups[-1][0], "Utilities")
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
        if name in ("get_width", "get_height"):
            return lambda: 17
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
        self.mod.RING_DIR = HERE            # generated kb_*.json lives in the tree

    def test_slot_at(self):
        slots = [(0, 10), (90, 10), (180, 10), (270, 10)]
        self.assertEqual(self.mod.slot_at(slots, 0, -97), 0)
        self.assertEqual(self.mod.slot_at(slots, 97, 0), 1)
        self.assertEqual(self.mod.slot_at(slots, -97, 0), 3)
        self.assertIsNone(self.mod.slot_at(slots, 0, 0))          # centre
        self.assertIsNone(self.mod.slot_at(slots, 60, -60 * 1.4)) # between

    def test_ring_json_matches_text_entry(self):
        import json
        with open(os.path.join(HERE, "kb_rings.json")) as f:
            rings = json.load(f)
        self.assertEqual(rings["letters"]["items"], list(te.LETTERS))
        self.assertEqual(sorted(rings), sorted(self.mod.IMAGE_RINGS))

    def _detent_calls(self):
        ui = self.mod.StationUI(FakeInputs())
        ui.begin()
        e = te.TextEntry(54)
        ui.show_keyboard(e.view())
        calls = []
        orig = (ui._color, ui._span, ui._kb_layout)
        ui._color = lambda lbl, c: calls.append("color")
        ui._span = lambda arc, a, b: calls.append("span")
        ui._kb_layout = lambda v: calls.append("layout")
        e.handle(NEXT)
        ui.show_keyboard(e.view())
        ui._color, ui._span, ui._kb_layout = orig
        return sorted(calls)

    def test_keyboard_detent_touches_few_widgets(self):
        # Image ring: just the cell moves (highlight label repositioned).
        self.assertEqual(self._detent_calls(), ["span"])
        self.mod.IMAGE_RING = False
        try:
            # Live labels: old and new label colour plus the cell.
            self.assertEqual(self._detent_calls(), ["color", "color", "span"])
        finally:
            self.mod.IMAGE_RING = True

    def test_cancel_prompt_does_not_relayout(self):
        ui = self.mod.StationUI(FakeInputs())
        ui.begin()
        e = te.TextEntry(54, text="ab")
        ui.show_keyboard(e.view())
        layouts = []
        orig = ui._kb_layout
        ui._kb_layout = lambda v: (layouts.append(v["mode"]), orig(v))
        e.handle(EXIT)                       # prompt
        ui.show_keyboard(e.view())
        e.handle(NEXT)                       # any intent: back to letters
        ui.show_keyboard(e.view())
        e.handle(EXIT)
        ui.show_keyboard(e.view())
        e.resume()                           # timeout path
        ui.show_keyboard(e.view())
        self.assertEqual(layouts, [])

    def test_hold_ring_late_and_stepped(self):
        ui = self.mod.StationUI(FakeInputs())
        ui.begin()
        spans = []
        ui._span = lambda arc, a, b: spans.append(b)
        for ms in range(0, 1001, 5):        # 5 ms loop over a 1 s hold
            ui.show_hold(ms / 1000)
        self.assertNotIn(True, [b < 0 for b in spans])
        self.assertLessEqual(len(spans), 360 // self.mod.HOLD_STEP + 1)
        spans.clear()
        for ms in range(0, 300, 5):         # a slow 300 ms click: no ring
            ui.show_hold(ms / 1000)
        self.assertEqual(spans, [])

    def test_lean_keyboard_flags(self):
        self.mod.SEG_TINTS, self.mod.CELL_DOT = False, True
        try:
            ui = self.mod.StationUI(FakeInputs())
            ui.begin()
            self.assertEqual(ui.k_segs, [])
            e = te.TextEntry(54, words=["w"])
            ui.show_keyboard(e.view())
            for _ in range(31):
                e.handle(NEXT)
                ui.show_keyboard(e.view())
            e.handle("tap:%d" % e.choices().index(te.MORE_ITEM))
            ui.show_keyboard(e.view())
        finally:
            self.mod.SEG_TINTS, self.mod.CELL_DOT = True, False

    def test_painters(self):
        ui = self.mod.StationUI(FakeInputs())
        ui.begin()
        ui.show_ring(["Read", "Tags", "Text"], 2)
        ui.show_list("Games", ["a"], 0)
        ui.show_list("Games", ["a", "b", "c"], 2)
        ui.show_reader(None, read=False)
        ui.show_reader("melody")
        ui.show_reader(None)
        ui.show_scan("stop")
        for kind in self.mod.KIND_STYLE:
            ui.show_result(kind, "T", "b")
        e = te.TextEntry(54, words=["melody"], text="x" * 20)
        ui.show_keyboard(e.view())
        for _ in range(29):
            e.handle(NEXT)
            ui.show_keyboard(e.view())
        e.handle("tap:%d" % e.choices().index(te.MORE_ITEM))
        ui.show_keyboard(e.view())
        e.handle("tap:%d" % e.choices().index(te.WORDS_ITEM))
        ui.show_keyboard(e.view())
        e.handle(EXIT)
        e.handle(EXIT)
        self.assertEqual(e.mode, te.M_CANCEL)
        ui.show_keyboard(e.view())
        ui.show_list("Games", ["g%d" % i for i in range(20)], 19)
        ui.beep_success()
        ui.beep_fail()
        for f in (None, 0.1, 0.5, 1.0, None):
            ui.show_hold(f)
        ui.tick()

    # Montserrat Medium advance widths at 28 px, measured from the Google
    # Fonts variable TTF at wght 500 (LVGL's built-ins are Medium). Icons
    # (backspace, ok) assumed 28 px.
    MONT28 = {"a": 16.7, "b": 19.1, "c": 16.0, "d": 19.1, "e": 17.1, "f": 9.9,
              "g": 19.3, "h": 19.1, "i": 7.8, "j": 8.0, "k": 17.2, "l": 7.8,
              "m": 29.6, "n": 19.1, "o": 17.8, "p": 19.1, "q": 19.1, "r": 11.5,
              "s": 14.0, "t": 11.6, "u": 19.0, "v": 15.7, "w": 25.2, "x": 15.5,
              "y": 15.7, "z": 14.6, "_": 14.0, "#": 19.7,
              "0": 18.7, "1": 10.4, "2": 16.1, "3": 16.0, "4": 18.7, "5": 16.1,
              "6": 17.3, "7": 16.7, "8": 18.0, "9": 17.3, "-": 10.7, ".": 6.4}
    ICON_W = 28

    def _widths(self, choices):
        out = []
        for c in choices:
            key = "_" if c == te.SPACE else c
            out.append(self.MONT28.get(key, self.ICON_W))
        return out

    def _assert_no_overlap(self, widths, radius):
        slots = self.mod.slot_angles(widths, radius)
        circ = 2 * math.pi * radius
        for i, (c, half) in enumerate(slots):
            arc_px = 2 * half * circ / 360
            self.assertGreaterEqual(arc_px, widths[i] + 2)
        total = sum(2 * h for _, h in slots)
        self.assertAlmostEqual(total, 360, places=3)

    def test_letters_ring_fits_at_28px(self):
        widths = self._widths(te.LETTERS)
        self._assert_no_overlap(widths, self.mod.KEY_R)
        # Uniform pitch would not: l-m-n needs 24.4 px, pitch is 20.3 px.
        pitch = 2 * math.pi * self.mod.KEY_R / len(widths)
        self.assertLess(pitch, (self.MONT28["m"] + self.MONT28["n"]) / 2)

    def test_more_ring_fits_at_28px(self):
        e = te.TextEntry(54, words=["w"])
        e.handle("tap:%d" % e.choices().index(te.MORE_ITEM))
        self._assert_no_overlap(self._widths(e.choices()), self.mod.KEY_R)

    def test_rim_rotation_bottoms_face_centre(self):
        for deg in range(0, 360, 5):
            r = self.mod.rim_rotation(deg)
            self.assertTrue(-180 < r <= 180, (deg, r))
            self.assertEqual((r - deg) % 360, 0)
        self.assertEqual(self.mod.rim_rotation(180), 180)
        self.assertEqual(self.mod.rim_rotation(270), -90)

    def test_span_full_ring_not_empty(self):
        calls = []

        class Arc:
            def set_angles(self, a, b):
                calls.append((a, b))

        self.mod.StationUI._span(Arc(), 0, 360)
        self.mod.StationUI._span(Arc(), -10, 20)
        self.assertEqual(calls, [(0, 360), (350, 20)])

    def test_slot_angles_refuses_overflow(self):
        with self.assertRaises(ValueError):
            self.mod.slot_angles([30] * 40, 97)


if __name__ == "__main__":
    unittest.main()
