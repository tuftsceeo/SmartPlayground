"""Exercise the Dial's WRITE menu logic with the hardware stubbed out.

Peer of BBoxFirmware/tools/box_menu_check.py, which caught two real
regressions on the Box. The menu, the sidecar reader and the row
truncation are all pure logic sitting behind an LVGL screen we cannot see
from a dev machine; this drives them directly so a regression shows up
here instead of on a teacher's Dial.

Run from anywhere:  python3 BDialFirmware/tools/dial_menu_check.py
Exits non-zero on any mismatch. It does NOT touch hardware.

Covers what the Box's version cannot: the Dial-only READ_ENTRY sentinel
in the utility group, and dial_ui._display_tag(). NOT covered here --
the row assembly inside paint_tag_group() needs live LVGL widgets, so
the "< Back" substitution and the "(%d)" written-count suffix are only
exercised by dial_ui.demo() on a real device.
"""
import sys, types, json, os, tempfile

BD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BD)


# --- minimal MicroPython / M5 / LVGL stubs ----------------------------
class _Any:
    """Absorbs any attribute chain or call.

    dial_ui.py evaluates real LVGL constants at import time -- notably
    `align=lv.ALIGN.TOP_MID` as a default argument, which runs when the
    class body is defined. A plain empty module would AttributeError
    there, so every stubbed name resolves to another _Any instead.
    """
    def __getattr__(self, name):
        return _Any()

    def __call__(self, *a, **k):
        return _Any()


for name in ("M5", "machine", "network", "espnow", "m5ui", "lvgl",
             "hardware", "unit"):
    m = types.ModuleType(name)
    m.__getattr__ = lambda n: _Any()      # module-level attribute fallback
    sys.modules[name] = m

# Module __getattr__ is not honoured on every MicroPython/CPython path, so
# also plant the attributes dial_ui/dial_input reach for by name.
for attr in ("ALIGN", "SYMBOL", "PART", "EVENT", "TEXT_ALIGN", "ANIM",
             "obj", "roller", "color_hex", "font_montserrat_14",
             "font_montserrat_16", "font_montserrat_24"):
    setattr(sys.modules["lvgl"], attr, _Any())
for attr in ("M5Page", "M5Label", "M5Button", "M5Roller", "init", "deinit"):
    setattr(sys.modules["m5ui"], attr, _Any())
sys.modules["M5"].Lcd = _Any()
sys.modules["M5"].Speaker = _Any()
sys.modules["M5"].begin = _Any()
sys.modules["M5"].update = _Any()
sys.modules["hardware"].Rotary = _Any()

import time as _t
_t.ticks_ms = lambda: int(_t.time() * 1000)
_t.sleep_ms = lambda ms: None
_t.ticks_diff = lambda a, b: a - b

import bdial_server as BS


class FakeUI:
    def __init__(self): self.screen = None
    def __getattr__(self, n):
        def f(*a, **k):
            if n.startswith("paint_"): self.screen = (n, a)
        return f


srv = BS.BdialServer.__new__(BS.BdialServer)
srv.ui = FakeUI()
srv._written = {"note_c": 3}
srv._mode = BS.MODE_WRITE
srv._write_state = BS.W_MENU
srv._cursor = 0
srv._group_cursor = 0
srv._groups = []
srv._entries = []
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
# Dial-only: the utility group carries a Read Card sentinel the Box has no
# equivalent for. _scan_step() special-cases it before it is ever treated
# as NDEF text, so it must stay in the row list but never be written.
check("utility group has Read Card", srv._groups[2],
      ("Utility Tags", ["stop", "battery", "Read Card"]))
check("written pruned to live labels", srv._written, {"note_c": 3})

# DONE is one press past the last group no matter how many tags exist.
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

# The scan/write states act on the tag, not the group title.
for st in (BS.W_SCAN, BS.W_SPLASH):
    srv._write_state = st
    check("current entry in %s" % st, srv._current_entry(), "note_c")

# Utility group is reachable and writable with no games loaded.
srv._index = {}
srv._rebuild_entries()
check("no games: rows", srv._entries, ["Games", "Utility Tags", "DONE"])
check("no games: utility still there", srv._groups[-1][1],
      ["stop", "battery", "Read Card"])

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

# --- dial_ui pure helpers --------------------------------------------
# The roller does not clip, so an over-long row would run off the panel.
# _fit() keeps the START of the text (the meaningful "getcode:" prefix)
# and appends ELLIPSIS -- see dial_ui._fit()'s docstring for why this
# replaced an earlier keep-both-ends scheme (reported on the Box's
# hardware as cutting the prefix past legibility).
import importlib.util
_spec = importlib.util.spec_from_file_location("dial_ui", BD + "/dial_ui.py")
ui = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ui)

check("short row untouched",
      ui._fit("note_c (3)", ui.ROW_CHARS), "note_c (3)")

budget = ui.ROW_CHARS
long_row = "getcode:a_very_long_melody_name_here"
got = ui._fit(long_row, budget)
expected = long_row[:budget - len(ui.ELLIPSIS)] + ui.ELLIPSIS
check("over-long row capped to budget", len(got), budget)
check("over-long row keeps the start, ellipsis at the end", got, expected)

# _display_tag capitalises the first letter ONLY. The rest of the string
# must survive byte-for-byte: it is what gets written to the NFC card, and
# the wand matches by exact set membership.
check("display tag capitalises first letter", ui._display_tag("note_c"), "Note_c")
check("display tag keeps colon and underscores",
      ui._display_tag("getcode:my_melody"), "Getcode:my_melody")
check("display tag leaves an already-capital name alone",
      ui._display_tag("Melody"), "Melody")
check("display tag on empty string", ui._display_tag(""), "")

print("\n%s" % ("all dial checks passed" if not fail else "%d FAILURES" % fail))
sys.exit(1 if fail else 0)
