"""station_fonts.py -- resolve the NFC Station's large fonts.

Sizes: BODY 28 px (the minimum anywhere on screen -- 2x the Dial's 14 px
small text), FOCUS 40 px (selected item, titles), GLYPH 48 px.

Each size comes from the LVGL build's built-in Montserrat if present,
otherwise from /flash/fonts/montserrat_<size>.bin. A required size with
neither source raises -- the UI must not quietly fall back to small text.
"""

import os

import lvgl as lv

BODY = 28
FOCUS = 40
GLYPH = 48
BIN_DIR = "/flash/fonts"


def builtin(size):
    """lv.font_montserrat_<size>, or None if the build does not ship it."""
    return getattr(lv, "font_montserrat_%d" % size, None)


def binfont(size):
    """Load /flash/fonts/montserrat_<size>.bin, or None if absent.

    A file that exists but fails to load raises: that is a broken asset,
    not a missing one.
    """
    name = "montserrat_%d.bin" % size
    try:
        files = os.listdir(BIN_DIR)
    except OSError:
        return None
    if name not in files:
        return None
    path = "S:%s/%s" % (BIN_DIR, name)
    # LVGL 9: binfont_create; LVGL 8: font_load. Neither -> this build
    # cannot load binary fonts at all, which must be a crash.
    loader = getattr(lv, "binfont_create", None) or getattr(lv, "font_load", None)
    if loader is None:
        raise RuntimeError("no binary font loader in this LVGL build")
    font = loader(path)
    if font is None:
        raise RuntimeError("font loader returned None for %s (LVGL drive "
                           "letter or path wrong?)" % path)
    return font


def find(size):
    """(font, source) for a size, or (None, None)."""
    font = builtin(size)
    if font is not None:
        return font, "builtin"
    font = binfont(size)
    if font is not None:
        return font, "binfont"
    return None, None


def require(size):
    """The font for a size; raises RuntimeError if unavailable."""
    font, _ = find(size)
    if font is None:
        raise RuntimeError(
            "font montserrat_%d unavailable: no builtin and no %s/montserrat_%d.bin"
            % (size, BIN_DIR, size))
    return font
