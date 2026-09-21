"""widget_test.py — bench diagnostic for two open bbox_ui.py questions.

Bench tool, not firmware -- not part of BOX_FILES / manifest.js. Run
from the REPL, from BBoxFirmware/:

  mpremote connect $PORT fs cp tools/widget_test.py :/flash/widget_test.py
  mpremote connect $PORT exec "import widget_test; widget_test.run()"

Answers two things bbox_ui.py currently guesses at rather than knows:

1. Glyph coverage (test_glyphs). bbox_ui.py used the Unicode ellipsis
   "…" (U+2026) and middle dot "·" (U+00B7); a game-name row was
   reported on hardware showing a blank/tofu box where a character
   should be. Both were swapped for plain ASCII ("...", "(%d)") on the
   assumption that an MCU-baked font subset carries ASCII but not
   necessarily anything past it. This stage shows a grid of candidate
   characters, each between "abc" and "xyz" so a missing glyph is easy
   to spot by position -- report which rows show a blank box in the
   middle instead of a real glyph.

2. Same-value redraw (test_repeat_no_reset / test_repeat_with_reset).
   Reported bug: a button showing "OPEN" would sometimes appear as a
   plain pink square with no text, including right after returning
   from the SERVE screen -- i.e. whenever the NEW label text happens to
   equal what the label already said last time. Theory: Label.setText()
   may skip its actual redraw when the string is unchanged from its
   last call, even though Widgets.fillScreen() has since wiped the
   pixels out from under it. bbox_ui.py's _set_text() now calls
   setText("") before the real text every time, forcing a genuine value
   change so the skip (if it exists) can never trigger. Stage 2
   reproduces the bug WITHOUT that fix (to confirm the theory); stage 3
   repeats it WITH the fix (to confirm the fix actually works). Report
   whether OPEN is visible at the end of 2b and at the end of 3b.
"""

import time

import M5
from M5 import *  # noqa: F401,F403 -- brings in `Widgets`

PAGE_BG = 0xF7F7FB
INK = 0x231F2E
PINK = 0xEF4D92

FONT12 = None
FONT16 = None


def _fonts():
    global FONT12, FONT16
    FONT12 = Widgets.FONTS.Montserrat12
    FONT16 = Widgets.FONTS.Montserrat16


def _pause(msg, seconds=5):
    print("### %s" % msg)
    time.sleep(seconds)


# Each candidate is (name, char). Printed as "abc<char>xyz" so a missing
# glyph -- a blank box -- is easy to place: it'll be the middle one.
CANDIDATES = [
    ("ellipsis U+2026", "…"),
    ("middle dot U+00B7", "·"),
    ("bullet U+2022", "•"),
    ("right arrow U+2192", "→"),
    ("left arrow U+2190", "←"),
    ("down triangle U+25BC", "▼"),
    ("multiplication x U+00D7", "×"),
    ("em dash U+2014", "—"),
    ("en dash U+2013", "–"),
    ("check mark U+2713", "✓"),
    ("degree sign U+00B0", "°"),
]


def test_glyphs():
    """Stage 1: one candidate character per row. Report which rows show
    a blank/empty box between "abc" and "xyz" instead of a real glyph."""
    Widgets.fillScreen(PAGE_BG)
    Widgets.Label("Stage 1: glyph coverage", 4, 4, 1.0, INK, PAGE_BG, FONT12)
    y = 24
    labels = []
    for name, ch in CANDIDATES:
        text = "abc%sxyz" % ch
        Widgets.Label(text, 4, y, 1.0, INK, PAGE_BG, FONT12)
        labels.append((name, y))
        y += 18
    print("### stage 1 rows top-to-bottom, in order:")
    for name, y in labels:
        print("    y=%d: %s" % (y, name))
    _pause("stage 1 -- report which y= rows show a blank box in the middle", 20)


def test_repeat_no_reset():
    """Stage 2: reproduce the bug WITHOUT the setText("") fix."""
    Widgets.fillScreen(PAGE_BG)
    Widgets.Label("Stage 2: repeat, no reset", 4, 4, 1.0, INK, PAGE_BG, FONT12)
    rect = Widgets.Rectangle(4, 100, 88, 26, PINK, PINK)
    label = Widgets.Label("OPEN", 14, 106, 1.0, 0xFFFFFF, PINK, FONT16)
    _pause("stage 2a -- pink card should say OPEN")
    Widgets.fillScreen(PAGE_BG)
    Widgets.Label("Stage 2: repeat, no reset", 4, 4, 1.0, INK, PAGE_BG, FONT12)
    rect.setColor(PINK, PINK)
    label.setText("OPEN")  # SAME text as before, no blank-first step
    _pause("stage 2b -- same repaint, NO fix -- does OPEN still show, or blank pink?")


def test_repeat_with_reset():
    """Stage 3: same scenario, WITH the setText("") fix bbox_ui.py now uses."""
    Widgets.fillScreen(PAGE_BG)
    Widgets.Label("Stage 3: repeat, with reset", 4, 4, 1.0, INK, PAGE_BG, FONT12)
    rect = Widgets.Rectangle(4, 100, 88, 26, PINK, PINK)
    label = Widgets.Label("OPEN", 14, 106, 1.0, 0xFFFFFF, PINK, FONT16)
    _pause("stage 3a -- pink card should say OPEN")
    Widgets.fillScreen(PAGE_BG)
    Widgets.Label("Stage 3: repeat, with reset", 4, 4, 1.0, INK, PAGE_BG, FONT12)
    rect.setColor(PINK, PINK)
    label.setText("")      # forces a real value change first
    label.setText("OPEN")  # then the real text -- this is bbox_ui.py's fix
    _pause("stage 3b -- same repaint, WITH the fix -- does OPEN show now?")


def run():
    M5.begin()
    Widgets.setRotation(0)
    _fonts()
    test_glyphs()
    test_repeat_no_reset()
    test_repeat_with_reset()
    print("### widget_test done. Report:")
    print("    1) which glyph rows (by y=) showed a blank box")
    print("    2) did stage 2b show OPEN, or a blank pink square?")
    print("    3) did stage 3b show OPEN?")
