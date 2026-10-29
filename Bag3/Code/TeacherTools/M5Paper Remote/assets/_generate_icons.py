"""Generate 1-bit black/white PNG icons for the M5Paper remote top bar.

Run: python3 _generate_icons.py
Produces gear.png, battery.png, bolt.png in this folder.

Design constraints (e-ink): mode "1" (1-bit), pure black-on-white, NO anti-aliasing or
alpha -- gray/edge pixels would dither badly on the EPD panel. PIL's ImageDraw on a mode "1"
image does not anti-alias, so shapes stay hard-edged.

Convention: background = white (1), ink = black (0).
"""

import math
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
WHITE = 1
BLACK = 0


def _new(w, h):
    img = Image.new("1", (w, h), WHITE)
    return img, ImageDraw.Draw(img)


def gear(path, size=36, teeth=8):
    """Solid gear silhouette: toothed disc with a round center hole."""
    img, d = _new(size, size)
    cx = cy = (size - 1) / 2.0
    r_body = size * 0.34      # main disc radius
    r_tooth = size * 0.48     # tooth tip radius
    r_hole = size * 0.14      # center hole radius
    r_base = r_body * 0.85    # teeth start slightly inside the disc edge
    tooth_half = size * 0.085  # fixed half-width (px) -> straight, parallel sides

    # Teeth as straight-sided rectangles (perpendicular offset = fixed pixel width).
    for i in range(teeth):
        a = math.radians(i * (360.0 / teeth))
        rad_dir = (math.cos(a), math.sin(a))
        perp = (-math.sin(a), math.cos(a))
        pts = []
        for sign, rad in ((-1, r_base), (1, r_base), (1, r_tooth), (-1, r_tooth)):
            px = cx + rad * rad_dir[0] + sign * tooth_half * perp[0]
            py = cy + rad * rad_dir[1] + sign * tooth_half * perp[1]
            pts.append((px, py))
        d.polygon(pts, fill=BLACK)

    # Body disc.
    d.ellipse([cx - r_body, cy - r_body, cx + r_body, cy + r_body], fill=BLACK)
    # Center hole (white).
    d.ellipse([cx - r_hole, cy - r_hole, cx + r_hole, cy + r_hole], fill=WHITE)

    img.save(path)
    return img


def battery(path, w=46, h=22, border=2, nub_w=4):
    """Horizontal battery SHELL outline only (fill bar is drawn in code)."""
    img, d = _new(w, h)
    body_w = w - nub_w
    # Outer body outline, `border` px thick.
    for i in range(border):
        d.rectangle([i, i, body_w - 1 - i, h - 1 - i], outline=BLACK)
    # Positive terminal nub on the right, vertically centered.
    nub_h = h // 2
    nub_y0 = (h - nub_h) // 2
    d.rectangle([body_w, nub_y0, w - 1, nub_y0 + nub_h - 1], fill=BLACK)
    img.save(path)
    return img


def bolt(path, w=12, h=16):
    """Charging indicator: WHITE lightning bolt on a BLACK background.

    Drawn over the battery's solid-black fill, so the bolt must be white to show.
    """
    img = Image.new("1", (w, h), BLACK)
    d = ImageDraw.Draw(img)
    # Zig-zag bolt polygon (proportional to canvas), in white.
    pts = [
        (w * 0.58, 0),
        (w * 0.05, h * 0.58),
        (w * 0.42, h * 0.58),
        (w * 0.30, h),
        (w * 0.95, h * 0.38),
        (w * 0.55, h * 0.38),
    ]
    d.polygon(pts, fill=WHITE)
    img.save(path)
    return img


def signal(path, level, bars=4, bar_w=7, gap=4, min_h=10, step=8):
    """Ascending-bars signal icon. `level` (0..bars-1) bars are filled solid
    black; the rest are drawn as hollow outlines. Geometry MUST match
    config.py SIGNAL_* constants and ui._draw_signal_primitive_at().
    """
    w = bars * bar_w + (bars - 1) * gap
    h = min_h + (bars - 1) * step
    img, d = _new(w, h)
    for i in range(bars):
        bh = min_h + i * step
        x0 = i * (bar_w + gap)
        y0 = h - bh
        if i <= level:
            d.rectangle([x0, y0, x0 + bar_w - 1, h - 1], fill=BLACK)
        else:
            d.rectangle([x0, y0, x0 + bar_w - 1, h - 1], outline=BLACK)
    img.save(path)
    return img


def main():
    gear(os.path.join(HERE, "gear.png"))
    battery(os.path.join(HERE, "battery.png"))
    bolt(os.path.join(HERE, "bolt.png"))
    for level in range(4):
        signal(os.path.join(HERE, "signal-%d.png" % level), level)
    names = ("gear.png", "battery.png", "bolt.png",
             "signal-0.png", "signal-1.png", "signal-2.png", "signal-3.png")
    for name in names:
        p = os.path.join(HERE, name)
        im = Image.open(p)
        print(name, im.size, im.mode)


if __name__ == "__main__":
    main()
