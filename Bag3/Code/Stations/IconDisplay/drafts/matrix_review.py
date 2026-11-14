"""Review sheets for the hand-edited "matrixicons" Illustrator exports.

Each export holds the same N icons in the same order: _original (one embedded
PNG per icon), -16x16 (a grid of <rect>s per icon, icon display) and -5x5 (wand).
Builds labelled contact sheets showing original | 16x16 | 5x5 per icon, with the
closest existing icon name as a hint (the SVGs carry no names).

Run: python3 matrix_review.py ORIGINAL.svg SVG16.svg SVG5.svg [-o outdir] [--per 24]
Writes outdir/matrix_review_N.png and outdir/matrix_index.json (index, nearest icon).
"""
import argparse, base64, io, json, os, re, sys
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__))
ICONS = os.path.join(HERE, "..", "icons")

def css(s):
    return {m.group(1): m.group(2) for m in re.finditer(r"\.(st\d+)\s*\{\s*fill:\s*(#[0-9a-fA-F]{3,6})", s)}

def hex_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3: h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

def parse_grids(path, n):
    """-> list of (n x n) lists of (r,g,b); unlisted cells and unclassed rects are black (off)."""
    s = open(path).read(); cls = css(s); out = []
    for g in re.findall(r"<g>(.*?)</g>", s, re.S):
        cells = []
        for m in re.finditer(r"<rect([^>]*)/>", g):
            a = m.group(1); x = float(re.search(r' x="([\d.\-]+)"', a).group(1)) if ' x="' in a else 0.0
            y = float(re.search(r'y="([\d.\-]+)"', a).group(1)) if ' y="' in a else 0.0
            w = float(re.search(r'width="([\d.\-]+)"', a).group(1)); h = float(re.search(r'height="([\d.\-]+)"', a).group(1))
            c = re.search(r'class="(st\d+)"', a)
            cells.append((x, y, w, h, hex_rgb(cls[c.group(1)]) if c else (0, 0, 0)))
        x0 = min(c[0] for c in cells); y0 = min(c[1] for c in cells)
        w, h = cells[0][2], cells[0][3]
        grid = [[(0, 0, 0)] * n for _ in range(n)]
        for x, y, _, _, col in cells:
            gx, gy = round((x - x0) / w), round((y - y0) / h)
            if 0 <= gx < n and 0 <= gy < n: grid[gy][gx] = col
        # SVG y runs down but Illustrator export lists rows bottom-up only by order; position decides, so no flip.
        out.append(dict(grid=grid, x=x0, y=y0))
    return out

def parse_images(path):
    s = open(path).read(); out = []
    for m in re.finditer(r'<image ([^>]*?)xlink:href="data:image/png;base64,([^"]+)"', s):
        t = re.search(r"translate\(([\d.\-]+)[ ,]([\d.\-]+)\)", m.group(1))
        out.append(dict(img=Image.open(io.BytesIO(base64.b64decode(m.group(2)))).convert("RGBA"),
                        x=float(t.group(1)), y=float(t.group(2))))
    return out

def load_existing():
    ex = {}
    for p in sorted(os.listdir(ICONS)):
        if not p.endswith(".py"): continue
        t = [tuple(map(int, m)) for m in re.findall(r"\((\d+),\s*(\d+),\s*(\d+)\)", open(os.path.join(ICONS, p)).read())][-256:]
        if len(t) == 256: ex[p[:-3]] = t
    return ex

def nearest(grid16, ex):
    """Closest icon by on/off mask overlap (names are a hint only)."""
    mask = {(x, y) for y in range(16) for x in range(16) if sum(grid16[y][x]) > 60}
    best = (0, None)
    for n, t in ex.items():
        m2 = {(i % 16, i // 16) for i, c in enumerate(t) if sum(c) > 0}
        u = len(mask | m2) or 1; j = len(mask & m2) / u
        if j > best[0]: best = (j, n)
    return best[1], round(best[0], 2)

def draw_grid(im, grid, ox, oy, cell, gap=1):
    d = ImageDraw.Draw(im); n = len(grid)
    d.rectangle([ox, oy, ox + n * cell, oy + n * cell], fill=(12, 12, 12))
    for y, row in enumerate(grid):
        for x, c in enumerate(row):
            d.rectangle([ox + x * cell, oy + y * cell, ox + (x + 1) * cell - gap - 1, oy + (y + 1) * cell - gap - 1], fill=c if sum(c) else (22, 22, 24))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("original"); ap.add_argument("svg16"); ap.add_argument("svg5")
    ap.add_argument("-o", "--out", default=os.path.join(HERE, "review")); ap.add_argument("--per", type=int, default=24)
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    orig = parse_images(a.original); g16 = parse_grids(a.svg16, 16); g5 = parse_grids(a.svg5, 5)
    if not (len(orig) == len(g16) == len(g5)):
        print(f"WARNING counts differ: original {len(orig)}, 16x16 {len(g16)}, 5x5 {len(g5)}", file=sys.stderr)
    N = min(len(orig), len(g16), len(g5)); ex = load_existing()
    try: font = ImageFont.truetype("DejaVuSans.ttf", 13)
    except OSError: font = ImageFont.load_default()
    index = []; TW, TH, COLS = 420, 156, 3
    for s0 in range(0, N, a.per):
        ids = range(s0, min(N, s0 + a.per)); rows = (len(ids) + COLS - 1) // COLS
        sheet = Image.new("RGB", (COLS * TW, rows * TH), (30, 30, 34)); d = ImageDraw.Draw(sheet)
        for k, i in enumerate(ids):
            cx, cy = (k % COLS) * TW, (k // COLS) * TH
            near, score = nearest(g16[i]["grid"], ex); index.append(dict(index=i, nearest=near, score=score, x=g16[i]["x"], y=g16[i]["y"]))
            o = orig[i]["img"]; o = o.resize((int(o.width * 128 / o.height), 128), Image.NEAREST)
            bg = Image.new("RGB", o.size, (12, 12, 12)); bg.paste(o, mask=o.split()[3]); sheet.paste(bg, (cx + 6, cy + 18))
            draw_grid(sheet, g16[i]["grid"], cx + 140, cy + 18, 8)
            draw_grid(sheet, g5[i]["grid"], cx + 285, cy + 18, 24, 3)
            d.text((cx + 6, cy + 2), f"#{i:02d}" + (f"  ~{near} ({score})" if score >= .8 else ""), fill=(200, 200, 205), font=font)
        p = os.path.join(a.out, f"matrix_review_{s0 // a.per + 1}.png"); sheet.save(p); print(p)
    json.dump(index, open(os.path.join(a.out, "matrix_index.json"), "w"), indent=1)
main()
