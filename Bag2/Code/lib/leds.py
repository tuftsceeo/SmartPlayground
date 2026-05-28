"""
LED Helpers — NeoPixel control and status display
===================================================
Auto-configures from hubtype. Works on any device.

All LED writes pass through _ScaledNeoPixel, which multiplies every
(r, g, b) tuple by brightness.MULTIPLIER on its way to the underlying
NeoPixel. Code outside this file does not need to know — when
brightness.calibrate(opt) sets MULTIPLIER on boot, every consumer
(Leds methods, freeze_dance, color_quest, gesture engine, etc.)
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

TRIGGER_ORDER = ["buttondown", "buttonup", "shake"]

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
# 5×5 GRID SHAPES — LED index lists
# ══════════════════════════════════════════════
# Grid layout:
#    0  1  2  3  4
#    5  6  7  8  9
#   10 11 12 13 14
#   15 16 17 18 19
#   20 21 22 23 24

# Numbers
SHAPE_0                  = (2, 3, 6, 9, 11, 14, 16, 19, 22, 23)
SHAPE_1                  = (2, 3, 8, 13, 18, 23)
SHAPE_2                  = (2, 3, 6, 9, 13, 17, 21, 22, 23, 24)
SHAPE_3                  = (1, 2, 3, 4, 9, 12, 13, 14, 19, 21, 22, 23, 24)
SHAPE_4                  = (1, 4, 6, 9, 11, 12, 13, 14, 19, 24)
SHAPE_5                  = (2, 3, 4, 6, 11, 12, 13, 14, 19, 21, 22, 23, 24)
SHAPE_6                  = (1, 2, 3, 4, 6, 11, 12, 13, 14, 16, 19, 21, 22, 23, 24)
SHAPE_7                  = (1, 2, 3, 4, 9, 13, 17, 21)
SHAPE_8                  = (1, 2, 3, 4, 6, 9, 12, 13, 16, 19, 21, 22, 23, 24)
SHAPE_9                  = (1, 2, 3, 4, 6, 9, 11, 12, 13, 14, 19, 21, 22, 23, 24)

# Letters
SHAPE_A                  = (0, 1, 2, 3, 4, 5, 9, 10, 11, 12, 13, 14, 15, 19, 20, 24)
SHAPE_B                  = (0, 1, 2, 3, 5, 9, 10, 11, 12, 13, 14, 15, 19, 20, 21, 22, 23)
SHAPE_C                  = (1, 2, 3, 5, 10, 15, 21, 22, 23)
SHAPE_D                  = (0, 1, 2, 3, 5, 9, 10, 14, 15, 19, 20, 21, 22, 23)
SHAPE_E                  = (0, 1, 2, 3, 4, 5, 10, 11, 12, 13, 15, 20, 21, 22, 23, 24)
SHAPE_F                  = (0, 1, 2, 3, 4, 5, 10, 11, 12, 13, 15, 20)
SHAPE_G                  = (1, 2, 3, 5, 10, 13, 14, 15, 19, 21, 22, 23, 24)
SHAPE_H                  = (1, 4, 6, 9, 11, 12, 13, 14, 16, 19, 21, 24)
SHAPE_I                  = (1, 2, 3, 7, 12, 17, 21, 22, 23)
SHAPE_J                  = (1, 2, 3, 4, 8, 13, 16, 18, 21, 22, 23)
SHAPE_K                  = (0, 3, 5, 7, 10, 11, 15, 17, 20, 23)
SHAPE_L                  = (0, 5, 10, 15, 20, 21, 22, 23)
SHAPE_M                  = (0, 4, 5, 6, 8, 9, 10, 12, 14, 15, 19, 20, 24)
SHAPE_N                  = (0, 4, 5, 6, 9, 10, 12, 14, 15, 18, 19, 20, 24)
SHAPE_O                  = (0, 1, 2, 3, 4, 5, 9, 10, 14, 15, 19, 20, 21, 22, 23, 24)
SHAPE_P                  = (0, 1, 2, 3, 4, 5, 9, 10, 11, 12, 13, 14, 15, 20)
SHAPE_Q                  = (1, 2, 3, 5, 9, 10, 14, 15, 18, 21, 22, 24)
SHAPE_R                  = (0, 1, 2, 3, 5, 9, 10, 14, 15, 16, 17, 18, 20, 24)
SHAPE_S                  = (0, 1, 2, 3, 4, 5, 10, 11, 12, 13, 14, 19, 20, 21, 22, 23, 24)
SHAPE_T                  = (0, 1, 2, 3, 4, 7, 12, 17, 22)
SHAPE_U                  = (0, 4, 5, 9, 10, 14, 15, 19, 21, 22, 23)
SHAPE_V                  = (0, 4, 5, 9, 11, 13, 16, 18, 22)
SHAPE_W                  = (0, 4, 5, 9, 10, 12, 14, 15, 17, 19, 20, 21, 23, 24)
SHAPE_X                  = (0, 4, 6, 8, 12, 16, 18, 20, 24)
SHAPE_Y                  = (0, 4, 6, 8, 12, 17, 22)
SHAPE_Z                  = (0, 1, 2, 3, 4, 8, 12, 16, 20, 21, 22, 23, 24)

# Symbols
SHAPE_QUESTION           = (1, 2, 5, 8, 12, 22)
SHAPE_EXCLAIM            = (2, 7, 12, 22)
SHAPE_PLUS               = (2, 7, 10, 11, 12, 13, 14, 17, 22)
SHAPE_DIAMOND            = (2, 6, 7, 8, 10, 11, 12, 13, 14, 16, 17, 18, 22)
SHAPE_POWER              = (2, 6, 8, 10, 14, 16, 18, 22)
SHAPE_HEART              = (1, 3, 5, 6, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 22)
SHAPE_CHECK              = (9, 13, 15, 17, 21)
SHAPE_LIGHTNING          = (1, 6, 7, 12, 17, 18, 23)
SHAPE_MUSIC              = (2, 3, 7, 12, 15, 16, 17, 20, 21, 22)
SHAPE_HOUSE              = (2, 6, 7, 8, 10, 11, 12, 13, 14, 15, 17, 19, 20, 21, 22, 23, 24)
SHAPE_TREE               = (2, 6, 7, 8, 11, 12, 13, 17, 22)
SHAPE_HOURGLASS          = (0, 1, 2, 3, 4, 6, 8, 12, 16, 18, 20, 21, 22, 23, 24)
SHAPE_MOON               = (2, 3, 4, 6, 7, 11, 12, 16, 17, 22, 23, 24)
SHAPE_STAR               = (2, 5, 7, 9, 11, 12, 13, 15, 17, 19, 22)
SHAPE_RAINDROP           = (2, 6, 8, 10, 14, 15, 19, 21, 22, 23)
SHAPE_FLAME              = (2, 6, 7, 8, 10, 12, 14, 15, 17, 19, 21, 22, 23)
SHAPE_CHECKERS           = (0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24)
SHAPE_SPIRAL             = (0, 1, 2, 3, 5, 8, 12, 16, 19, 21, 22, 23, 24)
SHAPE_FISH               = (2, 6, 7, 9, 10, 12, 13, 14, 16, 17, 19, 22)
SHAPE_BIRD               = (5, 6, 8, 9, 11, 12, 13, 17)
SHAPE_PACMAN             = (1, 2, 3, 4, 5, 7, 8, 10, 11, 12, 15, 16, 17, 18, 21, 22, 23, 24)
SHAPE_INVADER            = (1, 3, 5, 6, 7, 8, 9, 11, 12, 13, 16, 18, 20, 24)
SHAPE_GHOST              = (1, 2, 3, 5, 7, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24)

# Media / UI
SHAPE_PLAY               = (1, 6, 7, 11, 12, 13, 16, 17, 21)
SHAPE_PAUSE              = (1, 3, 6, 8, 11, 13, 16, 18, 21, 23)
SHAPE_RECTANGLE          = (5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19)
SHAPE_FASTFORWARD        = (5, 8, 10, 11, 13, 14, 15, 18)
SHAPE_REWIND             = (6, 9, 10, 11, 13, 14, 16, 19)
SHAPE_WIFI               = (1, 2, 3, 5, 6, 8, 9, 16, 17, 18, 20, 21, 23, 24)
SHAPE_POINTER            = (0, 5, 6, 10, 11, 12, 15, 16, 20)
SHAPE_BULLSEYE           = (1, 2, 3, 5, 9, 10, 12, 14, 15, 19, 21, 22, 23)

SHAPE_BATTERY_FULL  = (2, 6, 7, 8, 11, 12, 13, 16, 17, 18, 21, 22, 23)
SHAPE_BATTERY_HALF  = (2, 6, 8, 11, 13, 16, 17, 18, 21, 22, 23)
SHAPE_BATTERY_EMPTY = (2, 6, 8, 11, 13, 16, 18, 21, 22, 23)

# Characters
SHAPE_DANCER1            = (1, 5, 6, 7, 11, 16, 17, 20, 22)
SHAPE_DANCER2            = (2, 6, 7, 8, 12, 17, 21, 23)
SHAPE_DANCER3            = (3, 7, 8, 9, 13, 17, 18, 22, 24)
SHAPE_SAD_FACE           = (6, 8, 16, 17, 18, 20, 24)
SHAPE_HAPPY_FACE         = (6, 8, 15, 19, 21, 22, 23)
SHAPE_NEUTRAL_FACE       = (6, 8, 21, 22, 23)
SHAPE_SL_FACE            = (5, 8, 15, 21, 22, 23)
SHAPE_ANGRY_FACE         = (0, 4, 6, 8, 21, 22, 23)
SHAPE_SLEEPY_FACE        = (5, 6, 8, 9, 15, 19, 21, 22, 23)

# Arrows
SHAPE_ARROW_UP           = (2, 6, 7, 8, 10, 11, 12, 13, 14, 17, 22)
SHAPE_ARROW_DN           = (2, 7, 10, 11, 12, 13, 14, 16, 17, 18, 22)
SHAPE_ARROW_L            = (2, 6, 7, 10, 11, 12, 13, 14, 16, 17, 22)
SHAPE_ARROW_R            = (2, 7, 8, 10, 11, 12, 13, 14, 17, 18, 22)
SHAPE_DIAG_L             = (0, 5, 6, 10, 11, 12, 15, 16, 17, 18, 20, 21, 22, 23, 24)
SHAPE_DIAG_R             = (4, 8, 9, 12, 13, 14, 16, 17, 18, 19, 20, 21, 22, 23, 24)

# Utility
SHAPE_BORDER             = (0, 1, 2, 3, 4, 5, 9, 10, 14, 15, 19, 20, 21, 22, 23, 24)
SHAPE_INNER_3x3          = (6, 7, 8, 11, 12, 13, 16, 17, 18)
SHAPE_CORNERS            = (0, 4, 20, 24)
SHAPE_CENTER             = (12,)
SHAPE_TOP_ROW            = (0, 1, 2, 3, 4)
SHAPE_ROW2               = (5, 6, 7, 8, 9)
SHAPE_ROW3               = (10, 11, 12, 13, 14)
SHAPE_ROW4               = (15, 16, 17, 18, 19)
SHAPE_BOT_ROW            = (20, 21, 22, 23, 24)
SHAPE_LEFT_COL           = (0, 5, 10, 15, 20)
SHAPE_COL2               = (1, 6, 11, 16, 21)
SHAPE_COL3               = (2, 7, 12, 17, 22)
SHAPE_COL4               = (3, 8, 13, 18, 23)
SHAPE_RIGHT_COL          = (4, 9, 14, 19, 24)
SHAPE_SLASH_L            = (0, 6, 12, 18, 24)
SHAPE_SLASH_R            = (4, 8, 12, 16, 20)

TRIGGER_LED = {"buttondown": 0, "buttonup": 1, "shake": 2}

TRIGGER_COLOR_BRIGHT = {
    "buttondown": (0, 30, 0),
    "buttonup":   (0, 0, 30),
    "shake":      (0, 20, 20),
}

TRIGGER_COLOR_DIM = {
    "buttondown": (0, 6, 0),
    "buttonup":   (0, 0, 6),
    "shake":      (0, 4, 4),
}

GESTURE_LED          = 3
GESTURE_COLOR_BRIGHT = (15, 0, 15)
GESTURE_COLOR_DIM    = (3, 0, 3)

SC_LED               = 4
SC_COLOR_BRIGHT      = (15, 15, 0)
SC_COLOR_DIM         = (3, 3, 0)

READY_LED   = 5
READY_COLOR = (5, 0, 0)

# Inner 3x3 ring on 5x5 grid (rows 1-3, cols 1-3)
INNER_RING = [6, 7, 8, 11, 12, 13, 16, 17, 18]

# Boot status LED positions (top-left corner: LEDs 0, 1, 2)
BOOT_LED_POWER  = 0
BOOT_LED_BATT   = 1
BOOT_LED_READY  = 2

# Row data LED indices for each boot stage (cols 1-4 of that stage's row).
# Indexed by stage number, parallel to SHAPE_LEFT_COL (0, 5, 10, 15, 20).
_BOOT_STAGE_DATA = (
    ( 1,  2,  3,  4),   # stage 0: power / main() started
    ( 6,  7,  8,  9),   # stage 1: brightness (OPT3002)
    (11, 12, 13, 14),   # stage 2: battery (MAX17048)
    (16, 17, 18, 19),   # stage 3: NFC
    (21, 22, 23, 24),   # stage 4: accel
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
            num = HUB_CONFIG.get("num_leds", 25)
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
        Cycle through rows top-to-bottom: TOP_ROW, ROW2, ROW3, ROW4, BOT_ROW, repeat.

        Example:
            leds.animate_rows(self._frame, BLUE)
        """
        rows = (SHAPE_TOP_ROW, SHAPE_ROW2, SHAPE_ROW3, SHAPE_ROW4, SHAPE_BOT_ROW)
        idx = (frame // frames_per_step) % len(rows)
        self.show_shape(rows[idx], color, bg)

    def animate_columns(self, frame, color, bg=OFF, frames_per_step=6):
        """
        Cycle through columns left-to-right: LEFT_COL, COL2, COL3, COL4, RIGHT_COL, repeat.

        Example:
            leds.animate_columns(self._frame, GREEN)
        """
        cols = (SHAPE_LEFT_COL, SHAPE_COL2, SHAPE_COL3, SHAPE_COL4, SHAPE_RIGHT_COL)
        idx = (frame // frames_per_step) % len(cols)
        self.show_shape(cols[idx], color, bg)

    def animate_spin(self, frame, color, bg=OFF, frames_per_step=6):
        """
        Cycle through rotating bars: ROW3, SLASH_L, COL3, SLASH_R, repeat.
        Creates a spinning-line effect through the center of the grid.

        Example:
            leds.animate_spin(self._frame, PURPLE)
        """
        spin = (SHAPE_ROW3, SHAPE_SLASH_L, SHAPE_COL3, SHAPE_SLASH_R)
        idx = (frame // frames_per_step) % len(spin)
        self.show_shape(spin[idx], color, bg)

    def animate_grow(self, frame, color, bg=OFF, frames_per_step=6):
        """
        Expand outward: CENTER, INNER_3x3, BORDER, blank, repeat.
        The "blank" step shows bg only (no foreground shape).

        Example:
            leds.animate_grow(self._frame, CYAN)
        """
        grow = (SHAPE_CENTER, SHAPE_INNER_3x3, SHAPE_BORDER, ())
        idx = (frame // frames_per_step) % len(grow)
        self.show_shape(grow[idx], color, bg)

    def animate_shrink(self, frame, color, bg=OFF, frames_per_step=6):
        """
        Contract inward: BORDER, INNER_3x3, CENTER, blank, repeat.
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
        if stage >= len(SHAPE_LEFT_COL):
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
        Default idle: inner 3x3 ring lit with battery charge color (static).
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