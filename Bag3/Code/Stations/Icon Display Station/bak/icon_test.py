"""
Icon Display Bring-Up — Serpentine Grid + Scaled Shapes
============================================================
Board: Seeed XIAO ESP32-C6, same LED Driver Board as Slide Score
Station. Matrix: BTF-LIGHTING WS2812B 5050 SMD, 16x16 (256px),
believed wired serpentine (not confirmed pixel-by-pixel yet).

Purpose: exercise the serpentine-addressing idea before committing to
it in a real main.py. Draws:
  1. A row-by-row rainbow -- the fastest way to SEE whether the
     serpentine guess below (row-major, boustrophedon) is right.
     Clean solid rows = correct. Diagonal streaks/garbled colors =
     wrong axis or wrong start corner -- flip pixel_index() below.
  2. Three shapes scaled up 3x from the 5x5 grid in lib/leds.py
     (HEART, STAR, ARROW_R) -- the arrow is asymmetric on purpose, so
     a backwards/rotated result is obvious at a glance.

Not a station -- no hubtype.py/espnow_manager. Copy up temporarily.

Brightness: kept dim (ICON_INTENSITY below) per the readme's design
guidance -- a static icon has no reason to run at the level only
proven safe for a few seconds under voltage_test.py.

Run from the REPL:
    import icon_test
    icon_test.main()
"""

import machine
import neopixel
import time

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
DATA_PIN = 0    # GPIO0 = A0 screw terminal on the LED Driver Board.
                 # GPIO23 = D5 Grove connector, if wired there instead.
GRID_W = 16
GRID_H = 16
NUM_PIXELS = GRID_W * GRID_H

ICON_INTENSITY = 0.2
HOLD_MS = 3000


def pixel_index(col, row):
    """
    Row-major serpentine, starting top-left, alternating direction
    each row -- the common wiring for flexible WS2812 matrix panels
    (unlike Slide Score Station's column-major bar graph). If the
    rainbow test shows diagonal streaks instead of clean rows, this
    matrix is wired by column instead -- swap in Slide Score
    Station's version (base = col * GRID_H; + row, or
    + (GRID_H - 1 - row) on odd columns).
    """
    c = col if (row % 2 == 0) else (GRID_W - 1 - col)
    return row * GRID_W + c


# ─────────────────────────────────────────────
# HARDWARE
# ─────────────────────────────────────────────
strip = neopixel.NeoPixel(machine.Pin(DATA_PIN), NUM_PIXELS)


def _scale(rgb):
    return tuple(int(c * ICON_INTENSITY) for c in rgb)


def clear():
    for i in range(NUM_PIXELS):
        strip[i] = (0, 0, 0)
    strip.write()


# ─────────────────────────────────────────────
# SHAPES -- exact 5x5 index tuples from lib/leds.py, scaled 3x to fit
# the 16x16 grid (5*3=15px, leaving a 1px margin at the bottom/right).
# ─────────────────────────────────────────────
SRC_SIZE = 5
BLOCK    = 3

SHAPE_HEART   = (1, 3, 5, 6, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 22)
SHAPE_STAR    = (2, 5, 7, 9, 11, 12, 13, 15, 17, 19, 22)
SHAPE_ARROW_R = (2, 7, 8, 10, 11, 12, 13, 14, 17, 18, 22)  # asymmetric -- shows wiring mistakes clearly

RAINBOW_ROWS = [
    (255, 0, 0), (255, 100, 0), (200, 200, 0),
    (0, 255, 0), (0, 0, 255), (130, 0, 255),
]


def scale_shape(shape_indices):
    """5x5 SHAPE_* tuple -> set of (row, col) cells on the 16x16 grid."""
    cells = set()
    for idx in shape_indices:
        sr, sc = divmod(idx, SRC_SIZE)
        for dr in range(BLOCK):
            for dc in range(BLOCK):
                cells.add((sr * BLOCK + dr, sc * BLOCK + dc))
    return cells


def draw_shape(shape_indices, color):
    cells = scale_shape(shape_indices)
    rgb = _scale(color)
    for row in range(GRID_H):
        for col in range(GRID_W):
            strip[pixel_index(col, row)] = rgb if (row, col) in cells else (0, 0, 0)
    strip.write()


def draw_pixels(pixels):
    """
    Draw a flat 256-entry (r,g,b) tuple, row-major top-left -- exactly
    what image_to_icon.py writes out. Runs it through pixel_index() and
    ICON_INTENSITY like everything else here.

    Example:
        import cat_icon
        icon_test.draw_pixels(cat_icon.ICON)
    """
    for row in range(GRID_H):
        for col in range(GRID_W):
            strip[pixel_index(col, row)] = _scale(pixels[row * GRID_W + col])
    strip.write()


# ─────────────────────────────────────────────
# WIRING CHECK -- row-by-row rainbow
# ─────────────────────────────────────────────
def rainbow_rows(hold_ms=HOLD_MS):
    """Light each row solid in a rotating color. Clean bands = the
    serpentine guess above is right. Diagonal/garbled = flip it."""
    for row in range(GRID_H):
        rgb = _scale(RAINBOW_ROWS[row % len(RAINBOW_ROWS)])
        for col in range(GRID_W):
            strip[pixel_index(col, row)] = rgb
    strip.write()
    print("  Rows lit -- clean horizontal bands = serpentine guess is correct.")
    time.sleep_ms(hold_ms)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("\n" + "=" * 50)
    print("  Icon Display Bring-Up -- Serpentine + Scaled Shapes")
    print("  %dx%d grid, intensity %.0f%%" % (GRID_W, GRID_H, ICON_INTENSITY * 100))
    print("=" * 50 + "\n")

    try:
        print("  1/4: row rainbow (wiring check)")
        rainbow_rows()

        print("  2/4: heart")
        draw_shape(SHAPE_HEART, (200, 0, 60))
        time.sleep_ms(HOLD_MS)

        print("  3/4: star")
        draw_shape(SHAPE_STAR, (200, 160, 0))
        time.sleep_ms(HOLD_MS)

        print("  4/4: arrow (should point right)")
        draw_shape(SHAPE_ARROW_R, (0, 140, 200))
        time.sleep_ms(HOLD_MS)
    except KeyboardInterrupt:
        print("\n  Stopped by user.")
    finally:
        clear()
        print("  Cleared.")


if __name__ == "__main__":
    main()
