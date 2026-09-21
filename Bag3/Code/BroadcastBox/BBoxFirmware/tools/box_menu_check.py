"""Exercise the Box's WRITE menu logic with the hardware stubbed out.

The menu, the sidecar reader and the row truncation are all pure logic sitting
behind an M5 screen we cannot see from a dev machine. This drives them
directly so a regression shows up here instead of on a teacher's Box.

Run from anywhere:  python3 BBoxFirmware/tools/box_menu_check.py
Exits non-zero on any mismatch. It does NOT touch hardware.
"""
import sys, types, json, os, tempfile

BB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BB)

# --- minimal MicroPython / M5 stubs -----------------------------------
for name in ("M5", "machine", "network", "espnow"):
    m = types.ModuleType(name)
    sys.modules[name] = m
sys.modules["M5"].Lcd = types.SimpleNamespace()
sys.modules["M5"].Speaker = types.SimpleNamespace()
import time as _t
_t.ticks_ms = lambda: int(_t.time() * 1000)
_t.sleep_ms = lambda ms: None
_t.ticks_diff = lambda a, b: a - b

import bbox_server as BS

class FakeUI:
    def __init__(self): self.screen = None; self.kwargs = None
    def __getattr__(self, n):
        def f(*a, **k):
            if n.startswith("paint_"):
                self.screen = (n, a)
                self.kwargs = k
        return f

srv = BS.BboxServer.__new__(BS.BboxServer)
srv.ui = FakeUI()
srv._written = {"note_c": 3}
srv._mode = BS.MODE_WRITE
srv._write_state = BS.W_MENU
srv._cursor = 0
srv._group_cursor = 0
srv._groups = []
srv._entries = []
srv._reader_last_uid = None
srv.nfc = None
srv._index = {
    "my_melody": {"name": "My Melody", "tags":
        ["note_c","note_d","note_e","note_f","note_g","note_a","note_b",
         "note_c_high","erase","melody","backspace"]},
    "my_jump": {"name": "My Jump", "tags": []},
}
srv._rebuild_entries()

fail = 0
def check(label, got, want):
    global fail
    ok = got == want
    if not ok: fail += 1
    print(("ok   " if ok else "FAIL ") + label)
    if not ok:
        print("      got  %r" % (got,))
        print("      want %r" % (want,))

check("top level rows", srv._entries, ["My Melody", "My Jump", "Utility Tags", "DONE"])
check("melody group", srv._groups[0][1],
      ["getcode:my_melody", "my_melody", "note_c", "note_d", "note_e", "note_f",
       "note_g", "note_a", "note_b", "note_c_high", "erase", "melody", "backspace"])
check("jump group", srv._groups[1][1], ["getcode:my_jump", "my_jump"])
check("utility group", srv._groups[2],
      ("Utility Tags", ["stop", "battery", "Read Card"]))
check("written pruned to live labels", srv._written, {"note_c": 3})

# DONE is two presses from the top no matter how many tags exist.
presses = srv._entries.index("DONE")
check("presses to reach DONE from row 0", presses, 3)

# Enter the melody group and check the rows the screen would show.
srv._cursor = 0
srv._group_cursor = 0
srv._write_state = BS.W_GROUP
check("group rows end with back", srv._group_rows()[-1], "< back")
check("current entry inside group", srv._current_entry(), "getcode:my_melody")
srv._group_cursor = 2
check("current entry after 2 next", srv._current_entry(), "note_c")

# The scan/write states act on the tag, not the group title. (No
# W_OVERWRITE anymore -- a card holding different text is overwritten
# the same as a blank one, with no confirmation state in between.)
for st in (BS.W_SCAN, BS.W_SPLASH):
    srv._write_state = st
    check("current entry in %s" % st, srv._current_entry(), "note_c")

# Utility group is reachable and writable with no games loaded.
srv._index = {}
srv._rebuild_entries()
check("no games: rows", srv._entries, ["Games", "Utility Tags", "DONE"])
check("no games: utility still there", srv._groups[-1][1],
      ["stop", "battery", "Read Card"])

# READ_ENTRY ("NFC Reader" utility) debounce inside _scan_step(): stays in
# W_SCAN across reads (never advances to W_SPLASH like a write does), so it
# needs its own guard against re-reporting a card that's just sitting on
# the reader across repeated polls.
class FakeNfc:
    def __init__(self):
        self.next_tag = None
    def detect_tag(self, timeout=80):
        return self.next_tag
    def stop_crypto1(self):
        pass


class _FakeReaderLink:
    def __init__(self): self.sent = {}
    def send(self, obj): self.sent.clear(); self.sent.update(obj)


srv._cursor = srv._entries.index("Utility Tags")
srv._write_state = BS.W_GROUP
srv._group_cursor = srv._group_rows().index(BS.READ_ENTRY)
check("cursor lands on Read Card", srv._current_entry(), BS.READ_ENTRY)

# The action button must say READ, not WRITE, on the Read Card row --
# _repaint() is what decides this (read_only=True only for READ_ENTRY).
srv._repaint()
check("Read Card row paints read_only=True", srv.ui.kwargs.get("read_only"), True)
srv._group_cursor = srv._group_rows().index("stop")
srv._repaint()
check("a real write row paints read_only=False", srv.ui.kwargs.get("read_only"), False)
srv._group_cursor = srv._group_rows().index(BS.READ_ENTRY)  # leave it as found

