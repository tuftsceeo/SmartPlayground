"""Minimal color-LCD UI for the StickS3 Narrator.

No touch, no buttons -- this device only displays what it just said, as
large as will fit (one line or two), in a color matched to what the wand's
LED matrix is actually showing (see phrases.py's GAME_ICON_COLORS /
FREEZE_DANCE_CALL_COLORS for the per-tag audit). Deliberately secondary:
for a vision-impaired user the speaker is the real output; the screen is
for a sighted helper/teacher glancing over to confirm what's playing.

Runs in LANDSCAPE, not StickS3's native portrait orientation, so game names
get the full 240px width to work with instead of 135px.
NOT YET BENCH-VERIFIED which of setRotation(1)/(3) is right-side-up for how
this device ends up worn/clipped -- see README.md.

## Font size + line layout

_LAYOUT_TABLE below is pasted straight from assets/_simulate_text_fit.py's
output -- for every label the Narrator can currently show, it picks the
largest of the firmware's fixed DejaVu bitmap sizes (9/12/18/24/40/56/72)
that fits, splitting two/three-word labels across two lines when that fits
a strictly bigger font than cramming everything onto one line (e.g. "Go" is
72pt; "Freeze Dance" is two lines of 40pt rather than a much smaller single
line). It's measured against a real DejaVu Sans TTF via Pillow, not a flat
"N characters * some average width" guess -- see that script's docstring
for why, and its 10% safety margin for why the fits aren't pushed to 100%
of the screen width.

That's still an approximation of the firmware's own bitmap-font rasterizer,
not a live on-device measurement (unconfirmed API: some LovyanGFX-family
displays expose `M5.Lcd.textWidth()`, which would be a real measurement,
but this hasn't been confirmed to exist on StickS3's UIFlow2 build -- if it
does, swapping it in would remove the need for this pre-baked table
entirely). If a label isn't in the table (e.g. a new game added after this
table was generated), `_fallback_layout` estimates a single-line size from
a rough per-character width instead of crashing -- re-run
assets/_simulate_text_fit.py and paste a fresh _LAYOUT_TABLE when that
happens, rather than leaving new labels on the rough estimate long-term.

## Positioning: plain setCursor()+print(), not setTextDatum()/drawString()

An earlier version tried `M5.Lcd.setTextDatum(M5.Lcd.Datum.middle_center)` +
`drawString()` to center text, with a same-firmware fallback to a fixed
`setCursor` guess if that raised. On real hardware, `setTextDatum` DID
raise (the `Datum` enum evidently isn't what was assumed here), which
silently dropped rendering into that fallback -- and the fallback used a
single hardcoded y that assumed a small single-line font, so anything
rendered at 40-72pt landed low on the screen with a large empty gap above
it, and a two-line layout got collapsed into one joined line at the wrong
position entirely.

Rather than add a second guess on top of a wrong one, positioning is now
plain `setCursor(x, y)` + `print(line)` -- the same primitive
`../M5Paper Remote/ui.py`'s `_draw_text_left` already relies on for
non-centered text, with no special datum/enum dependency at all. `x` is
computed per line from `_LAYOUT_TABLE`'s pre-measured pixel widths (real
horizontal centering via arithmetic, not an on-device text-measurement
call); `y` stacks lines downward from a block that's vertically centered
using the known font_size, top-anchored (matching how `setCursor`+`print`
positions text elsewhere in this repo's M5GFX-based UIs).
"""

import M5
from M5 import *

from phrases import color_for_tag, label_for_tag

WHITE = 0xFFFFFF
BLACK = 0x000000
BLUE = 0x2060FF

# Landscape: StickS3's native panel is 135x240 (portrait); rotated 90
# degrees these swap. If text renders upside-down or mirrored on real
# hardware, change ROTATION to 3 instead of 1 -- both are "landscape", they
# just differ on which physical edge is "up".
ROTATION = 1
SCREEN_W = 240
SCREEN_H = 135

MARGIN = 10
LINE_GAP = 4
_DEJAVU_NAMES = {
    9: "DejaVu9", 12: "DejaVu12", 18: "DejaVu18", 24: "DejaVu24",
    40: "DejaVu40", 56: "DejaVu56", 72: "DejaVu72",
}
# Largest first -- _fallback_layout tries each until one fits.
_FONT_CANDIDATES = (72, 56, 40, 24, 18, 12, 9)
# Rough average glyph width as a fraction of point size -- only used for a
# label that isn't in _LAYOUT_TABLE; see that table's generator for the
# real per-glyph measurement used everywhere else.
_CHAR_WIDTH_FACTOR = 0.62

