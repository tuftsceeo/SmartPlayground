"""Make 5x5 wand icons from the 16x16 matrixicons: crop the empty margin, centre in a
square, resample to 5x5. Never touches matrixicons/json5/ (the hand-made 5x5s).

  1. lit = any channel >= LIT (near-off outline pixels don't count for the crop box)
  2. crop to the lit bounding box, pad the short side with off cells to a centred square
  3. area-resample: each 5x5 cell covers S/5 source cells (fractional overlap weights);
     it is lit if >= COVER of its area is lit, and takes the area-weighted DOMINANT colour
     (not the blend) so hues stay saturated
Run: python3 downscale16to5.py [--lit 40] [--cover 0.4] [-o matrixicons/json5_cropped]
Writes <name>.json per icon (rows + pal, same format as json5/) and compare.png
(16x16 | existing 5x5 | new 5x5).
"""
import argparse, glob, json, os
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__)); M = os.path.join(HERE, "matrixicons")

def grid(icon):
    pal = {k: tuple(int(v[i:i + 2], 16) for i in (1, 3, 5)) for k, v in icon["pal"].items()}
    return [[None if ch == "." else pal[ch] for ch in row] for row in icon["rows"]]

def downscale(g, lit, cover):
    n = len(g); on = lambda c: c is not None and max(c) >= lit
    pts = [(x, y) for y in range(n) for x in range(n) if on(g[y][x])]
    if not pts: return [[None] * 5 for _ in range(5)]
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts) + 1
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts) + 1
    S = max(x1 - x0, y1 - y0); ox = x0 - (S - (x1 - x0)) / 2; oy = y0 - (S - (y1 - y0)) / 2  # square box in source cells
    out = [[None] * 5 for _ in range(5)]; step = S / 5
    for ty in range(5):
        for tx in range(5):
            bx0, bx1, by0, by1 = ox + tx * step, ox + (tx + 1) * step, oy + ty * step, oy + (ty + 1) * step
            area = lit_area = 0.0; votes = {}
            for y in range(max(0, int(by0 // 1)), min(n, int(by1 // 1) + 1)):
                for x in range(max(0, int(bx0 // 1)), min(n, int(bx1 // 1) + 1)):
                    w = max(0, min(bx1, x + 1) - max(bx0, x)) * max(0, min(by1, y + 1) - max(by0, y))
                    if w <= 0: continue
                    c = g[y][x]
                    if on(c): lit_area += w; votes[c] = votes.get(c, 0) + w * (1 + max(c) / 510)  # slight bias to brighter
            area = step * step
            if lit_area / area >= cover and votes: out[ty][tx] = max(votes, key=votes.get)
    return out

def to_icon(g):
    pal, rows = {}, []
    for r in g: rows.append("".join("." if c is None else pal.setdefault(c, chr(65 + len(pal))) for c in r))
    return dict(rows=rows, pal={k: "#%02x%02x%02x" % c for c, k in pal.items()})

def draw(im, g, ox, oy, cell):
    d = ImageDraw.Draw(im); n = len(g); d.rectangle([ox, oy, ox + n * cell, oy + n * cell], fill=(12, 12, 12))
    for y, r in enumerate(g):
        for x, c in enumerate(r):
            d.rectangle([ox + x * cell, oy + y * cell, ox + (x + 1) * cell - 2, oy + (y + 1) * cell - 2], fill=c if c and sum(c) else (24, 24, 26))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--lit", type=int, default=40); ap.add_argument("--cover", type=float, default=0.4)
    ap.add_argument("-o", "--out", default=os.path.join(M, "json5_cropped")); a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    files = sorted(glob.glob(os.path.join(M, "json16", "*.json"))); TW, TH, COLS, per = 330, 150, 3, 30; tiles = []
    for f in files:
        name = os.path.basename(f)[:-5]; g16 = grid(json.load(open(f))); g5 = downscale(g16, a.lit, a.cover)
        json.dump(to_icon(g5), open(os.path.join(a.out, name + ".json"), "w"), indent=1)
        old = os.path.join(M, "json5", name + ".json"); tiles.append((name, g16, grid(json.load(open(old))) if os.path.exists(old) else None, g5))
    for s0 in range(0, len(tiles), per):
        ch = tiles[s0:s0 + per]; rows = (len(ch) + COLS - 1) // COLS; im = Image.new("RGB", (COLS * TW, rows * TH), (30, 30, 34)); d = ImageDraw.Draw(im)
        for k, (name, g16, old, g5) in enumerate(ch):
            cx, cy = (k % COLS) * TW, (k // COLS) * TH; d.text((cx + 6, cy + 2), name, fill=(220, 220, 225))
            draw(im, g16, cx + 6, cy + 18, 8)
            if old: draw(im, old, cx + 146, cy + 18, 20)
            draw(im, g5, cx + 256, cy + 18, 14)
        im.save(os.path.join(a.out, f"compare_{s0 // per + 1}.png"))
    print(len(tiles), "icons ->", a.out)
main()
