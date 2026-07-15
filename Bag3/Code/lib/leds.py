"""
LED Helpers — NeoPixel control and status display  (Bag3 / 6×10 matrix)
========================================================================
Auto-configures from hubtype. Works on any device.

Bag3 difference vs Bag2
-----------------------
The wand's matrix is now 6 columns × 10 rows (60 LEDs) instead of the
old 5×5 (25 LEDs). LEDs are wired row-major:

        index = row * COLS + col          (COLS = 6)

so row 0 is indices 0..5 (left→right), row 1 is 6..11, etc. — the
strip runs one horizontal row at a time (same convention as the old
5×5, just 6 wide and 10 tall).

All the SHAPE_* glyphs below were redrawn natively for this taller grid
using a small ASCII-art helper (_art / _glyph). The public names are
unchanged so every game that imports them keeps working.

All LED writes pass through _ScaledNeoPixel, which multiplies every
(r, g, b) tuple by brightness.MULTIPLIER on its way to the underlying
NeoPixel. Code outside this file does not need to know — when
brightness.calibrate(opt) sets MULTIPLIER on boot, every consumer
automatically adapts.

Usage:
    from leds import Leds
    leds = Leds()           # auto from hubtype
    leds = Leds(pin=21, num=18)  # override

    leds.solid(200, 0, 0)   # red, scaled by brightness.MULTIPLIER
    leds.np[5] = (0, 200, 0)  # also scaled — wrapper intercepts
"""

import math
import time
from neopixel import NeoPixel as _RawNeoPixel
import machine

from hubtype import HUB_CONFIG
import brightness   # required — provides MULTIPLIER

TRIGGER_ORDER = ["buttondown", "buttonup", "whenshake"]

# ══════════════════════════════════════════════
# MATRIX GEOMETRY
# ══════════════════════════════════════════════
# Row-major: index = row * COLS + col. For the wand COLS=6, ROWS=10.
COLS = HUB_CONFIG.get("matrix_cols", 6)
ROWS = HUB_CONFIG.get("matrix_rows", 10)

# Characters that count as "lit" in ASCII-art shape definitions.
_LIT = "1#XO*@"


def _xy(col, row):
    """(col, row) -> strip index, row-major (row 0 = top, col 0 = left)."""
    return row * COLS + col


def _art(*rows):
    """
    Build a sorted index tuple from rows of ASCII art (row 0 = top).

    Each row is a string up to COLS wide; any char in _LIT lights that
    cell, anything else ('0', '.', ' ') leaves it dark. Rows/cols past
    the matrix bounds are ignored, so art can be written for the 6×10
    wand and simply clips on smaller devices.
    """
    idx = []
    for row, line in enumerate(rows):
        if row >= ROWS:
            break
        for col, ch in enumerate(line):
            if col >= COLS:
                break
            if ch in _LIT:
                idx.append(_xy(col, row))
    return tuple(sorted(idx))


def _glyph(*rows7):
    """Place a 7-row font glyph with a one-row top margin (rows 1..7)."""
    return _art("", *rows7)


# ══════════════════════════════════════════════
# COLOR PALETTE — outdoor-tuned, brightness module scales them
# ══════════════════════════════════════════════
# White at ~55% per channel so total current draw stays comparable to
# two-channel colors.
#
# BLUE is pushed harder because the blue NeoPixel die is the weakest of
# the three; a "balanced" 200 looks visibly darker than 200-red or 200-green.)
#
# Values were tuned by-eye against the actual hardware, not by sRGB math:
OFF      = (0, 0, 0)
BLACK      = (0, 0, 0)

RED      = (130, 0, 0)
ROSE     = (120, 10, 20)

ORANGE   = (120, 40, 0)
AMBER    = (120, 80, 0)
YELLOW   = (110, 120, 0)

LIME     = (50, 210, 0)
GREEN    = (0, 230, 0)

TEAL     = (0, 180, 100)
CYAN     = (0, 180, 240)
BLUE     = (0, 20, 255)

INDIGO   = (30, 0, 255)
PURPLE   = (50, 0, 250)
MAGENTA  = (120, 0, 160)

WHITE    = (140, 150, 150)
PINK     = (200, 80,  120)   # pale
PEACH    = (180, 120, 30)    # pale orange
MINT     = (30,  190, 50)    # pale green
SKY      = (60,   150, 250)  # pale blue

# Dim variants (~50% of base) for backgrounds / status indicators.
# Nonzero channels use max(20, half of base) so at indoor MULTIPLIER (0.05)
# each intended channel still rounds to at least 1 after scaling.
RED_DIM     = (65, 0,   0)
GREEN_DIM   = (0,  115, 0)
BLUE_DIM    = (0,  20,  127)
YELLOW_DIM  = (55, 60,  0)
WHITE_DIM   = (70, 75,  75)
ORANGE_DIM  = (60, 20,  0)
AMBER_DIM   = (60, 40,  0)
PINK_DIM    = (100, 40,  60)
PURPLE_DIM  = (25, 0,   125)