# Pasted from `python assets/_simulate_text_fit.py` -- see this file's
# docstring. Keys are the exact rendered label text (from phrases.py's
# label_for_tag). Values are (font_size, ((line1, pixel_width), ...)) --
# one or two (text, width) pairs; the width lets us center each line with
# plain arithmetic instead of an on-device text-measurement call.
_LAYOUT_TABLE = {
    'Narrator ready': (40, (('Narrator', 169), ('ready', 115))),
    'Stopped': (40, (('Stopped', 165),)),
    'Color Quest': (40, (('Color', 104), ('Quest', 118))),
    'Freeze Dance': (40, (('Freeze', 135), ('Dance', 128))),
    'Jump In': (40, (('Jump In', 154),)),
    'Cooking': (40, (('Cooking', 160),)),
    'Melody': (40, (('Melody', 144),)),
    'Shake Fill': (40, (('Shake Fill', 192),)),
    'Shake Rainbow': (40, (('Shake', 123), ('Rainbow', 171))),
    'Rainbow': (40, (('Rainbow', 171),)),
    'Jump Counter': (40, (('Jump', 104), ('Counter', 160))),
    'Bell Choir': (40, (('Bell Choir', 192),)),
    'NFC Bell Choir': (40, (('NFC', 81), ('Bell Choir', 192))),
    'Ice Cream': (40, (('Ice', 59), ('Cream', 133))),
    'Multi Ice Cream': (40, (('Multi Ice', 170), ('Cream', 133))),
    'Gestures': (40, (('Gestures', 180),)),
    'Go': (72, (('Go', 100),)),
    'Freeze': (56, (('Freeze', 186),)),
    'Dance': (56, (('Dance', 178),)),
    'Ready': (56, (('Ready', 176),)),
    'Listening...': (24, (('Listening...', 133),)),
}


def _set_font(size):
    name = _DEJAVU_NAMES.get(size)
    font = getattr(M5.Lcd.FONTS, name, None) if name else None
    if font is not None:
        try:
            M5.Lcd.setFont(font)
            return
        except Exception:
            pass
    try:
        M5.Lcd.setTextSize(2)
    except Exception:
        pass


def _fallback_layout(text):
    """Single-line rough estimate for a label _LAYOUT_TABLE doesn't have.
    No known pixel width for this text, so _draw_lines left-aligns it
    instead of guessing a center point."""
    max_width = SCREEN_W - 2 * MARGIN
    for size in _FONT_CANDIDATES:
        if len(text) * size * _CHAR_WIDTH_FACTOR <= max_width:
            return size, ((text, None),)
    return _FONT_CANDIDATES[-1], ((text, None),)


def _layout_for(text):
    return _LAYOUT_TABLE.get(text) or _fallback_layout(text)


def _draw_lines(line_widths, font_size, bg, fg):
    """line_widths: ((text, pixel_width_or_None), ...). Plain
    setCursor()+print() -- see this file's docstring for why, instead of
    setTextDatum()/drawString()."""
    try:
        M5.Lcd.startWrite()
    except Exception:
        pass
    try:
        M5.Lcd.fillScreen(bg)
        _set_font(font_size)
        try:
            M5.Lcd.setTextColor(fg, bg)
        except Exception:
            pass
        n = len(line_widths)
        total_h = n * font_size + (n - 1) * LINE_GAP
        y = SCREEN_H // 2 - total_h // 2
        if y < 0:
            y = 0
        for text, width in line_widths:
            x = MARGIN if width is None else max(MARGIN, (SCREEN_W - width) // 2)
            try:
                M5.Lcd.setCursor(x, y)
                M5.Lcd.print(text)
            except Exception:
                pass
            y += font_size + LINE_GAP
    finally:
        try:
            M5.Lcd.endWrite()
        except Exception:
            pass


def _draw_centered(text, bg, fg=None):
    if fg is None:
        fg = WHITE if bg != WHITE else BLACK
    font_size, line_widths = _layout_for(text)
    _draw_lines(line_widths, font_size, bg, fg)


class NarratorUI(object):
    def __init__(self):
        try:
            M5.Lcd.setRotation(ROTATION)
        except Exception as e:
            print("  setRotation err: %s" % str(e))

    def paint_idle(self):
        _draw_centered("Listening...", BLACK)

    def paint_game(self, tag):
        color = color_for_tag(tag)
        # A matched icon color becomes the background (bold, matches the
        # matrix) with black text for contrast; no match falls back to the
        # original white-on-blue treatment.
        if color is not None:
            _draw_centered(label_for_tag(tag), color, fg=BLACK)
        else:
            _draw_centered(label_for_tag(tag), BLUE)
