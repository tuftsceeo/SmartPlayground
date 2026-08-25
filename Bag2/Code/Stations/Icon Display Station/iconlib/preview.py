"""
preview.py -- render a 16x16 authored ICON tuple as a simulated-LED PNG,
through the SAME forward model (§Root cause) the editor's live canvas
uses, so it stops lying the way the raw-value ANSI preview used to.

Honest about what it's good for: cell-on/off, silhouette, thin-feature
survival, relative brightness ordering, quantization damage. NOT reliable
for absolute hue -- WS2812 dies are narrowband/off-primary in a way no
sRGB monitor simulation captures. Sign off on structure here; sign off on
hue only from the real matrix.
"""

from PIL import Image, ImageDraw, ImageFilter

from ledcolor import predict_led_appearance
from raster import W, H

PREVIEW_SCALE = 24
DOT_RADIUS = 8
BLOOM_RADIUS = 3
BG = (10, 10, 12)


def render_preview(pixels, intensity, out_path=None):
    """pixels: flat 256 (r,g,b) authored tuples, row-major top-left.
    Returns a PIL Image; also writes it to out_path if given."""
    size = W * PREVIEW_SCALE
    img = Image.new("RGB", (size, size), BG)
    dots = Image.new("RGB", (size, size), (0, 0, 0))
    draw = ImageDraw.Draw(dots)

    for row in range(H):
        for col in range(W):
            rgb = pixels[row * W + col]
            if rgb == (0, 0, 0):
                continue
            seen = predict_led_appearance(rgb, intensity)
            cx = col * PREVIEW_SCALE + PREVIEW_SCALE // 2
            cy = row * PREVIEW_SCALE + PREVIEW_SCALE // 2
            draw.ellipse((cx - DOT_RADIUS, cy - DOT_RADIUS, cx + DOT_RADIUS, cy + DOT_RADIUS), fill=seen)

    bloom = dots.filter(ImageFilter.GaussianBlur(BLOOM_RADIUS))
    out = Image.blend(img, bloom, 0.35)
    # simple screen-blend of the sharp dots over the bloomed background, clamped
    px_out = out.load()
    px_dots = dots.load()
    for y in range(size):
        for x in range(size):
            bo = px_out[x, y]
            do = px_dots[x, y]
            px_out[x, y] = tuple(min(255, bo[c] + do[c]) for c in range(3))

    if out_path:
        out.save(out_path)
    return out