srv.nfc = FakeNfc()
flink = _FakeReaderLink()
srv.link = flink
BS.existing_text = lambda nfc, tag: "hello"
tag_a = {"uid_hex": "AA", "sak": 0, "tag_type": "ntag"}
tag_b = {"uid_hex": "BB", "sak": 0, "tag_type": "ntag"}

srv.nfc.next_tag = tag_a
srv._scan_step()
check("reader: first read reports the card", flink.sent.get("uid"), "AA")
check("reader: last-seen uid latched", srv._reader_last_uid, "AA")

flink.sent.clear()
srv._scan_step()  # same card, still resting on the reader
check("reader: card still resting does not re-report", flink.sent, {})

srv.nfc.next_tag = None
srv._scan_step()  # lifted
check("reader: lifting the card clears the debounce", srv._reader_last_uid, None)

srv.nfc.next_tag = tag_a
srv._scan_step()  # same card set back down
check("reader: same card replaced re-reports", flink.sent.get("uid"), "AA")

flink.sent.clear()
srv.nfc.next_tag = tag_b
srv._scan_step()  # a different card, without ever reading "None" between
check("reader: a different card reports without needing removal first",
      flink.sent.get("uid"), "BB")

# Sidecar reading.
d = tempfile.mkdtemp()
BS.GAMES_DIR = d
open(d + "/g.tags.json", "w").write('["note_c", "erase"]')
check("sidecar parsed", srv._read_tags("g"), ["note_c", "erase"])
check("sidecar absent -> []", srv._read_tags("nope"), [])
open(d + "/bad.tags.json", "w").write("{not json")
check("sidecar unparseable -> [] (and prints)", srv._read_tags("bad"), [])
open(d + "/obj.tags.json", "w").write('{"a": 1}')
check("sidecar wrong type -> []", srv._read_tags("obj"), [])

# games.list must carry each game's tags, or the app falls back to showing
# only the baseline pair for a game this laptop never sent.
sent = {}
class FakeLink:
    def send(self, obj): sent.clear(); sent.update(obj)
srv.link = FakeLink()
srv._active = "my_melody"
srv._index = {"my_melody": {"name": "My Melody", "tags": ["note_c", "erase"]},
              "plain": {"name": "Plain"}}
BS.GAMES_DIR = "/nonexistent"   # sizes fall back to 0; we only inspect shape
srv.do_games_list({}, 1)
rows = {r["slug"]: r for r in sent.get("list", [])}
check("games.list carries tags", rows["my_melody"]["tags"], ["note_c", "erase"])
check("games.list tags default to []", rows["plain"]["tags"], [])

# Row truncation: the screen does not clip, so an over-long row would run
# off the panel. _fit() keeps the START of the text (the meaningful
# "getcode:" prefix) and appends ELLIPSIS -- see bbox_ui._fit()'s
# docstring for why this replaced an earlier keep-both-ends scheme
# (reported on hardware as cutting the prefix past legibility).
import importlib.util, types as _types
sys.modules.setdefault("M5", _types.ModuleType("M5"))
_spec = importlib.util.spec_from_file_location("bbox_ui", BB + "/bbox_ui.py")
ui = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ui)

check("short row untouched",
      ui._fit("note_c (3)", ui.ROW_CHARS), "note_c (3)")

budget = ui.ROW_CHARS
long_row = "getcode:a_very_long_melody_name_here"
got = ui._fit(long_row, budget)
expected = long_row[:budget - len(ui.ELLIPSIS)] + ui.ELLIPSIS
check("over-long row capped to budget", len(got), budget)
check("over-long row keeps the start, ellipsis at the end", got, expected)

# --- card_writer._decode_ndef_text: Text AND URI records ---------------
# This file only ever WRITES Text ('T') records, but some tags already in
# circulation (from Bag1/Bag2, or a generic NFC writer app) carry a URI
# ('U') record instead -- Bag2's own decoder always read both. Regression
# test for the URI branch specifically, since it was silently dropped from
# this ported copy at some point and only caught by comparing against
# Bag2/Code/lib/nfc_reader.py's decoder.
import card_writer as CW


def _build_ndef_uri(uri, prefix_code=0):
    """Hand-build a TLV+NDEF URI record -- mirrors build_ndef_text()'s
    Text-record shape but with type 'U' and a URI abbreviation code byte
    in place of the language-code byte."""
    payload = bytes([prefix_code]) + uri.encode('utf-8')
    flags = 0xD1  # MB|ME|SR, TNF=0x01 (well-known) -- same as a Text record
    rec_type = b'U'
    record = bytes([flags, len(rec_type), len(payload)]) + rec_type + payload
    return bytes([0x03, len(record)]) + record + bytes([0xFE])


check("decode: Text record still works",
      CW._decode_ndef_text(CW.build_ndef_text("note_c")), "note_c")
check("decode: URI record with a prefix code",
      CW._decode_ndef_text(_build_ndef_uri("example.com/g", prefix_code=3)),
      "http://example.com/g")
check("decode: URI record with no prefix (code 0)",
      CW._decode_ndef_text(_build_ndef_uri("getcode:my_melody", prefix_code=0)),
      "getcode:my_melody")

print("\n%s" % ("all box checks passed" if not fail else "%d FAILURES" % fail))
sys.exit(1 if fail else 0)
