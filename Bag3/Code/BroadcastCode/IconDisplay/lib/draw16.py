"""
draw16.py -- draw shapes and small text straight onto the 16x16 panel at
runtime, for games whose display changes with play rather than swapping
between pre-authored icons.

Where the other two drawing paths stop:
    icon_store.read_icon(name, into=panel.src)  plays back a whole authored
        frame from icons/<name>.py -- every state has to exist as a file.
    shapes.draw_shape(panel, SHAPE_7, rgb)      scales one 5x5 glyph 3x to
        fill the panel -- one digit at a time, so "12" can't be shown.
This module composes a frame in place instead, so a live score, a countdown
or a progress bar doesn't need a file per value.

Everything writes into a 768-byte authored frame -- normally panel.src --
laid out exactly as icons/<name>.py is: row-major from the top-left, three
bytes per pixel, linear PWM duty (NOT sRGB; see iconlib/ledcolor.py in the
Icon Display Station). Values are unscaled: the panel applies INTENSITY when
it draws, so keep authored colours in the same range the icon files use.

Nothing here touches hardware, so none of it reaches the LEDs until the
caller flushes:

    import draw16
    draw16.clear(panel.src)
    draw16.number(panel.src, score, 5, 5, (0, 200, 60))
    draw16.show(panel)

Drawing calls take the buffer rather than the panel, and don't flush on their
own, so a frame built from several calls is written to the strip once instead
of once per shape -- a mid-draw flush is visible as flicker.

COORDINATES ARE (row, col) EVERYWHERE, top-left origin, matching
icon_matrix.pixel_index()'s argument order-of-thought and the icon file
layout. Every function in this module takes them in that order.

THIS MODULE IS FIRMWARE-RESIDENT. code_server.py serves a pulled game its
own file and its icons -- ROLE_FILES has no lib leg, and the staging tree
carries no lib/ -- so a game that arrives over the wire can only import what
was already flashed. A game written against draw16 fails on a display that
predates it, with an ImportError at load rather than anything visible on the
panel. Flash the display before handing out games that use it.
"""

W = 16
H = 16
N = W * H
_STRIDE = W * 3

BLACK = (0, 0, 0)


def _put(src, row, col, r, g, b):
    """Unclipped single-pixel write. Callers clip; this is the inner loop."""
    o = (row * W + col) * 3
    src[o] = r
    src[o + 1] = g
    src[o + 2] = b


def px(src, row, col, color):
    """One pixel, ignored if it falls outside the panel."""
    if 0 <= row < H and 0 <= col < W:
        _put(src, row, col, color[0], color[1], color[2])


def get(src, row, col):
    """The authored colour at (row, col), or BLACK outside the panel."""
    if not (0 <= row < H and 0 <= col < W):
        return BLACK
    o = (row * W + col) * 3
    return (src[o], src[o + 1], src[o + 2])


def clear(src, color=BLACK):
    """Fill the whole frame. Default black = every LED off."""
    r, g, b = color
    if r == 0 and g == 0 and b == 0:
        for i in range(N * 3):
            src[i] = 0
        return
    for i in range(0, N * 3, 3):
        src[i] = r
        src[i + 1] = g
        src[i + 2] = b


def rect(src, r0, c0, r1, c1, color):
    """Filled rectangle, inclusive of both corners, clipped to the panel."""
    if r0 > r1:
        r0, r1 = r1, r0
    if c0 > c1:
        c0, c1 = c1, c0
    r0 = 0 if r0 < 0 else r0
    c0 = 0 if c0 < 0 else c0
    r1 = H - 1 if r1 > H - 1 else r1
    c1 = W - 1 if c1 > W - 1 else c1
    r, g, b = color
    for row in range(r0, r1 + 1):
        for col in range(c0, c1 + 1):
            _put(src, row, col, r, g, b)


def frame(src, r0, c0, r1, c1, color):
    """Rectangle outline, one pixel thick -- a border for a score panel."""
    rect(src, r0, c0, r0, c1, color)
    rect(src, r1, c0, r1, c1, color)
    rect(src, r0, c0, r1, c0, color)
    rect(src, r0, c1, r1, c1, color)


def circle(src, row, col, radius, color):
    """Filled circle centred on (row, col). Centre may be fractional, which
    is how you get a circle centred between cells rather than on one."""
    ellipse(src, row, col, radius, radius, color)


