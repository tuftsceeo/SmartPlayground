"""gen_ring.py -- pre-render the keyboard rings as LVGL RGB565 images.

Host-side tool. Draws each ring (tinted sections + rotated rim labels) once,
so the Dial blits an image instead of re-rendering 30 rotated labels and 10
thick arcs on every redraw. Only the highlight (cell + one white label) is
drawn live by station_ui.

Outputs, in the tree root (deploy them to /flash/ with the .py files):
  kb_letters.bin                240x240 LVGL v9 image, RGB565, 115 KB
  kb_rings.json                 per ring: items and slot [centre, half] deg
  tools/kb_letters.png          preview (host only)

Geometry, colours and slot rules match station_ui.py (KEY_R, BAND_W,
RIM_OUTER, slot_angles, rim_rotation). Fonts: LVGL's Montserrat-Medium and
FontAwesome5 (pass their paths, or they are fetched from LVGL release/v9.2).

    python3 tools/gen_ring.py [--size PX] [Montserrat-Medium.ttf FontAwesome5.woff]

--size must equal the font size station_ui really gets for BODY (28, or the
smaller built-in station_fonts falls back to -- check the "# font:" boot line
or tools/font_probe.py); otherwise the image and the live highlight differ.
"""

import json
import math
import os
import struct
import sys
import urllib.request

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.modules.setdefault("M5", type(sys)("M5"))
import text_entry  # noqa: E402

LVGL_FONTS = "https://raw.githubusercontent.com/lvgl/lvgl/release/v9.2/scripts/built_in_font/"
SS = 4                              # supersampling factor
W = H = 240
RIM_OUTER, BAND_W, KEY_R, BODY = 118, 44, 97, 28
PAGE_BG, CARD_BG, WRITE_BG, INK = 0xF7F7FB, 0xFFFFFF, 0xF2EEFC, 0x231F2E
ICONS = {text_entry.DEL: "", text_entry.DONE: "",
         text_entry.WORDS_ITEM: ""}
# Only the letters ring is pre-rendered: each image is 115 KB of the Dial's
# ~786 KB /flash. The # ring is drawn from live labels (station_ui.IMAGE_RINGS).
RINGS = {
    "letters": list(text_entry.LETTERS),
}


def rgb(c):
    return ((c >> 16) & 255, (c >> 8) & 255, c & 255)


def label(c):
    return "_" if c == text_entry.SPACE else c


def slot_angles(widths, radius, min_gap=2):
    """Same as station_ui.slot_angles."""
    circ = 2 * math.pi * radius
    n = len(widths)
    spare = circ - sum(widths)
    if spare < min_gap * n:
        raise ValueError("ring items do not fit")
    gap = spare / n
    out = []
    pos = -(widths[0] + gap) / 2
    for w in widths:
        slot = w + gap
        out.append((round((pos + slot / 2) * 360 / circ, 3), round(slot * 180 / circ, 3)))
        pos += slot
    return out


def rim_rotation(deg):
    """Same as station_ui.rim_rotation."""
    d = deg % 360
    return d - 360 if d > 180 else d


def fetch(name):
    path = os.path.join(HERE, "tools", ".cache_" + name.replace("+", "_"))
    if not os.path.exists(path):
        urllib.request.urlretrieve(LVGL_FONTS + name, path)
    return path


def render(items, mont, fa, size):
    text_f = ImageFont.truetype(mont, size * SS)
    icon_f = ImageFont.truetype(fa, size * SS)
    font_of = lambda c: icon_f if c in ICONS else text_f
    glyph = lambda c: ICONS.get(c, label(c))
    # Real advance widths, icons included: the backspace glyph is ~1.25 em,
    # and a fixed icon width made its cell too narrow.
    widths = [font_of(c).getlength(glyph(c)) / SS for c in items]
    slots = slot_angles(widths, KEY_R)

    img = Image.new("RGB", (W * SS, H * SS), rgb(PAGE_BG))
    d = ImageDraw.Draw(img)
    cx = cy = W * SS / 2
    ro = RIM_OUTER * SS
    box = (cx - ro, cy - ro, cx + ro, cy + ro)
    seg = text_entry.SEGMENT
    for i in range(0, len(items), seg):
        a = slots[i][0] - slots[i][1]
        b = slots[min(i + seg, len(items)) - 1]
        b = b[0] + b[1]
        tint = WRITE_BG if (i // seg) % 2 else CARD_BG
        d.pieslice(box, a - 90, b - 90, fill=rgb(tint))   # PIL 0 deg = 3 o'clock
    ri = (RIM_OUTER - BAND_W) * SS
    d.ellipse((cx - ri, cy - ri, cx + ri, cy + ri), fill=rgb(PAGE_BG))

    for c, (ang, _) in zip(items, slots):
        f = font_of(c)
        g = glyph(c)
        l, t, r, b = f.getbbox(g)
        tile = Image.new("RGBA", (r - l + 8 * SS, b - t + 8 * SS), (0, 0, 0, 0))
        ImageDraw.Draw(tile).text((4 * SS - l, 4 * SS - t), g, font=f, fill=rgb(INK))
        tile = tile.rotate(-rim_rotation(ang), resample=Image.BICUBIC, expand=True)
        x = cx + KEY_R * SS * math.sin(math.radians(ang)) - tile.width / 2
        y = cy - KEY_R * SS * math.cos(math.radians(ang)) - tile.height / 2
        img.paste(tile, (int(x), int(y)), tile)
    return img.resize((W, H), Image.LANCZOS), slots


def write_lvgl_bin(img, path):
    """LVGL 9 image: 12-byte header (magic 0x19, cf RGB565 0x12) + pixels."""
    px = img.load()
    with open(path, "wb") as f:
        f.write(struct.pack("<BBHHHHH", 0x19, 0x12, 0, W, H, W * 2, 0))
        for y in range(H):
            row = bytearray()
            for x in range(W):
                r, g, b = px[x, y]
                row += struct.pack("<H", ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3))
            f.write(row)


def main():
    args = sys.argv[1:]
    size = BODY
    if "--size" in args:
        i = args.index("--size")
        size = int(args[i + 1])
        del args[i:i + 2]
    if len(args) == 2:
        mont, fa = args
    else:
        mont = fetch("Montserrat-Medium.ttf")
        fa = fetch("FontAwesome5-Solid+Brands+Regular.woff")
    table = {}
    for name, items in RINGS.items():
        img, slots = render(items, mont, fa, size)
        write_lvgl_bin(img, os.path.join(HERE, "kb_%s.bin" % name))
        img.save(os.path.join(HERE, "tools", "kb_%s.png" % name))
        table[name] = {"items": items, "slots": slots}
    with open(os.path.join(HERE, "kb_rings.json"), "w") as f:
        json.dump(table, f)
    print("wrote %s kb_rings.json" % " ".join("kb_%s.bin" % n for n in RINGS))


if __name__ == "__main__":
    main()
