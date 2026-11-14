"""Scale 5x5 wand glyphs/images up to 16x16 approximations for the icon display.

Sources (any combination):
  --shapes    every SHAPE_* in Wand Module/lib/leds.py (lit cells, one colour; default white)
  --games     the GAME_ICON (shape, colour) pairs from Wand Module/main.py
  --cooking   the 5x5 recipe images in Wand Module/cooking.py (multicolour)
  --svg5 F    the 5x5 grids of a matrixicons-5x5 Illustrator export (via matrix_review.py)

Methods (all shown on the sheet, 5x5 | block | smooth | smooth+shade):
  block   house convention: 3x integer blocks, centred in 15x15 (rimmed by 1 empty row/col)
  smooth  each 16x16 pixel samples the 5x5 bilinearly; the lit mask is thresholded so corners
          round off and diagonals become 2-px steps; colour comes from the nearest lit cell
  shade   smooth + the LED-matrix style rules: lighter top edge, darker bottom edge per colour

Wand colours are dim duty values; they are rescaled so the brightest channel is 255 before
the 16x16 duty is built, keeping the hue. Output is a starting point for hand editing.

Run: python3 scale5to16.py [--shapes] [--games] [--cooking] [--svg5 FILE] [-o outdir] [--json]
Writes outdir/scale5to16_N.png (+ scale5to16.json with 16-row drafts if --json).
"""
import argparse, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
WAND = os.path.join(CODE, "Wand Module")
COLOR_RE = re.compile(r"^([A-Z_0-9]+)\s*=\s*\((\d+),\s*(\d+),\s*(\d+)\)")
SHAPE_RE = re.compile(r"^(SHAPE_[A-Za-z0-9_]+)\s*=\s*\(([0-9,\s]*)\)")
OFF = (0, 0, 0)

def read_leds():
    shapes, colors = {}, {}
    for line in open(os.path.join(WAND, "lib", "leds.py")):
        m = SHAPE_RE.match(line)
        if m: shapes[m.group(1)] = [int(x) for x in m.group(2).replace(" ", "").split(",") if x]; continue
        m = COLOR_RE.match(line)
        if m: colors[m.group(1)] = tuple(int(m.group(i)) for i in (2, 3, 4))
    return shapes, colors

def bright(c):
    """Rescale a dim wand colour so its max channel is 255 (hue kept)."""
    m = max(c)
    return OFF if m == 0 else tuple(round(v * 255 / m) for v in c)