# ══════════════════════════════════════════════
# 6×10 GRID SHAPES — drawn natively for the tall matrix
# ══════════════════════════════════════════════
# Canvas reference (col across, row down; row-major index = row*6 + col):
#        c0 c1 c2 c3 c4 c5
#   r0 [  0  1  2  3  4  5 ]
#   r1 [  6  7  8  9 10 11 ]
#   ...
#   r9 [ 54 55 56 57 58 59 ]

# ── Numbers (5×7 font, left-aligned cols 0-4, rows 1-7) ──
SHAPE_0 = _glyph("01110", "10001", "10011", "10101", "11001", "10001", "01110")
SHAPE_1 = _glyph("00100", "01100", "00100", "00100", "00100", "00100", "01110")
SHAPE_2 = _glyph("01110", "10001", "00001", "00010", "00100", "01000", "11111")
SHAPE_3 = _glyph("11111", "00010", "00100", "00010", "00001", "10001", "01110")
SHAPE_4 = _glyph("00010", "00110", "01010", "10010", "11111", "00010", "00010")
SHAPE_5 = _glyph("11111", "10000", "11110", "00001", "00001", "10001", "01110")
SHAPE_6 = _glyph("00110", "01000", "10000", "11110", "10001", "10001", "01110")
SHAPE_7 = _glyph("11111", "00001", "00010", "00100", "01000", "01000", "01000")
SHAPE_8 = _glyph("01110", "10001", "10001", "01110", "10001", "10001", "01110")
SHAPE_9 = _glyph("01110", "10001", "10001", "01111", "00001", "00010", "01100")

# ── Letters (5×7 font, left-aligned cols 0-4, rows 1-7) ──
SHAPE_A = _glyph("01110", "10001", "10001", "11111", "10001", "10001", "10001")
SHAPE_B = _glyph("11110", "10001", "10001", "11110", "10001", "10001", "11110")
SHAPE_C = _glyph("01110", "10001", "10000", "10000", "10000", "10001", "01110")
SHAPE_D = _glyph("11100", "10010", "10001", "10001", "10001", "10010", "11100")
SHAPE_E = _glyph("11111", "10000", "10000", "11110", "10000", "10000", "11111")
SHAPE_F = _glyph("11111", "10000", "10000", "11110", "10000", "10000", "10000")
SHAPE_G = _glyph("01110", "10001", "10000", "10111", "10001", "10001", "01111")
SHAPE_H = _glyph("10001", "10001", "10001", "11111", "10001", "10001", "10001")
SHAPE_I = _glyph("01110", "00100", "00100", "00100", "00100", "00100", "01110")
SHAPE_J = _glyph("00111", "00010", "00010", "00010", "00010", "10010", "01100")
SHAPE_K = _glyph("10001", "10010", "10100", "11000", "10100", "10010", "10001")
SHAPE_L = _glyph("10000", "10000", "10000", "10000", "10000", "10000", "11111")
SHAPE_M = _glyph("10001", "11011", "10101", "10101", "10001", "10001", "10001")
SHAPE_N = _glyph("10001", "10001", "11001", "10101", "10011", "10001", "10001")
SHAPE_O = _glyph("01110", "10001", "10001", "10001", "10001", "10001", "01110")
SHAPE_P = _glyph("11110", "10001", "10001", "11110", "10000", "10000", "10000")
SHAPE_Q = _glyph("01110", "10001", "10001", "10001", "10101", "10010", "01101")
SHAPE_R = _glyph("11110", "10001", "10001", "11110", "10100", "10010", "10001")
SHAPE_S = _glyph("01111", "10000", "10000", "01110", "00001", "00001", "11110")
SHAPE_T = _glyph("11111", "00100", "00100", "00100", "00100", "00100", "00100")
SHAPE_U = _glyph("10001", "10001", "10001", "10001", "10001", "10001", "01110")
SHAPE_V = _glyph("10001", "10001", "10001", "10001", "10001", "01010", "00100")
SHAPE_W = _glyph("10001", "10001", "10001", "10101", "10101", "11011", "10001")
SHAPE_X = _glyph("10001", "10001", "01010", "00100", "01010", "10001", "10001")
SHAPE_Y = _glyph("10001", "10001", "01010", "00100", "00100", "00100", "00100")
SHAPE_Z = _glyph("11111", "00001", "00010", "00100", "01000", "10000", "11111")

# ── Symbols ──
SHAPE_QUESTION = _art("", "011100", "100010", "000010", "000100",
                      "001000", "001000", "000000", "001000")
SHAPE_EXCLAIM  = _art("", "001100", "001100", "001100", "001100",
                      "001100", "001100", "000000", "001100")
SHAPE_PLUS     = _art("", "", "001100", "001100", "111111",
                      "111111", "001100", "001100")
SHAPE_DIAMOND  = _art("", "001100", "011110", "111111", "111111",
                      "111111", "111111", "011110", "001100")
SHAPE_POWER    = _art("", "001100", "101101", "100001", "100001",
                      "100001", "010010", "001100")
