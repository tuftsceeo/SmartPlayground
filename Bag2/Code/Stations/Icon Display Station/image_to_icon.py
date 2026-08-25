import sys
import colorsys
from PIL import Image

W = 16
H = 16

# pulled straight from lib/leds.py -- base colors only, no _DIM variants
# (brightness is handled by rescaling to the source pixel's own value below)
PALETTE = {
    "RED": (130, 0, 0), "ROSE": (120, 10, 20),
    "ORANGE": (120, 40, 0), "AMBER": (120, 80, 0), "YELLOW": (110, 120, 0),
    "LIME": (50, 210, 0), "GREEN": (0, 230, 0),
    "TEAL": (0, 180, 100), "CYAN": (0, 180, 240), "BLUE": (0, 20, 255),
    "INDIGO": (30, 0, 255), "PURPLE": (50, 0, 250), "MAGENTA": (120, 0, 160),
    "WHITE": (140, 150, 150), "PINK": (200, 80, 120), "PEACH": (180, 120, 30),
    "MINT": (30, 190, 50), "SKY": (60, 150, 250),
}
PALETTE_HSV = {name: colorsys.rgb_to_hsv(*(c/255 for c in rgb)) for name, rgb in PALETTE.items()}

V_FLOOR = 0.04  # basically-black source pixels just go off, don't hue-match noise
S_FLOOR = 0.12  # near-gray source pixels -- hue is meaningless, treat as white

def hue_dist(h1, h2):
    d = abs(h1 - h2)
    return min(d, 1 - d)

def snap(rgb):
    r, g, b = (c / 255 for c in rgb)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if v < V_FLOOR:
        return (0, 0, 0)
    name = "WHITE" if s < S_FLOOR else min(PALETTE_HSV, key=lambda n: hue_dist(h, PALETTE_HSV[n][0]))
    ph, ps, pv = PALETTE_HSV[name]
    if pv <= 0:
        return (0, 0, 0)
    scale = v / pv
    pr, pg, pb = PALETTE[name]
    return (min(255, int(pr * scale)), min(255, int(pg * scale)), min(255, int(pb * scale)))

def convert(path):
    img = Image.open(path).convert("RGBA")
    bg = Image.new("RGBA", img.size, (0, 0, 0, 255))
    img = Image.alpha_composite(bg, img).convert("RGB").resize((W, H), Image.NEAREST)
    px = []
    for row in range(H):
        for col in range(W):
            px.append(snap(img.getpixel((col, row))))
    return px

def preview(px):
    for row in range(H):
        line = ""
        for col in range(W):
            r, g, b = px[row * W + col]
            line += "\x1b[48;2;%d;%d;%dm  \x1b[0m" % (r, g, b)
        print(line)

def write(px, out):
    with open(out, "w") as f:
        f.write("ICON = (\n")
        for row in range(H):
            f.write("    " + ", ".join(str(p) for p in px[row*W:(row+1)*W]) + ",\n")
        f.write(")\n")

if __name__ == "__main__":
    path = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else "icon_out.py"
    px = convert(path)
    preview(px)
    write(px, out)
    print("wrote", out)
