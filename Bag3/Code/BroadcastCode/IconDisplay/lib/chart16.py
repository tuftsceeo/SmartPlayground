"""
chart16.py -- countable displays for early-years games: a block graph, a
pictograph built from the wand's own 5x5 glyphs, a 3x3 glyph grid, and a
plain line graph.

Built on draw16 (primitives) and fed the SHAPE_* tuples from shapes.py, which
are the display's copy of the wand's leds.py glyph table. Passing those
through unscaled means a heart on the panel is pixel-for-pixel the heart on
the wand -- for children still building abstraction, the same picture in both
places is doing real work, so nothing here redraws its own version of one.

WHAT FITS, which decides the shape of this module:

    5x5 glyphs, 3 across     3*5 = 15 of 16     -> fits, 1 spare row/column
    the same with any gap    3*5 + 2 = 17       -> DOES NOT FIT
    5x5 glyphs, 2 across     5*2 + 1 = 11       -> fits with room to spare
    2-row blocks, 1-row gap  5 units = 14 rows  -> counts to FIVE

That second line is the one that shapes everything else. Every SHAPE_* fills
all five of its rows and columns -- a star is a point on its top row and a
point on its bottom row -- so two of them placed 5 apart touch, and three
stacked identical glyphs read as one tall shape rather than three things.
Counting needs a gap, a gap needs 17 rows, and there are 16.

So the split is:

    counting identical pictures  -> count_glyphs(), 2x2 with real gaps, to 4
    counting past four           -> blocks(), which can carry a glyph label
                                    per bar so a team keeps its picture
    nine DISTINCT glyphs         -> grid(), no gaps, where different shapes
                                    and colours do the separating

grid() is deliberately not offered as a way to count nine identical things;
it cannot be made to work at this size.

Everything writes into a 768-byte frame (normally panel.src) and flushes
nothing -- compose, then draw16.show(panel) once. Coordinates are (row, col)
from the top-left, as everywhere else.
"""

import draw16

CELL = 5          # a wand glyph is 5x5, and is never scaled here
GRID_N = 3        # 3x3 glyphs fit only because they touch
COUNT_CAP = 4     # identical glyphs that fit WITH gaps, so they stay countable
BLOCK_CAP = 5     # countable blocks per bar at the default size

W = draw16.W
H = draw16.H


