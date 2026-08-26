"""
Dev-only text-fit simulator for the StickS3 Narrator's landscape display.
============================================================================
NOT deployed to the device -- run this on a laptop to check, for every
label the Narrator can show, which of the firmware's fixed DejaVu bitmap
font sizes (9/12/18/24/40/56/72 -- see ../narrator_ui.py and
../../M5Paper Remote/ui.py's identical _DEJAVU_NAMES table) actually fits
the 240x135 landscape screen, on one line or split across two.

Measures real glyph widths with the actual DejaVu Sans TTF (bundled with
matplotlib on most machines) via Pillow, rather than a flat "N chars * some
average width" guess -- proportional fonts vary a lot per character ("I"
vs "M"), so that guess under- or over-estimates fit unpredictably. This is
still an approximation of the firmware's own bitmap-font metrics (a scaled
TTF measurement, not the actual on-device rasterizer), which is why
narrator_ui.py's runtime code prefers M5.Lcd.textWidth() when available and
only falls back to this simulator's numbers when it isn't -- see that
file's docstring.

    pip install pillow
    python _simulate_text_fit.py
"""

import os
import sys

from PIL import ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from phrases import FREEZE_DANCE_LABELS, GAME_LABELS, SPECIAL_LABELS  # noqa: E402

# Matches narrator_ui.py's ROTATION=1 landscape screen.
SCREEN_W = 240
SCREEN_H = 135
MARGIN = 10
# This measures a TTF approximation of the firmware's own fixed bitmap
# fonts, not the real on-device rasterizer -- pull in some slack so a small
# metrics mismatch (bitmap font slightly wider than the TTF proxy at the
# same nominal size) doesn't clip text at the screen edge on real hardware.
SAFETY = 0.90
MAX_W = int((SCREEN_W - 2 * MARGIN) * SAFETY)
MAX_H = SCREEN_H - 2 * MARGIN
LINE_GAP = 4

# The firmware's actual fixed bitmap sizes (see _DEJAVU_NAMES in both
# narrator_ui.py and ../M5Paper Remote/ui.py) -- NOT arbitrary point sizes.
FONT_SIZES = (72, 56, 40, 24, 18, 12, 9)

# Bundled with matplotlib; same family the on-device "DejaVuNN" fonts are
# named after. Regular weight -- M5Stack's UIFlow2 DejaVu fonts are regular,
# not bold.
_CANDIDATE_TTF_PATHS = []
try:
    import matplotlib

    _CANDIDATE_TTF_PATHS.append(
        os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf", "DejaVuSans.ttf")
    )
except ImportError:
    pass
_CANDIDATE_TTF_PATHS += [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:\\Windows\\Fonts\\DejaVuSans.ttf",
]

_FONT_CACHE = {}


def _font(size):
    if size not in _FONT_CACHE:
        path = next((p for p in _CANDIDATE_TTF_PATHS if os.path.isfile(p)), None)
        if path is None:
            raise SystemExit(
                "Couldn't find DejaVuSans.ttf. Install matplotlib (`pip install matplotlib`) "
                "or point _CANDIDATE_TTF_PATHS at a copy."
            )
        _FONT_CACHE[size] = ImageFont.truetype(path, size)
    return _FONT_CACHE[size]


def text_width(text, size):
    bbox = _font(size).getbbox(text)
    return bbox[2] - bbox[0]


def best_single_line(text):
    """Largest font size (from FONT_SIZES) whose rendered width fits MAX_W,
    or the smallest size (even if it still overflows) as a last resort."""
    for size in FONT_SIZES:
        if text_width(text, size) <= MAX_W:
            return size
    return FONT_SIZES[-1]


def best_two_line(words):
    """Try every split point between `words`; for each candidate font size
    (largest first), a split "fits" if both resulting lines fit MAX_W and
    the stacked pair fits MAX_H. Returns (size, (line1, line2)) or None if
    there's nothing to split (single word) or nothing fits better than
    single-line."""
    if len(words) < 2:
        return None
    best = None  # (size, split)
    for i in range(1, len(words)):
        line1 = " ".join(words[:i])
        line2 = " ".join(words[i:])
        for size in FONT_SIZES:
            if 2 * size + LINE_GAP > MAX_H:
                continue
            if text_width(line1, size) <= MAX_W and text_width(line2, size) <= MAX_W:
                if best is None or size > best[0]:
                    best = (size, (line1, line2))
                break  # sizes are largest-first; first fit for this split is its best
    return best


def choose_layout(text):
    """Decide single-line vs two-line for `text`, preferring two-line only
    when it wins a strictly larger font size (not just a tie) -- otherwise
    a short single word would get split for no visual benefit."""
    words = text.split()
    single_size = best_single_line(text)
    two = best_two_line(words)
    if two is not None and two[0] > single_size:
        return two[0], two[1], text_width(two[1][0], two[0]), text_width(two[1][1], two[0])
    w = text_width(text, single_size)
    return single_size, (text,), w, None


def layout_with_widths(text):
    """(font_size, ((line, width), ...)) -- widths let narrator_ui.py
    center each line with plain setCursor()+print() arithmetic instead of
    a setTextDatum()/drawString() call that's turned out not to be reliable
    on real StickS3 hardware (see narrator_ui.py's docstring)."""
    size, lines, w1, w2 = choose_layout(text)
    if len(lines) == 1:
        return size, ((lines[0], w1),)
    return size, ((lines[0], w1), (lines[1], w2))


def main():
    all_labels = list(SPECIAL_LABELS.values()) + list(GAME_LABELS.values()) + list(FREEZE_DANCE_LABELS.values())
    true_max_w = SCREEN_W - 2 * MARGIN
    print(
        "Screen usable area: %dx%d (MARGIN=%d); fit budget after %.0f%% safety margin: %dpx wide\n"
        % (true_max_w, MAX_H, MARGIN, SAFETY * 100, MAX_W)
    )
    print("%-16s %-8s %-24s %s" % ("Label", "Size", "Layout", "Width used (of true 220px)"))
    print("-" * 78)
    for label in all_labels:
        size, lines, w1, w2 = choose_layout(label)
        layout_desc = " / ".join(lines)
        if len(lines) == 1:
            pct = 100.0 * w1 / true_max_w
            width_desc = "%dpx (%.0f%%)" % (w1, pct)
        else:
            pct = 100.0 * max(w1, w2) / true_max_w
            width_desc = "%dpx+%dpx (%.0f%% max)" % (w1, w2, pct)
        print("%-16s %-8d %-24s %s" % (label, size, layout_desc, width_desc))

    print("\n# Paste into narrator_ui.py's _LAYOUT_TABLE (see that file's docstring):")
    print("_LAYOUT_TABLE = {")
    for label in all_labels:
        size, line_widths = layout_with_widths(label)
        print("    %r: (%d, %r)," % (label, size, line_widths))
    print("}")


if __name__ == "__main__":
    main()
