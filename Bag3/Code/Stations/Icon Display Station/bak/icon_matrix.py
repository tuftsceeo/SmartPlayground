"""
icon_matrix.py -- NeoPixel driver: serpentine addressing, the intensity
LUT, and a fast bulk-draw path. See the top-level plan
("ESP32-C6 firmware") for the design rationale.

TRUNCATION IS CANONICAL: the LUT is `lut[i] = int(i * intensity)`, matching
iconlib/ledcolor.py's predict_led_appearance() and the webapp's
js/pipeline/ledcolor.js exactly (round() is NOT used -- MicroPython's
round() rounds half away from zero while CPython 3 rounds half to even, so
a round-based scale would silently diverge between the toolchain and the
device; see readme.md and the plan's "Firmware canon: truncation").
"""

import machine
import neopixel
from array import array

W = 16
H = 16
N = W * H
DATA_PIN = 0
DEFAULT_INTENSITY = 0.30
MAX_INTENSITY = 0.50  # readme: 50% cleared a full 12V rainbow ramp; nothing
                       # above that has been characterized -- see plan risks.


"""
PANEL ORIENTATION
=================
MIRROR_X defaults True because that is what THIS panel needs: with it False
the image came out cleanly left-right flipped (verified against the stem/leaf
asymmetry of the grapes icon -- on screen the leaf sits right of the stem, on
the panel it appeared left of it). Set it False for a panel wired the other
way round.

Why the original bring-up test did not catch this: icon_test.py's row-rainbow
lights every row a SOLID colour, and a horizontal mirror is invisible to that
test -- a mirrored solid row is still a solid row. It validated the serpentine
*phase* (rows are clean, not zigzag-torn), never the start corner. An earlier
comment here claimed "confirmed wiring", which overstated what that test
could show.

A clean whole-image mirror (rather than per-row zigzag tearing) is itself the
diagnostic: the serpentine phase is right and only the starting corner is
flipped.
"""
MIRROR_X = True   # True = data-in column order is reversed (this panel)
FLIP_Y = False    # True = row 0 is at the bottom


def pixel_index(col, row, mirror_x=None, flip_y=None):
    """Logical (col,row) from top-left -> serpentine strip index."""
    mx = MIRROR_X if mirror_x is None else mirror_x
    fy = FLIP_Y if flip_y is None else flip_y
    if mx:
        col = W - 1 - col
    if fy:
        row = H - 1 - row
    c = col if (row % 2 == 0) else (W - 1 - col)
    return row * W + c


class Matrix:
    def __init__(self, pin=DATA_PIN, intensity=DEFAULT_INTENSITY):
        self.np = neopixel.NeoPixel(machine.Pin(pin), N)
        # MicroPython's neopixel.py exposes .ORDER (per-channel buffer slot)
        # and .buf (the raw bytearray) on the ports that support them.
        # ORDER[i] is the buffer slot for input channel i, e.g. (1,0,2,3)
        # means the wire order is GRB. Fall back to the slow per-pixel path
        # if either isn't present -- see _draw_slow.
        order = getattr(self.np, "ORDER", None)
        buf = getattr(self.np, "buf", None)
        self.fast = order is not None and isinstance(buf, bytearray) and len(buf) >= N * 3
        if self.fast:
            self.sr, self.sg, self.sb = order[0], order[1], order[2]
            self.buf = buf
        # Precomputed destination byte offset (into .buf) for each logical
        # pixel 0..N-1, row-major -- folds the serpentine permutation into
        # a single table lookup instead of a per-pixel pixel_index() call.
        # Rebuilt by set_orientation() so a panel wired the other way round
        # needs a command, not a code edit.
        self.mirror_x = MIRROR_X
        self.flip_y = FLIP_Y
        self.off = None
        self._build_offsets()
        self.lut = bytearray(256)
        self.src = bytearray(N * 3)  # last authored (unscaled) frame
        self.intensity = 0.0
        self.set_intensity(intensity)
        self.clear()

    def set_intensity(self, value):
        v = 0.0 if value is None or value < 0 else min(float(value), MAX_INTENSITY)
        self.intensity = v
        lut = self.lut
        for i in range(256):
            lut[i] = int(i * v)  # truncation -- see module docstring
        return v

    def _build_offsets(self):
        self.off = array(
            "H",
            (3 * pixel_index(p % W, p // W, self.mirror_x, self.flip_y) for p in range(N)),
        )

    def set_orientation(self, mirror_x=None, flip_y=None):
        """Change panel orientation at runtime and redraw the cached frame.
        See the MIRROR_X note at the top of this module."""
        if mirror_x is not None:
            self.mirror_x = bool(mirror_x)
        if flip_y is not None:
            self.flip_y = bool(flip_y)
        self._build_offsets()
        return self.mirror_x, self.flip_y

    def draw_bytes(self, src):
        """src: 768 bytes, authored (unscaled) RGB triples, row-major top-left."""
        if len(src) != N * 3:
            raise ValueError("frame must be %d bytes, got %d" % (N * 3, len(src)))
        if src is not self.src:
            self.src[:] = src
        if self.fast:
            self._draw_fast(src)
        else:
            self._draw_slow(src)
        self.np.write()

    def redraw(self):
        """Re-apply the last authored frame at the current intensity --
        used after set_intensity() so a brightness change doesn't need the
        768 authored bytes re-sent over serial."""
        if self.fast:
            self._draw_fast(self.src)
        else:
            self._draw_slow(self.src)
        self.np.write()

    def _draw_fast(self, src):
        buf = self.buf
        lut = self.lut
        off = self.off
        sr, sg, sb = self.sr, self.sg, self.sb
        s = 0
        for p in range(N):
            d = off[p]
            buf[d + sr] = lut[src[s]]
            buf[d + sg] = lut[src[s + 1]]
            buf[d + sb] = lut[src[s + 2]]
            s += 3

    def _draw_slow(self, src):
        np_ = self.np
        lut = self.lut
        off = self.off
        s = 0
        for p in range(N):
            np_[off[p] // 3] = (lut[src[s]], lut[src[s + 1]], lut[src[s + 2]])
            s += 3

    def set_pixels(self, triples):
        """triples: iterable of (idx, r, g, b) -- sparse per-pixel update,
        against the cached authored frame (so a later redraw()/intensity
        change stays consistent)."""
        for idx, r, g, b in triples:
            if idx < 0 or idx >= N:
                continue
            o = idx * 3
            self.src[o] = r
            self.src[o + 1] = g
            self.src[o + 2] = b
        self.draw_bytes(self.src)

    def clear(self):
        for i in range(N * 3):
            self.src[i] = 0
        if self.fast:
            for i in range(len(self.buf)):
                self.buf[i] = 0
            self.np.write()
        else:
            for i in range(N):
                self.np[i] = (0, 0, 0)
            self.np.write()