def shape_grid(cells, color):
    g = [[OFF] * 5 for _ in range(5)]
    for i in cells: g[i // 5][i % 5] = color
    return g

def cooking_images(colors):
    src = open(os.path.join(WAND, "cooking.py")).read()
    env = dict(colors); env["BROWN"] = colors["AMBER"]; env["BLACK"] = OFF
    out = {}
    for m in re.finditer(r"^([A-Z]+) = \[\n(.*?)\n\]", src, re.S | re.M):
        names = re.findall(r"[A-Z_]+", m.group(2))
        if len(names) == 25 and all(n in env for n in names):
            out[m.group(1).lower()] = [[env[names[y * 5 + x]] for x in range(5)] for y in range(5)]
    return out

def block(g):
    """3x integer blocks centred in 16x16 (offset 0 -> margin falls right/bottom, as icon_test.py)."""
    o = [[OFF] * 16 for _ in range(16)]
    for y in range(15):
        for x in range(15): o[y][x] = g[y // 3][x // 3]
    return o

def smooth(g, thresh=0.5, span=15.0):
    """Bilinear-sample the lit mask over a span x span area centred in 16x16."""
    off = (16 - span) / 2; o = [[OFF] * 16 for _ in range(16)]
    lit = lambda x, y: 1.0 if 0 <= x < 5 and 0 <= y < 5 and g[y][x] != OFF else 0.0
    for py in range(16):
        for px in range(16):
            u = (px + .5 - off) * 5 / span - .5; v = (py + .5 - off) * 5 / span - .5
            x0, y0 = int(u // 1), int(v // 1); fx, fy = u - x0, v - y0
            w = [(x0, y0, (1 - fx) * (1 - fy)), (x0 + 1, y0, fx * (1 - fy)), (x0, y0 + 1, (1 - fx) * fy), (x0 + 1, y0 + 1, fx * fy)]
            if sum(wt * lit(x, y) for x, y, wt in w) < thresh: continue
            # colour: weight lit neighbours, keep the dominant one so palettes stay crisp
            best = max(((wt, g[y][x]) for x, y, wt in w if lit(x, y)), key=lambda t: t[0])
            o[py][px] = best[1]
    return o

def shade(img):
    """Top-lit three-tone: nothing lit above -> lighter (25% toward white); nothing lit below -> darker (55%)."""
    o = [row[:] for row in img]
    for y in range(16):
        for x in range(16):
            c = img[y][x]
            if c == OFF: continue
            up = img[y - 1][x] if y else OFF; dn = img[y + 1][x] if y < 15 else OFF
            if up == OFF and dn != OFF: o[y][x] = tuple(round(v + (255 - v) * .25) for v in c)
            elif dn == OFF and up != OFF: o[y][x] = tuple(round(v * .55) for v in c)
    return o

def prep(g):  # normalise a 5x5 grid's colours for 16x16 use
    return [[bright(c) for c in row] for row in g]

def gather(a):
    shapes, colors = read_leds(); items = []
    if a.shapes:
        for n, cells in shapes.items(): items.append((n[6:].lower(), shape_grid(cells, colors.get("WHITE", (255, 255, 255)))))
    if a.games:
        main = open(os.path.join(WAND, "main.py")).read()
        for m in re.finditer(r'^\s*"(\w+)":\s*\((SHAPE_\w+),\s*([A-Z_]+)\),', main, re.M):
            if m.group(2) in shapes and m.group(3) in colors: items.append(("game_" + m.group(1), shape_grid(shapes[m.group(2)], colors[m.group(3)])))
    if a.cooking:
        for n, g in cooking_images(colors).items(): items.append(("cook_" + n, g))
    if a.svg5:  # reuse matrix_review's parser without running its main()
        path = os.path.join(HERE, "matrix_review.py")
        ns = {"__name__": "matrix_review", "__file__": path}
        exec(compile(open(path).read().replace("\nmain()\n", "\n"), path, "exec"), ns)
        for i, d in enumerate(ns["parse_grids"](a.svg5, 5)): items.append((f"svg5_{i:02d}", d["grid"]))
    return items

def screen(c):  # LED -> screen preview model (same as category_sheet.py / samples.py)
    PRIM = [(0.7006, 0.2993, 400), (0.0743, 0.8338, 1150), (0.1241, 0.0578, 250)]
    PRIM = [((x / y) * I, I, ((1 - x - y) / y) * I) for x, y, I in PRIM]; LY = sum(p[1] for p in PRIM)
    if not any(c): return (26, 26, 28)
    X, Y, Z = [sum(c[j] / 255 * PRIM[j][i] for j in range(3)) / LY for i in range(3)]
    f = lambda v: max(0, min(1, v)); gm = lambda v: 12.92 * v if v <= .0031308 else 1.055 * v ** (1 / 2.4) - .055
    return tuple(round(gm(f(v)) * 255) for v in (3.2406 * X - 1.5372 * Y - .4986 * Z, -.9689 * X + 1.8758 * Y + .0415 * Z, .0557 * X - .204 * Y + 1.057 * Z))

def main():
    ap = argparse.ArgumentParser()
    for f in ("--shapes", "--games", "--cooking", "--json"): ap.add_argument(f, action="store_true")
    ap.add_argument("--svg5"); ap.add_argument("-o", "--out", default=os.path.join(HERE, "review")); ap.add_argument("--per", type=int, default=20)
    a = ap.parse_args()
    if not (a.shapes or a.games or a.cooking or a.svg5): a.shapes = a.games = a.cooking = True
    from PIL import Image, ImageDraw
    os.makedirs(a.out, exist_ok=True); items = gather(a); CELL, TW, TH, COLS = 7, 4 * 0 + 460, 140, 2
    drafts = {}
    for s0 in range(0, len(items), a.per):
        chunk = items[s0:s0 + a.per]; rows = (len(chunk) + COLS - 1) // COLS
        im = Image.new("RGB", (COLS * TW, rows * TH), (24, 24, 28)); d = ImageDraw.Draw(im)
        for k, (name, g5) in enumerate(chunk):
            ox, oy = (k % COLS) * TW + 6, (k // COLS) * TH + 16; g = prep(g5)
            variants = [g, block(g), smooth(g), shade(smooth(g))]
            drafts[name] = variants[3]
            d.text((ox, oy - 14), name, fill=(220, 220, 220)); x = ox
            for vi, v in enumerate(variants):
                n = len(v); c = 14 if n == 5 else CELL; d.rectangle([x, oy, x + n * c, oy + n * c], fill=(12, 12, 12))
                for yy in range(n):
                    for xx in range(n):
                        d.ellipse([x + xx * c + 1, oy + yy * c + 1, x + xx * c + c - 2, oy + yy * c + c - 2], fill=screen(v[yy][xx]) if any(v[yy][xx]) else (24, 24, 26))
                x += n * c + 10
        p = os.path.join(a.out, f"scale5to16_{s0 // a.per + 1}.png"); im.save(p); print(p)
    if a.json:
        out = {}
        for name, img in drafts.items():
            pal = {}; rows = []
            for r in img:
                rows.append("".join("." if c == OFF else pal.setdefault(c, chr(65 + len(pal))) for c in r))
            out[name] = dict(rows=rows, pal={k: list(c) for c, k in pal.items()})
        json.dump(out, open(os.path.join(a.out, "scale5to16.json"), "w"), indent=1); print("json:", len(out))
main()
