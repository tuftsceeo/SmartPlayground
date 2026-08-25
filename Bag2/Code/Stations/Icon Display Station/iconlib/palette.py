"""
palette.py -- PC-side copy of lib/leds.py's base color palette (no _DIM
variants; brightness here comes from the segment's own proposed amplitude,
not a separate dim constant). This intentionally does NOT import leds.py
directly: leds.py pulls in `machine`/`neopixel`/`hubtype`, which only exist
on-device under MicroPython. Keep this list in sync by hand when leds.py's
base palette changes -- there's no way to share the source of truth across
the MicroPython/CPython boundary without adding a device-side dependency
on a PC tool.
"""

PALETTE = {
    "RED": (130, 0, 0), "ROSE": (120, 10, 20),
    "ORANGE": (120, 40, 0), "AMBER": (120, 80, 0), "YELLOW": (110, 120, 0),
    "LIME": (50, 210, 0), "GREEN": (0, 230, 0),
    "TEAL": (0, 180, 100), "CYAN": (0, 180, 240), "BLUE": (0, 20, 255),
    "INDIGO": (30, 0, 255), "PURPLE": (50, 0, 250), "MAGENTA": (120, 0, 160),
    "WHITE": (140, 150, 150), "PINK": (200, 80, 120), "PEACH": (180, 120, 30),
    "MINT": (30, 190, 50), "SKY": (60, 150, 250),
}

# Unit directions (max component normalized to 1.0) -- used for HUE-ONLY
# matching. Never compare raw PALETTE magnitudes to a source pixel; that's
# the v/pv amplification bug that blew out saturation in every earlier
# version of this tool.
PALETTE_DIRECTIONS = {
    name: tuple(c / max(rgb) if max(rgb) else 0 for c in rgb)
    for name, rgb in PALETTE.items()
}