def ellipse(src, row, col, r_row, r_col, color):
    """Filled ellipse with separate row and column radii. Cells count as
    inside when their centre is, matching the authoring tool's rasteriser so
    a shape drawn here lands on the same cells it would in a built icon."""
    if r_row <= 0 or r_col <= 0:
        return
    r, g, b = color
    top = int(row - r_row)
    bottom = int(row + r_row) + 1
    left = int(col - r_col)
    right = int(col + r_col) + 1
    if top < 0:
        top = 0
    if left < 0:
        left = 0
    if bottom > H:
        bottom = H
    if right > W:
        right = W
    for rr in range(top, bottom):
        dy = (rr + 0.5 - row) / r_row
        for cc in range(left, right):
            dx = (cc + 0.5 - col) / r_col
            if dx * dx + dy * dy <= 1.0:
                _put(src, rr, cc, r, g, b)


def line(src, r0, c0, r1, c1, color):
    """Bresenham line, for a needle, a tail or a connecting stroke."""
    dr = abs(r1 - r0)
    dc = abs(c1 - c0)
    sr = 1 if r0 < r1 else -1
    sc = 1 if c0 < c1 else -1
    err = dr - dc
    while True:
        px(src, r0, c0, color)
        if r0 == r1 and c0 == c1:
            return
        e2 = err * 2
        if e2 > -dc:
            err -= dc
            r0 += sr
        if e2 < dr:
            err += dr
            c0 += sc


# ─── 3x5 text ───────────────────────────────────────────────────────────
# Three columns is the narrowest a digit stays legible at, and it is what
# lets a two-digit score fit with room to spare: 3 + 1 + 3 = 7 of 16 columns.
# shapes.py's SHAPE_0..9 are 5x5 scaled 3x, which fills the panel with a
# single character -- fine for a status mark, no use for a score.
#
# One glyph is five bytes, one per row, low three bits, leftmost column is
# the high bit (0b100).
GLYPH_W = 3
GLYPH_H = 5

_CHARS = "0123456789 -:."
_FONT = bytes((
    0b111, 0b101, 0b101, 0b101, 0b111,  # 0
    0b010, 0b110, 0b010, 0b010, 0b111,  # 1
    0b111, 0b001, 0b111, 0b100, 0b111,  # 2
    0b111, 0b001, 0b111, 0b001, 0b111,  # 3
    0b101, 0b101, 0b111, 0b001, 0b001,  # 4
    0b111, 0b100, 0b111, 0b001, 0b111,  # 5
    0b111, 0b100, 0b111, 0b101, 0b111,  # 6
    0b111, 0b001, 0b001, 0b001, 0b001,  # 7
    0b111, 0b101, 0b111, 0b101, 0b111,  # 8
    0b111, 0b101, 0b111, 0b001, 0b111,  # 9
    0b000, 0b000, 0b000, 0b000, 0b000,  # space
    0b000, 0b000, 0b111, 0b000, 0b000,  # -
    0b000, 0b010, 0b000, 0b010, 0b000,  # :
    0b000, 0b000, 0b000, 0b000, 0b010,  # .
))


def glyph(src, char, row, col, color):
    """One 3x5 character, top-left at (row, col). Unknown characters draw
    nothing, so a stray one leaves a gap instead of raising mid-frame."""
    i = _CHARS.find(char)
    if i < 0:
        return
    base = i * GLYPH_H
    r, g, b = color
    for gr in range(GLYPH_H):
        bits = _FONT[base + gr]
        rr = row + gr
        if not (0 <= rr < H):
            continue
        for gc in range(GLYPH_W):
            if bits & (0b100 >> gc):
                cc = col + gc
                if 0 <= cc < W:
                    _put(src, rr, cc, r, g, b)


def text(src, s, row, col, color, spacing=1):
    """A short string, left-aligned at (row, col). Returns the column just
    past the last glyph, so runs in different colours can be chained."""
    for char in s:
        glyph(src, char, row, col, color)
        col += GLYPH_W + spacing
    return col - spacing


def width(s, spacing=1):
    """Width in cells of what text() would draw -- for centring:

        col = (draw16.W - draw16.width(s)) // 2
    """
    if not s:
        return 0
    return len(s) * GLYPH_W + (len(s) - 1) * spacing


def number(src, value, row, col=None, color=(190, 190, 190), spacing=1):
    """An integer, centred horizontally when col is None. Centring is the
    default because a score that grows from 9 to 10 otherwise appears to
    lurch sideways."""
    s = "%d" % value
    if col is None:
        col = (W - width(s, spacing)) // 2
    return text(src, s, row, col, color, spacing)


# ─── flush ──────────────────────────────────────────────────────────────

def show(panel):
    """Push the composed frame to the LEDs.

    panel.draw_bytes() skips its copy when handed the panel's own buffer,
    which is the normal case here, so this is the cheap path.
    """
    panel.draw_bytes(panel.src)