SHAPE_HEART    = _art("", "011011", "111111", "111111", "011110", "001100")
SHAPE_CHECK    = _art("", "", "000011", "000110", "001100",
                      "101000", "111000", "010000")
SHAPE_LIGHTNING = _art("000110", "001100", "011000", "111110",
                       "001100", "011000", "110000")
SHAPE_MUSIC    = _art("", "000110", "000110", "000100", "000100",
                      "000100", "000100", "110100", "111100", "111000")
SHAPE_HOUSE    = _art("", "001100", "011110", "111111", "100001",
                      "101101", "101101", "111111")
SHAPE_TREE     = _art("", "001100", "011110", "011110", "111111",
                      "111111", "001100", "001100")
SHAPE_HOURGLASS = _art("", "111111", "011110", "001100", "001100",
                       "001100", "011110", "111111")
SHAPE_MOON     = _art("", "001110", "011100", "111000", "111000",
                      "111000", "011100", "001110")
SHAPE_STAR     = _art("", "001100", "001100", "111111", "011110",
                      "001100", "011110", "110011")
SHAPE_RAINDROP = _art("", "001100", "001100", "011110", "011110",
                      "111111", "111111", "011110")
SHAPE_FLAME    = _art("", "", "000100", "001100", "001110",
                      "011110", "111111", "111011", "011110")
SHAPE_SPIRAL   = _art("111111", "000001", "111101", "100101",
                      "101101", "100001", "111111")
SHAPE_FISH     = _art("", "", "", "010000", "111010",
                      "011111", "111010", "010000")
SHAPE_BIRD     = _art("", "", "", "100001", "110011", "011110", "001100")
SHAPE_PACMAN   = _art("", "011110", "111100", "111000", "110000",
                      "111000", "111100", "011110")
SHAPE_INVADER  = _art("", "", "100001", "011110", "111111",
                      "101101", "111111", "010010", "101101")
SHAPE_GHOST    = _art("", "011110", "111111", "110011", "111111",
                      "111111", "111111", "101101")
# Alternating checkerboard across the whole matrix.
SHAPE_CHECKERS = tuple(_xy(c, r) for c in range(COLS) for r in range(ROWS)
                       if (c + r) % 2 == 0)

# ── Media / UI ──
SHAPE_PLAY        = _art("", "010000", "011000", "011100", "011110",
                         "011110", "011100", "011000", "010000")
SHAPE_PAUSE       = _art("", "", "011011", "011011", "011011",
                         "011011", "011011", "011011")
SHAPE_RECTANGLE   = _art("", "", "111111", "111111", "111111",
                         "111111", "111111", "111111")
SHAPE_FASTFORWARD = _art("", "", "", "100100", "110110",
                         "111111", "110110", "100100")
SHAPE_REWIND      = _art("", "", "", "001001", "011011",
                         "111111", "011011", "001001")
SHAPE_WIFI        = _art("", "", "011110", "100001", "001100",
                         "010010", "001100")
SHAPE_POINTER     = _art("", "100000", "110000", "111000", "111100",
                         "111110", "111000", "010100", "010010")
SHAPE_BULLSEYE    = _art("", "011110", "100001", "101101", "101101",
                         "100001", "011110")

SHAPE_BATTERY_FULL  = _art("001100", "011110", "011110", "011110", "011110",
                           "011110", "011110", "011110", "011110")
SHAPE_BATTERY_HALF  = _art("001100", "011110", "010010", "010010", "010010",
                           "011110", "011110", "011110", "011110")
SHAPE_BATTERY_EMPTY = _art("001100", "011110", "010010", "010010", "010010",
                           "010010", "010010", "010010", "011110")

# ── Characters ──
SHAPE_DANCER1 = _art("", "001100", "001100", "101101", "011110",
                     "001100", "010010", "100001")
SHAPE_DANCER2 = _art("", "001100", "001100", "111111", "001100",
                     "001100", "010010", "010010")
SHAPE_DANCER3 = _art("", "001100", "001100", "001101", "011100",
                     "001100", "010010", "100010")
SHAPE_SAD_FACE     = _art("", "", "", "010010", "", "011110", "100001")
SHAPE_HAPPY_FACE   = _art("", "", "", "010010", "", "100001", "011110")
SHAPE_NEUTRAL_FACE = _art("", "", "", "010010", "", "", "011110")
SHAPE_SL_FACE      = _art("", "", "", "010010", "", "", "111111")
SHAPE_ANGRY_FACE   = _art("", "", "100001", "010010", "", "011110", "100001")
SHAPE_SLEEPY_FACE  = _art("", "", "", "110011", "010010", "", "011110")

# ── Arrows ──
SHAPE_ARROW_UP = _art("", "001100", "011110", "111111", "001100",
                      "001100", "001100", "001100", "001100")
SHAPE_ARROW_DN = _art("", "001100", "001100", "001100", "001100",
                      "001100", "111111", "011110", "001100")
