"""
preview.py -- render a 16x16 authored ICON tuple as a simulated-LED PNG:
square cells behind a dark diffuser, coloured with the same WS2812 model as
the web editor's swatches (webapp/js/pipeline/ledGamut.js ledSwatchHex) and
the Simulator's icon display.

Colour is the LED's emitted light at full duty, independent of intensity,
the way the editor shows it. Good for silhouette, thin-feature survival and
relative colour; sign off on absolute hue only from the real matrix.
"""

from PIL import Image, ImageDraw

from raster import W, H

PREVIEW_SCALE = 24
GAP = 2
BG = (10, 10, 11)
OFF = (29, 29, 33)

# xy chromaticity and luminous intensity (mcd) of each WS2812B primary.
_PRIMARIES = ((0.7006, 0.2993, 400.0), (0.0743, 0.8338, 1150.0), (0.1241, 0.0578, 250.0))
_PRIM_XYZ = [((x / y) * iv, iv, ((1 - x - y) / y) * iv) for x, y, iv in _PRIMARIES]
_Y_WHITE = sum(p[1] for p in _PRIM_XYZ)


def led_screen_rgb(duty):
    """Authored duty (r,g,b) -> sRGB bytes of the light the panel emits."""
    X, Y, Z = (sum(duty[j] / 255.0 * _PRIM_XYZ[j][i] for j in range(3)) / _Y_WHITE for i in range(3))
    lin = (3.2406 * X - 1.5372 * Y - 0.4986 * Z,
           -0.9689 * X + 1.8758 * Y + 0.0415 * Z,
           0.0557 * X - 0.204 * Y + 1.057 * Z)
    out = []
    for c in lin:
        v = max(0.0, min(1.0, c))
        v = 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055
        out.append(round(v * 255))
    return tuple(out)


def render_preview(pixels, intensity=None, out_path=None):
    """pixels: flat 256 (r,g,b) authored tuples, row-major top-left.
    `intensity` is accepted for callers but does not dim the render.
    Returns a PIL Image; also writes it to out_path if given."""
    size = W * PREVIEW_SCALE
    img = Image.new("RGB", (size, size), BG)
    draw = ImageDraw.Draw(img)
    for row in range(H):
        for col in range(W):
            rgb = tuple(pixels[row * W + col])
            fill = OFF if rgb == (0, 0, 0) else led_screen_rgb(rgb)
            x = col * PREVIEW_SCALE + GAP // 2
            y = row * PREVIEW_SCALE + GAP // 2
            draw.rounded_rectangle((x, y, x + PREVIEW_SCALE - GAP - 1, y + PREVIEW_SCALE - GAP - 1), radius=3, fill=fill)
    if out_path:
        img.save(out_path)
    return img
