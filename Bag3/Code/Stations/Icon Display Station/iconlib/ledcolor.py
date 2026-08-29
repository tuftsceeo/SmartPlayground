"""
ledcolor.py -- the forward model: what a byte written to a WS2812 actually
looks like, vs. what an sRGB image byte looks like.

ROOT CAUSE this module exists to fix: every earlier version of this tool
treated `leds.py` byte tuples as if they were sRGB code values (like a PNG
pixel). They are not -- they are linear PWM duty cycle. The real chain is:

    file byte -> x INTENSITY -> int() truncate -> /255 = LINEAR LIGHT -> sRGB-encode -> what the eye sees

Comparing an authored color to a source-image color with one shared OKLab
decode (the sRGB one) silently double-applies or skips a gamma step
depending on which side you're looking at. This module gives two decode
entry points so that never happens by accident:

    oklab_from_srgb(rgb)    -- for PNG/JPEG source pixels (already sRGB)
    oklab_from_linear(rgb)  -- for leds.py / authored LED byte tuples

and a `predict_led_appearance()` that runs a byte tuple through the full
chain above, for previews and the diagnostic table in the design doc.
"""

import math
import os
import sys

_UTIL_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "Utilities"))
if _UTIL_DIR not in sys.path:
    sys.path.append(_UTIL_DIR)
try:
    from color_selection import srgb_to_linear as _srgb_to_linear
except Exception:
    def _srgb_to_linear(c):
        c = c / 255.0
        if c <= 0.04045:
            return c / 12.92
        return ((c + 0.055) / 1.055) ** 2.4

# Rec.601-ish linear luma weights. NOT derived from the palette's own
# per-channel caps (see design doc §Uncertain) -- that would bake in an
# unrelated by-eye tuning decision as if it were photometric fact.
LUMA_W = (0.299, 0.587, 0.114)


def _linear_to_srgb(c):
    """c in [0,1] linear -> [0,1] sRGB-encoded."""
    if c <= 0.0031308:
        v = c * 12.92
    else:
        v = 1.055 * (c ** (1 / 2.4)) - 0.055
    return min(1.0, max(0.0, v))


def _oklab(rl, gl, bl):
    """OKLab from LINEAR-light r,g,b in [0,1]. Shared math for both entry points."""
    l = 0.4122214708 * rl + 0.5363325363 * gl + 0.0514459929 * bl
    m = 0.2119034982 * rl + 0.6806995451 * gl + 0.1073969566 * bl
    s = 0.0883024619 * rl + 0.2817188376 * gl + 0.6299787005 * bl
    l_ = l ** (1 / 3) if l > 0 else 0.0
    m_ = m ** (1 / 3) if m > 0 else 0.0
    s_ = s ** (1 / 3) if s > 0 else 0.0
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b_ok = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return L, a, b_ok


def oklab_from_srgb(rgb):
    """rgb: 0-255 sRGB-encoded byte tuple (a PNG/JPEG source pixel)."""
    r, g, b = rgb
    return _oklab(_srgb_to_linear(r), _srgb_to_linear(g), _srgb_to_linear(b))


def oklab_from_linear(rgb):
    """rgb: 0-255 tuple that IS linear light (a leds.py / authored LED byte).
    No gamma decode -- the byte already *is* the linear value, just scaled
    to 0-255 instead of 0-1."""
    r, g, b = rgb
    return _oklab(r / 255.0, g / 255.0, b / 255.0)


def dE_srgb(c1, c2):
    """OKLab distance between two sRGB-encoded (image) colors."""
    L1, a1, b1 = oklab_from_srgb(c1)
    L2, a2, b2 = oklab_from_srgb(c2)
    return math.sqrt((L1 - L2) ** 2 + (a1 - a2) ** 2 + (b1 - b2) ** 2)


def dE_linear(c1, c2):
    """OKLab distance between two linear (LED byte) colors."""
    L1, a1, b1 = oklab_from_linear(c1)
    L2, a2, b2 = oklab_from_linear(c2)
    return math.sqrt((L1 - L2) ** 2 + (a1 - a2) ** 2 + (b1 - b2) ** 2)


def predict_led_appearance(rgb, intensity):
    """
    Run an authored leds.py-convention byte tuple through the full device
    chain and return the sRGB byte tuple an eye would perceive on a
    calibrated monitor: file byte -> xINTENSITY -> truncate -> /255 linear
    -> sRGB-encode. This is what preview.py renders and what the design
    doc's root-cause table checks against.
    """
    out = []
    for c in rgb:
        duty = int(c * intensity)          # device does this (see main.py scale())
        linear = duty / 255.0
        srgb = _linear_to_srgb(linear)
        out.append(int(round(srgb * 255)))
    return tuple(out)


def luma_linear(rgb):
    """Perceived-brightness proxy for an authored (linear) byte tuple, using
    LUMA_W directly on the 0-255 linear values (no gamma involved -- these
    bytes already are linear light)."""
    r, g, b = rgb
    return LUMA_W[0] * r + LUMA_W[1] * g + LUMA_W[2] * b


def purify(rgb):
    """c' = c - min(c), i.e. strip the shared white/gray component so the
    color sits on the fully-saturated shell of the gamut. Returns a 0-255
    int tuple; may be (0,0,0) for a neutral gray input."""
    m = min(rgb)
    return tuple(c - m for c in rgb)


def hue_deg(rgb):
    """Hue angle in degrees [0,360) via a plain RGB max/min hexcone -- used
    only for the brown-band test, not for palette matching (palette
    matching uses ratio/direction, see segment.py propose_color)."""
    r, g, b = (c / 255.0 for c in rgb)
    mx, mn = max(r, g, b), min(r, g, b)
    d = mx - mn
    if d == 0:
        return 0.0
    if mx == r:
        h = ((g - b) / d) % 6
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return h * 60.0


def is_brown(rgb, h_lo=30.0, h_hi=75.0, chroma_max=0.45, lightness_max=0.55):
    """Heuristic brown test on an sRGB source color: hue inside the
    orange/amber band, but low chroma and low lightness -- the combination
    that reads as 'brown' rather than 'saturated orange'. Uses plain HSL
    chroma/lightness (cheap, and this is a coarse gate, not the final
    color decision -- the human overrides in the editor either way)."""
    r, g, b = (c / 255.0 for c in rgb)
    mx, mn = max(r, g, b), min(r, g, b)
    chroma = mx - mn
    lightness = (mx + mn) / 2
    h = hue_deg(rgb)
    return (h_lo <= h <= h_hi) and chroma <= chroma_max and lightness <= lightness_max