SHAPE_ARROW_L  = _art("", "", "", "001000", "011000",
                      "111111", "011000", "001000")
SHAPE_ARROW_R  = _art("", "", "", "000100", "000110",
                      "111111", "000110", "000100")
# Lower-left / lower-right filled triangles.
SHAPE_DIAG_L = tuple(_xy(c, r) for r in range(ROWS) for c in range(COLS)
                     if c <= r * (COLS - 1) // (ROWS - 1))
SHAPE_DIAG_R = tuple(_xy(c, r) for r in range(ROWS) for c in range(COLS)
                     if (COLS - 1 - c) <= r * (COLS - 1) // (ROWS - 1))

# ── Utility / geometric ──
SHAPE_LEFT_COL  = tuple(_xy(0, r) for r in range(ROWS))
SHAPE_RIGHT_COL = tuple(_xy(COLS - 1, r) for r in range(ROWS))
SHAPE_TOP_ROW   = tuple(_xy(c, 0) for c in range(COLS))
SHAPE_BOT_ROW   = tuple(_xy(c, ROWS - 1) for c in range(COLS))
# Center 2×2 block.
_cc = (COLS - 1) // 2
_cr = (ROWS - 1) // 2
SHAPE_CENTER  = tuple(_xy(c, r) for c in (_cc, _cc + 1) for r in (_cr, _cr + 1))
SHAPE_CORNERS = (_xy(0, 0), _xy(0, ROWS - 1), _xy(COLS - 1, 0), _xy(COLS - 1, ROWS - 1))
# Perimeter of the whole matrix.
SHAPE_BORDER = tuple(sorted(set(
    [_xy(c, 0) for c in range(COLS)] + [_xy(c, ROWS - 1) for c in range(COLS)] +
    [_xy(0, r) for r in range(ROWS)] + [_xy(COLS - 1, r) for r in range(ROWS)]
)))
# Filled centered block (cols 1..COLS-2, rows 3..ROWS-4) — the "inner" ring
# used by grow/shrink animations and the idle display.
SHAPE_INNER_3x3 = tuple(_xy(c, r)
                        for c in range(1, COLS - 1)
                        for r in range(3, ROWS - 3))
# Diagonals for the spin animation (one pixel per column).
SHAPE_SLASH_L = tuple(_xy(c, min(ROWS - 1, c * (ROWS - 1) // (COLS - 1)))
                      for c in range(COLS))
SHAPE_SLASH_R = tuple(_xy(c, max(0, (ROWS - 1) - c * (ROWS - 1) // (COLS - 1)))
                      for c in range(COLS))
# Mid horizontal / vertical bars (used by the spinner).
SHAPE_MID_ROW = tuple(_xy(c, r) for c in range(COLS) for r in (_cr, _cr + 1))
SHAPE_MID_COL = tuple(_xy(c, r) for c in (_cc, _cc + 1) for r in range(ROWS))

TRIGGER_LED = {"buttondown": 0, "buttonup": 1, "whenshake": 2}

TRIGGER_COLOR_BRIGHT = {
    "buttondown": (0, 30, 0),
    "buttonup":   (0, 0, 30),
    "whenshake":  (0, 20, 20),
}

TRIGGER_COLOR_DIM = {
    "buttondown": (0, 6, 0),
    "buttonup":   (0, 0, 6),
    "whenshake":  (0, 4, 4),
}

GESTURE_LED          = 3
GESTURE_COLOR_BRIGHT = (15, 0, 15)
GESTURE_COLOR_DIM    = (3, 0, 3)

SC_LED               = 4
SC_COLOR_BRIGHT      = (15, 15, 0)
SC_COLOR_DIM         = (3, 3, 0)

READY_LED   = 5
READY_COLOR = (5, 0, 0)

# Centered cluster lit during idle (battery-colored). Same set as the
# inner block used by the grow/shrink animations.
INNER_RING = list(SHAPE_INNER_3x3)

# Boot status LED positions (top of the left column: indices 0, 1, 2)
BOOT_LED_POWER  = 0
BOOT_LED_BATT   = 1
BOOT_LED_READY  = 2

# Row data LED indices for each boot stage (cols 1-4 of that stage's row).
# Stage indicators themselves live in the left column (SHAPE_LEFT_COL[stage]),
# i.e. indices 0..4. Five stages fit comfortably in the 10-row left column.
_BOOT_STAGE_DATA = tuple(
    tuple(_xy(c, stage) for c in range(1, 5))   # cols 1-4 at row=stage
    for stage in range(5)
)


# ══════════════════════════════════════════════
# SCALED NEOPIXEL WRAPPER
# ══════════════════════════════════════════════
class _ScaledNeoPixel:
    """
    Drop-in replacement for NeoPixel that multiplies every (r, g, b)
    write by brightness.MULTIPLIER. The multiplier is read fresh on
    each write, so it stays current even if calibrate() runs after
    the wrapper is constructed.

    Supports: indexed write/read, .fill(), .write(), .n, len().
    Does NOT scale on read-back — np[i] returns the value actually
    sent to the strip (already scaled), not the original color.
    """

    __slots__ = ('_np', 'n')

    def __init__(self, pin, n):
        self._np = _RawNeoPixel(pin, n)
        self.n = n

    def __setitem__(self, i, color):
        m = brightness.MULTIPLIER
        # color is expected to be a 3-tuple (r, g, b). Scale and clamp to byte.
        try:
            r = int(color[0] * m)
            g = int(color[1] * m)
            b = int(color[2] * m)
        except Exception:
            self._np[i] = color
            return
        if r > 255: r = 255
        if g > 255: g = 255
        if b > 255: b = 255
        self._np[i] = (r, g, b)

    def __getitem__(self, i):
        return self._np[i]

    def __len__(self):
        return self.n

    def fill(self, color):
        m = brightness.MULTIPLIER
        try:
            r = min(255, int(color[0] * m))
            g = min(255, int(color[1] * m))
            b = min(255, int(color[2] * m))
            self._np.fill((r, g, b))
        except Exception:
            self._np.fill(color)

    def write(self):
        self._np.write()


def _is_gesture(name):
    return name is not None and name.startswith("gesture:")

def _is_sc(name):
    return name is not None and name.startswith("SC:")


def battery_color(soc):
    """Return (r, g, b) for a given state-of-charge percentage."""
    if soc > 75:
        # Keep nonzero channels >= 20 so indoor multiplier (0.05) still shows.
        return (0, 120, 0)      # green
    elif soc > 30:
        return (120, 80, 0)     # yellow
    elif soc > 10:
        return (120, 0, 0)      # red
    else:
        return (120, 0, 0)      # red (caller handles flashing for <10%)


class Leds:
    def __init__(self, pin=None, num=None):
        if pin is None:
            pin = HUB_CONFIG.get("led_pin", 20)
        if num is None:
            num = HUB_CONFIG.get("num_leds", 60)
        self.np = _ScaledNeoPixel(machine.Pin(pin), num)
        self.num = num

    def off(self):
        for i in range(self.num):
            self.np[i] = (0, 0, 0)
        self.np.write()

    def solid(self, r, g, b):
        for i in range(self.num):
            self.np[i] = (r, g, b)
        self.np.write()

    def fill(self, color):
        """Fill all LEDs with a color tuple. Tuple-friendly form of solid()."""
        self.solid(*color)

    def flash(self, r, g, b, times=2, on_ms=120, off_ms=80):
        for _ in range(times):
            self.solid(r, g, b); time.sleep_ms(on_ms)
            self.off(); time.sleep_ms(off_ms)

    def flash_color(self, color, times=2, on_ms=120, off_ms=80):
        """Flash a color tuple. Tuple-friendly form of flash()."""
        self.flash(color[0], color[1], color[2],
                   times=times, on_ms=on_ms, off_ms=off_ms)

    def show_shape(self, indices, color, bg=OFF):
        """
        Light only the LEDs at `indices` in `color`, all others in `bg`.
        Indices outside the strip range are silently skipped.

        Example:
            leds.show_shape(SHAPE_SAD_FACE, BLUE)
            leds.show_shape(SHAPE_HEART, RED, bg=WHITE_DIM)
        """
        for i in range(self.num):
            self.np[i] = bg
        for idx in indices:
            if 0 <= idx < self.num:
                self.np[idx] = color
        self.np.write()

    def show_pattern(self, color_to_indices, bg=OFF):
        """
        Light multiple groups of LEDs in different colors.

        color_to_indices: dict mapping (r, g, b) tuples to iterables of indices.
        bg: background color for LEDs not listed in any group.

        Example:
            leds.show_pattern({
                RED:    (0, 4),
                YELLOW: (12,),
                GREEN:  (20, 24),
            })
        """
        for i in range(self.num):
            self.np[i] = bg
        for color, indices in color_to_indices.items():
            for idx in indices:
                if 0 <= idx < self.num:
                    self.np[idx] = color
        self.np.write()

    def animate_dancer(self, frame, color, bg=OFF, frames_per_step=6):
        """
        Cycle through DANCER1, DANCER2, DANCER3 shapes based on frame count.
        Call this each loop iteration to animate a dancing figure.

        Example:
            leds.animate_dancer(self._frame, PURPLE)
        """
        dancers = (SHAPE_DANCER1, SHAPE_DANCER2, SHAPE_DANCER3, SHAPE_DANCER2)
        idx = (frame // frames_per_step) % len(dancers)
        self.show_shape(dancers[idx], color, bg)


    def animate_rows(self, frame, color, bg=OFF, frames_per_step=6):
        """
        Sweep a lit row top-to-bottom, repeating. Uses the full height of
        the matrix (all ROWS rows), so on the 6×10 wand the bar travels
        through 10 rows rather than the old 5.

        Example:
            leds.animate_rows(self._frame, BLUE)
        """
        r = (frame // frames_per_step) % ROWS
        row = tuple(_xy(c, r) for c in range(COLS))
        self.show_shape(row, color, bg)

    def animate_columns(self, frame, color, bg=OFF, frames_per_step=6):
        """
        Sweep a lit column left-to-right, repeating. Uses all COLS columns.

        Example:
            leds.animate_columns(self._frame, GREEN)
        """
        c = (frame // frames_per_step) % COLS
        col = tuple(_xy(c, r) for r in range(ROWS))
        self.show_shape(col, color, bg)

    def animate_spin(self, frame, color, bg=OFF, frames_per_step=6):
        """
        Rotate a bar through the center: mid-row, slash, mid-col, anti-slash.
        Creates a spinning-line effect through the middle of the grid.

        Example:
            leds.animate_spin(self._frame, PURPLE)
        """
        spin = (SHAPE_MID_ROW, SHAPE_SLASH_L, SHAPE_MID_COL, SHAPE_SLASH_R)
        idx = (frame // frames_per_step) % len(spin)
        self.show_shape(spin[idx], color, bg)

    def animate_grow(self, frame, color, bg=OFF, frames_per_step=6):
        """
        Expand outward: CENTER, INNER block, BORDER, blank, repeat.
        The "blank" step shows bg only (no foreground shape).

        Example:
            leds.animate_grow(self._frame, CYAN)
        """
        grow = (SHAPE_CENTER, SHAPE_INNER_3x3, SHAPE_BORDER, ())
        idx = (frame // frames_per_step) % len(grow)
        self.show_shape(grow[idx], color, bg)

    def animate_shrink(self, frame, color, bg=OFF, frames_per_step=6):
        """
        Contract inward: BORDER, INNER block, CENTER, blank, repeat.
        The "blank" step shows bg only (no foreground shape).

        Example:
            leds.animate_shrink(self._frame, ORANGE)
        """
        shrink = (SHAPE_BORDER, SHAPE_INNER_3x3, SHAPE_CENTER, ())
        idx = (frame // frames_per_step) % len(shrink)
        self.show_shape(shrink[idx], color, bg)

    def animate_arrow_spin(self, frame, color, bg=OFF, frames_per_step=6):
        """
        Rotate arrow direction: ARROW_UP, ARROW_L, ARROW_DN, ARROW_R, repeat.

        Example:
            leds.animate_arrow_spin(self._frame, YELLOW)
        """
        arrows = (SHAPE_ARROW_UP, SHAPE_ARROW_L, SHAPE_ARROW_DN, SHAPE_ARROW_R)
        idx = (frame // frames_per_step) % len(arrows)
        self.show_shape(arrows[idx], color, bg)

    def animate_firework(self, frame, color, bg=OFF, frames_per_step=6):
        """
        Burst outward: CENTER, STAR, CORNERS, blank, repeat.
        The "blank" step shows bg only (no foreground shape).

        Example:
            leds.animate_firework(self._frame, MAGENTA)
        """
        burst = (SHAPE_CENTER, SHAPE_STAR, SHAPE_CORNERS, ())
        idx = (frame // frames_per_step) % len(burst)
        self.show_shape(burst[idx], color, bg)

    def pulse_color(self, r, g, b, duration_ms=600):
        steps = 20
        for s in range(steps):
            scale = math.sin(math.pi * s / steps)
            self.solid(int(r * scale), int(g * scale), int(b * scale))
            time.sleep_ms(duration_ms // steps)
        self.off()

    def breathe(self, r, g, b, frame):
        bri = (math.sin(frame * 0.08) + 1) / 2
        self.solid(int(r * bri), int(g * bri), int(b * bri))

    def breathe_shape(self, indices, color, frame, bg=OFF, speed=0.08, min_level=2):
        """
        Breathing animation for a shape. Sin-wave brightness scaling driven by frame counter.

        speed: sin coefficient. Larger = faster breathing. Default 0.08 gives
        a ~3.1s cycle at a 40ms loop. Try 0.16 for roughly twice as fast.

        min_level: floor applied to each non-zero RGB channel of the foreground
        color so the shape never fully disappears at the bottom of the breath.
        The floor is applied per-channel and only to channels that are non-zero
        in the source color, so a pure (R, 0, 0) still breathes as pure red.
        """
        bri = (math.sin(frame * speed) + 1) / 2
        r = int(color[0] * bri)
        g = int(color[1] * bri)
        b = int(color[2] * bri)
        if color[0] and r < min_level: r = min_level
        if color[1] and g < min_level: g = min_level
        if color[2] and b < min_level: b = min_level
        self.show_shape(indices, (r, g, b), bg=bg)

    def fade_shape(self, indices, color, duration_ms, bg=OFF):
        """Blocking linear fade from full color to bg over duration_ms. Uses ~20 steps."""
        steps = 20
        if duration_ms <= 0:
            self.show_shape(indices, bg, bg=bg)
            return
        step_ms = max(1, duration_ms // steps)
        for s in range(steps, -1, -1):
            scale = s / steps
            self.show_shape(
                indices,
                (int(color[0] * scale), int(color[1] * scale), int(color[2] * scale)),
                bg=bg
            )
            time.sleep_ms(step_ms)

    # ══════════════════════════════════════════
    # BOOT SEQUENCE LEDs
    # ══════════════════════════════════════════
    # The boot bar uses the left column for stage indicators (one LED per
    # stage, indices 0..4) and cols 1-4 of the same row for analog data.

    def boot_power(self):
        """
        Called at module level before I2C or main() runs.
        Lights stage 0 (LED 0) dim white as the earliest possible power signal.
        If main() never starts due to an import failure, this LED stays dim white.
        boot_stage_ok(0) upgrades it to green once main() is actually reached.
        """
        self.np[SHAPE_LEFT_COL[0]] = WHITE
        self.np.write()

    def boot_stage_start(self, stage):
        """Light the stage indicator dim white — init for this stage is beginning."""
        if stage < len(SHAPE_LEFT_COL):
            self.np[SHAPE_LEFT_COL[stage]] = WHITE
            self.np.write()

    def boot_stage_ok(self, stage, row_colors=None, row_flash=0):
        """
        Mark a boot stage green (success). Previously completed stages are unaffected.

        row_colors: optional list of up to 4 color tuples for LEDs cols 1-4 of
        the same row. Used to display analog data (battery level, brightness tier).
        row_flash: if > 0 and row_colors provided, flash the row that many times
        (100ms on / 100ms off) before settling. Used for low-battery warning.
        """
        if stage >= len(_BOOT_STAGE_DATA):
            return
        self.np[SHAPE_LEFT_COL[stage]] = GREEN
        if row_colors is not None:
            row = _BOOT_STAGE_DATA[stage]
            if row_flash > 0:
                for _ in range(row_flash):
                    for i, color in enumerate(row_colors):
                        if i < len(row):
                            self.np[row[i]] = color
                    self.np.write()
                    time.sleep_ms(100)
                    for i in range(len(row_colors)):
                        if i < len(row):
                            self.np[row[i]] = OFF
                    self.np.write()
                    time.sleep_ms(100)
            for i, color in enumerate(row_colors):
                if i < len(row):
                    self.np[row[i]] = color
        self.np.write()

    def boot_stage_warn(self, stage):
        """
        Mark a boot stage amber — non-fatal failure, system continues.
        Row data for this stage is left empty. Previously completed stages are unaffected.
        """
        if stage < len(SHAPE_LEFT_COL):
            self.np[SHAPE_LEFT_COL[stage]] = AMBER
            self.np.write()

    def boot_stage_fail(self, stage):
        """
        Mark a boot stage as a fatal failure. Flashes only that stage indicator
        red twice, then holds red. Previously completed stage LEDs remain visible
        so the failure point is clear.
        """
        if stage >= len(SHAPE_LEFT_COL):
            return
        led = SHAPE_LEFT_COL[stage]
        for _ in range(2):
            self.np[led] = RED
            self.np.write()
            time.sleep_ms(150)
            self.np[led] = OFF
            self.np.write()
            time.sleep_ms(100)
        self.np[led] = RED
        self.np.write()

    # ── Legacy 3-LED boot methods ─────────────────────────────────────────
    # These are retained for standalone game entry points (jumpin.py, etc.)
    # that call them directly. main.py uses boot_stage_* instead.

    def boot_battery(self, soc):
        """Legacy: show battery on LEDs 0-1. Use boot_stage_ok(2, row) instead."""
        color = battery_color(soc)
        if soc <= 10:
            for _ in range(5):
                self.np[BOOT_LED_POWER] = color
                self.np[BOOT_LED_BATT] = color
                self.np.write()
                time.sleep_ms(100)
                self.np[BOOT_LED_POWER] = OFF
                self.np[BOOT_LED_BATT] = OFF
                self.np.write()
                time.sleep_ms(100)
        self.np[BOOT_LED_POWER] = color
        self.np[BOOT_LED_BATT] = color
        self.np.write()

    def boot_ready(self, soc):
        """Legacy: light LED 2 in battery color. Use boot_stage_ok(4) instead."""
        self.np[BOOT_LED_READY] = battery_color(soc)
        self.np.write()

    def boot_clear(self):
        """Legacy: clear LEDs 0-2. leds.off() is preferred for the new boot bar."""
        for i in (BOOT_LED_POWER, BOOT_LED_BATT, BOOT_LED_READY):
            if i < self.num:
                self.np[i] = OFF
        self.np.write()

    # ══════════════════════════════════════════
    # IDLE / SCANNING / PROGRAMMING (unchanged from original)
    # ══════════════════════════════════════════

    def idle_default(self, soc):
        """
        Default idle: centered cluster lit with battery charge color (static).
        Use idle_low_blink() instead when battery <= 10%.
        """
        color = battery_color(soc)
        for i in range(self.num):
            self.np[i] = color if i in INNER_RING else (0, 0, 0)
        self.np.write()

    def idle_low_blink(self, frame):
        """
        Battery <= 10% idle: center LED blinks red (~1Hz at 200ms loop).
        All other LEDs off.
        """
        center = self.num // 2
        on = ((frame // 5) % 2) == 0
        for i in range(self.num):
            if i == center and on:
                self.np[i] = (40, 0, 0)
            else:
                self.np[i] = (0, 0, 0)
        self.np.write()

    def idle(self, frame):
        """LEGACY: soft breathing across all LEDs. Kept for backward compat."""
        phase = (math.sin(frame * 0.06) + 1) / 2
        level = 2 + int(6 * phase)
        r = level
        g = int(level * 0.6)
        b = level
        for i in range(self.num):
            self.np[i] = (r, g, b)
        self.np.write()

    def idle_sleep(self):
        """Static dim blue dot in the center while NFC sleeps."""
        center = self.num // 2
        for i in range(self.num):
            self.np[i] = (0, 0, 3) if i == center else (0, 0, 0)
        self.np.write()

    def breathe_sleep(self, frame):
        """Even dimmer single-pixel breathing — NFC is sleeping."""
        phase = (math.sin(frame * 0.04) + 1) / 2
        level = 1 + int(4 * phase)
        center = self.num // 2
        for i in range(self.num):
            if i == center:
                self.np[i] = (0, 0, level)
            else:
                self.np[i] = (0, 0, 0)
        self.np.write()

    # ── Scanning (wand) ──

    def scan_animate(self, frame):
        center = self.num // 2
        radius = frame % 8
        for i in range(self.num):
            dist = abs(i - center)
            if dist == radius:
                self.np[i] = (15, 10, 20)
            elif dist == max(0, radius - 1):
                self.np[i] = (5, 3, 7)
            else:
                self.np[i] = (0, 0, 0)
        self.np.write()

    def scan_complete(self):
        self.solid(20, 15, 25)
        time.sleep_ms(80)
        self.off()

    # ── Programming indicators (wand, needs >=6 LEDs) ──

    def show_programming(self, rules, editing):
        for i in range(self.num):
            self.np[i] = (0, 0, 0)
        if self.num < 6:
            self.np.write(); return

        has_any = False
        for trig in TRIGGER_ORDER:
            idx = TRIGGER_LED[trig]
            if trig in rules and len(rules[trig]) > 0:
                self.np[idx] = TRIGGER_COLOR_BRIGHT[trig]
                has_any = True
            elif trig == editing:
                self.np[idx] = TRIGGER_COLOR_DIM[trig]

        if GESTURE_LED < self.num:
            gc = False
            for k in rules:
                if _is_gesture(k) and len(rules[k]) > 0:
                    gc = True; break
            if gc:
                self.np[GESTURE_LED] = GESTURE_COLOR_BRIGHT
                has_any = True
            elif _is_gesture(editing):
                self.np[GESTURE_LED] = GESTURE_COLOR_DIM

        if SC_LED < self.num:
            sc = False
            for k in rules:
                if _is_sc(k) and len(rules[k]) > 0:
                    sc = True; break
            if sc:
                self.np[SC_LED] = SC_COLOR_BRIGHT
                has_any = True
            elif _is_sc(editing):
                self.np[SC_LED] = SC_COLOR_DIM

        if has_any and READY_LED < self.num:
            self.np[READY_LED] = READY_COLOR
        self.np.write()

    def show_running(self, rules):
        for i in range(self.num):
            self.np[i] = (0, 0, 0)
        for trig in TRIGGER_ORDER:
            if trig in rules and len(rules[trig]) > 0:
                idx = TRIGGER_LED[trig]
                if idx < self.num:
                    self.np[idx] = TRIGGER_COLOR_DIM[trig]
        if GESTURE_LED < self.num:
            for k in rules:
                if _is_gesture(k) and len(rules[k]) > 0:
                    self.np[GESTURE_LED] = GESTURE_COLOR_DIM; break
        if SC_LED < self.num:
            for k in rules:
                if _is_sc(k) and len(rules[k]) > 0:
                    self.np[SC_LED] = SC_COLOR_DIM; break
        self.np.write()

    # ── Battery (adaptive) ──

    def show_battery_level(self, soc):
        soc_c = max(0, min(100, soc))
        lit = max(1, int(soc_c / 100 * self.num))
        if soc_c > 50:
            r, g, b = 0, 40, 0
        elif soc_c > 20:
            r, g, b = 40, 25, 0
        else:
            r, g, b = 40, 0, 0
        for i in range(self.num):
            self.np[i] = (r, g, b) if i < lit else (0, 0, 0)
        self.np.write()
        return r, g, b, lit

    def fade_out_battery(self, r, g, b, lit):
        for step in range(10, -1, -1):
            sc = step / 10
            for i in range(self.num):
                if i < lit:
                    self.np[i] = (int(r * sc), int(g * sc), int(b * sc))
                else:
                    self.np[i] = (0, 0, 0)
            self.np.write()
            time.sleep_ms(40)
        self.off()
