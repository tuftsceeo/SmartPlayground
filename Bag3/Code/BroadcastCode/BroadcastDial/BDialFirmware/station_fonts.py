"""station_fonts.py -- the NFC Station's font sizes, from built-in fonts.

Sizes: BODY 28 px (the minimum anywhere on screen -- 2x the Dial's 14 px
small text), FOCUS 40 px (selected item, titles), GLYPH 48 px.

Only fonts compiled into the firmware are used (lv.font_montserrat_<n>);
nothing is loaded from flash. A size the build lacks falls back to the
largest built-in size below it, and the substitution is printed so it is
visible in the serial log -- the layout is then smaller than designed.
"""

import lvgl as lv

BODY = 28
FOCUS = 40
GLYPH = 48

# Montserrat sizes LVGL can be built with, largest first.
_SIZES = (48, 46, 44, 42, 40, 38, 36, 34, 32, 30, 28, 26, 24, 22, 20, 18, 16, 14)


def builtin(size):
    """lv.font_montserrat_<size>, or None if the build does not ship it."""
    return getattr(lv, "font_montserrat_%d" % size, None)


def find(size):
    """(font, actual_size) for the largest built-in size <= size."""
    for s in _SIZES:
        if s <= size:
            font = builtin(s)
            if font is not None:
                return font, s
    return None, None


def require(size):
    """Font for a size, substituting a smaller built-in one if needed.
    Raises RuntimeError if no Montserrat at or below size is built in."""
    font, actual = find(size)
    if font is None:
        raise RuntimeError("no built-in montserrat font at or below %d px" % size)
    if actual != size:
        print("# font: montserrat_%d not built in, using %d" % (size, actual))
    return font
