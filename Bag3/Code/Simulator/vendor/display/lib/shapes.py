"""
5x5 glyph data for the Icon Display, and the two helpers that put it on the
16x16 panel.

PEER: Bag3/Code/BroadcastCode/BroadcastBox/MockWand/lib/leds.py holds the master copy of
the SHAPE_* tuples below (its "5x5 GRID SHAPES" section) -- keep the two in
sync. A slight drift here is tolerated for now; deduplicating the data is
planned for after the MVP is proven, not before.

Data only below the shape table: no LED/NeoPixel driver. draw_shape() and
wifi_animate() give the display the same glyph vocabulary the wand uses for
pull-mode status, built on icon_store.scale_into(), which already does the
integer 3x centred scale from a 5x5 frame onto this 16x16 panel.
"""

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

# Wifi signal strength, 0-2 arcs over a base dot. Used as a cycling
# "trying to connect" animation by wifi_animate(); the last frame doubles
# as the still image for a connect failure (red = no AP at all, orange =
# AP there but the pull was refused). See WIFI_FRAMES below.
SHAPE_WIFI_0             = (22,)
SHAPE_WIFI_1             = (11, 12, 13, 22)
SHAPE_WIFI_2             = (0, 1, 2, 3, 4, 11, 12, 13, 22)
WIFI_FRAMES              = (SHAPE_WIFI_0, SHAPE_WIFI_1, SHAPE_WIFI_2)
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


# ─────────────────────────────────────────────
# Painting a 5x5 glyph onto the 16x16 panel
# ─────────────────────────────────────────────
import icon_store
from icon_matrix import W, H

_GLYPH_W = 5
_GLYPH_H = 5
_glyph_buf = bytearray(_GLYPH_W * _GLYPH_H * 3)


def draw_shape(panel, shape, rgb):
    """Paint a 5x5 SHAPE_* glyph onto the panel, scaled and centred.

    `shape` is a flat index tuple into a 5x5 grid, exactly as leds.py's
    show_shape() reads them on the wand. Every other index is left dark.
    """
    r, g, b = rgb
    buf = _glyph_buf
    for i in range(len(buf)):
        buf[i] = 0
    for idx in shape:
        if 0 <= idx < _GLYPH_W * _GLYPH_H:
            o = idx * 3
            buf[o] = r
            buf[o + 1] = g
            buf[o + 2] = b
    icon_store.scale_into(buf, _GLYPH_W, _GLYPH_H, panel.src, W, H)
    panel.draw_bytes(panel.src)


def wifi_animate(panel, frame, rgb, frames_per_step=3):
    """Cycle the wifi bars 0-1-2-0..., mirroring leds.wifi_animate().

    `frame` is a free-running tick from the caller, so this stays a pure
    render call with no sleeps. Pass frames_per_step=1 during a scan (a scan
    blocks for ~2.5s per call, so each call advances a bar -- a countdown of
    the scan budget) and 3 during a join (one call per ~200ms poll, so a bar
    every ~600ms reads as a smooth cycle). See MockWand/main.py's
    _pull_status() for the wand's identical timing rationale.
    """
    step = (frame // frames_per_step) % len(WIFI_FRAMES)
    draw_shape(panel, WIFI_FRAMES[step], rgb)


# ══════════════════════════════════════════════
# PER-CELL DRAWING
# ══════════════════════════════════════════════
# draw_shape() paints one glyph in one colour, which is every case except the
# two below: the boot screen lights each cell its own colour, and both keep
# earlier cells lit while later ones change. So those hold the 5x5 frame
# between calls rather than rebuilding it from a shape each time.

def draw_cells(panel, cells, clear=True):
    """Paint individual 5x5 cells, each its own colour, scaled and centred.

    `cells` is any iterable of (index, (r, g, b)). With clear=False the
    frame keeps whatever was already in it, so a caller can light one more
    cell without redrawing the rest.
    """
    buf = _glyph_buf
    if clear:
        for i in range(len(buf)):
            buf[i] = 0
    for idx, rgb in cells:
        if 0 <= idx < _GLYPH_W * _GLYPH_H:
            o = idx * 3
            buf[o], buf[o + 1], buf[o + 2] = rgb
    icon_store.scale_into(buf, _GLYPH_W, _GLYPH_H, panel.src, W, H)
    panel.draw_bytes(panel.src)


def idle_default(panel, rgb):
    """The inner 3x3 lit, static -- what MockWand shows when it is waiting.

    The wand colours this square by battery charge (leds.idle_default()).
    This device has no battery, so the caller passes the colour; green means
    the same thing on both: powered, idle, nothing wrong.

    Static on purpose. An animation here would be a second thing writing the
    panel every frame, and this device shares those 256 pixels with the icon
    editor over USB.
    """
    draw_cells(panel, [(i, rgb) for i in SHAPE_INNER_3x3])


# ══════════════════════════════════════════════
# BOOT SCREEN
# ══════════════════════════════════════════════
# Mirrors MockWand's leds.boot_stage_*(): the left column is one cell per
# boot stage, and the four cells to its right carry that stage's data. Same
# colour language on both devices -- dim white means started, green ok, amber
# a non-fatal problem, red a fatal one -- so the same glance reads either.
#
# The stages differ because the devices differ. The wand's are power,
# brightness, battery, NFC, accel; this device has no battery, no light
# sensor and no accelerometer, and has a panel and a USB link instead.

STAGE_ROWS = (
    (1, 2, 3, 4),        # stage 0: power / main() reached   (row: radio)
    (6, 7, 8, 9),        # stage 1: panel
    (11, 12, 13, 14),    # stage 2: storage                  (row: game count)
    (16, 17, 18, 19),    # stage 3: USB link
    (21, 22, 23, 24),    # stage 4: card reader
)

WHITE_DIM = (40, 40, 40)
STAGE_OK = (0, 120, 0)
STAGE_WARN = (120, 60, 0)
STAGE_FAIL = (120, 0, 0)


class BootScreen:
    """The five stage cells and their data rows, held across calls.

    Keeps its own cell->colour map because each stage paints only its own
    cells: a stage that finishes must not blank the ones before it, which is
    what makes the panel readable as a record of how far boot got.
    """

    def __init__(self, panel):
        self.panel = panel
        self.cells = {}

    def _paint(self):
        draw_cells(self.panel, self.cells.items())

    def stage_start(self, stage):
        """Dim white: this stage has begun. Left lit if the stage never ends,
        which is exactly what a hang looks like from across the room."""
        if stage < len(SHAPE_LEFT_COL):
            self.cells[SHAPE_LEFT_COL[stage]] = WHITE_DIM
            self._paint()

    def stage_ok(self, stage, row_colors=None):
        """Green, optionally with up to four data cells beside it."""
        self._mark(stage, STAGE_OK, row_colors)

    def stage_warn(self, stage, row_colors=None):
        """Amber: this part did not come up, the device runs without it."""
        self._mark(stage, STAGE_WARN, row_colors)

    def stage_fail(self, stage):
        """Red. Nothing here is fatal today, but the colour is reserved so
        the display cannot say "fine" about something that was not."""
        self._mark(stage, STAGE_FAIL, None)

    def _mark(self, stage, color, row_colors):
        if stage >= len(SHAPE_LEFT_COL):
            return
        self.cells[SHAPE_LEFT_COL[stage]] = color
        if row_colors:
            row = STAGE_ROWS[stage]
            for i in range(len(row_colors)):
                if i < len(row) and row_colors[i]:
                    self.cells[row[i]] = row_colors[i]
        self._paint()

    def clear(self):
        self.cells = {}
        self.panel.clear()