def glyph5(src, row, col, shape, color):
    """One wand glyph at native 5x5, top-left at (row, col).

    `shape` is a flat index tuple into a 5x5 grid -- the SHAPE_* constants in
    shapes.py, exactly as the wand's show_shape() reads them. Unscaled on
    purpose: shapes.draw_shape() blows one up 3x to fill the panel, which is
    the opposite of what counting several of them needs.
    """
    for idx in shape:
        if 0 <= idx < CELL * CELL:
            draw16.px(src, row + idx // CELL, col + idx % CELL, color)


# ─── 3x3 glyph grid ─────────────────────────────────────────────────────

def grid(src, cells, row0=0, col0=0):
    """Up to nine wand glyphs in a 3x3 arrangement.

    `cells` is nine entries, row-major, each either (shape, color) or None
    for an empty cell. Shorter lists just leave the rest empty, so a three
    letter word is cells for row 1 and None elsewhere -- or pass three and
    set row0=5 to centre one row.

    The cells touch: 15 of the 16 columns are glyph, so a separator would
    have to eat a glyph's edge. Give adjacent cells different colours when
    they need to read apart.
    """
    for i, entry in enumerate(cells):
        if entry is None:
            continue
        shape, color = entry
        r = row0 + (i // GRID_N) * CELL
        c = col0 + (i % GRID_N) * CELL
        glyph5(src, r, c, shape, color)


def grid_row(src, entries, row=CELL, col0=0):
    """One row of up to three glyphs -- a 3 character word or numeral.

    Defaults to the middle band, which is where a single row wants to sit on
    a 16-row panel.
    """
    for i, entry in enumerate(entries[:GRID_N]):
        if entry is not None:
            shape, color = entry
            glyph5(src, row, col0 + i * CELL, shape, color)


# ─── pictograph: count things with pictures of the thing ────────────────

def count_glyphs(src, n, shape, color, gap=2, empty=None):
    """Count one quantity as up to four copies of its own picture.

    Laid out 2x2 with real gaps between them, because that is the largest
    arrangement of 5x5 glyphs that stays countable: three across needs 17 of
    16 columns, and glyphs placed 5 apart touch and merge into one shape.

    Fills left-to-right, top row first, the way a child reading a page
    counts. `empty` optionally outlines the slots not yet earned, which
    turns "we have two" into "we need two more".

    Returns the count clamped away, or 0.
    """
    span = CELL * 2 + gap
    row0 = (H - span) // 2
    col0 = (W - span) // 2
    lost = n - COUNT_CAP if n > COUNT_CAP else 0
    shown = COUNT_CAP if n > COUNT_CAP else n
    for k in range(COUNT_CAP):
        r = row0 + (k // 2) * (CELL + gap)
        c = col0 + (k % 2) * (CELL + gap)
        if k < shown:
            glyph5(src, r, c, shape, color)
        elif empty is not None:
            draw16.frame(src, r, c, r + CELL - 1, c + CELL - 1, empty)
    return lost


# ─── block graph: the kindergarten bar chart ────────────────────────────

def blocks(src, values, colors, cap=BLOCK_CAP, block_h=2, gap_v=1, gap_h=2,
           empty=None, labels=None):
    """Bars made of separate countable blocks, growing from the bottom.

    Discrete blocks rather than a solid bar so the height can be COUNTED
    rather than compared against the other bar -- that is the whole point at
    this age, and it is also what lets a bar go past the four that pictures
    manage.

    labels  optional (shape, color) per bar, drawn as a 5x5 wand glyph above
            it, so a team keeps the same picture here that its wand shows.
            Costs the top 5 rows, which drops the bar to four blocks -- pass
            cap=4 with it.
    empty   optional colour for the not-yet-earned blocks, drawn as a dim
            outline, turning "we have three" into "we need two more".

    Returns the count clamped away, or 0.
    """
    n = len(values)
    if n == 0:
        return 0
    bar_w = (W - (n - 1) * gap_h) // n
    if bar_w < 1:
        bar_w = 1
    total = n * bar_w + (n - 1) * gap_h
    col0 = (W - total) // 2
    floor_row = H - 1
    # labelled bars give up the top CELL rows to the glyph
    top = CELL if labels is not None else 0

    lost = 0
    for i in range(n):
        value = values[i]
        if value > cap:
            lost += value - cap
            value = cap
        c0 = col0 + i * (bar_w + gap_h)
        c1 = c0 + bar_w - 1

        if labels is not None and i < len(labels) and labels[i] is not None:
            shape, lcolor = labels[i]
            # centre the 5-wide glyph over its bar, clipped to the panel
            gcol = c0 + (bar_w - CELL) // 2
            if gcol < 0:
                gcol = 0
            elif gcol + CELL > W:
                gcol = W - CELL
            glyph5(src, 0, gcol, shape, lcolor)

        for k in range(cap):
            r1 = floor_row - k * (block_h + gap_v)
            r0 = r1 - block_h + 1
            if r0 < top:
                break
            if k < value:
                draw16.rect(src, r0, c0, r1, c1, colors[i])
            elif empty is not None:
                draw16.frame(src, r0, c0, r1, c1, empty)
    return lost


# ─── line graph ─────────────────────────────────────────────────────────

def line_graph(src, values, color, vmax=None, baseline=None):
    """A plain polyline of up to 16 samples, oldest at the left.

    The least concrete thing in this module -- it asks a reader to map
    position to quantity, which is the skill the other two are still
    building. Reach for it when the shape over time is the point.
    """
    if not values:
        return
    if vmax is None:
        vmax = max(values)
    if vmax <= 0:
        vmax = 1
    pts = values[-W:]
    step = 1 if len(pts) >= W else max(1, W // len(pts))

    if baseline is not None:
        draw16.rect(src, H - 1, 0, H - 1, W - 1, baseline)

    prev = None
    for i, v in enumerate(pts):
        col = i * step
        if col > W - 1:
            break
        if v < 0:
            v = 0
        row = H - 1 - int((float(v) / vmax) * (H - 1))
        if prev is not None:
            draw16.line(src, prev[0], prev[1], row, col, color)
        else:
            draw16.px(src, row, col, color)
        prev = (row, col)
