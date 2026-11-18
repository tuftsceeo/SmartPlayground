"""Store the matrixicons Illustrator exports as JSON (+ editor-ready PNGs).

Run: python3 matrix_export.py SVG16.svg SVG5.svg [-o matrixicons] [--png]
Writes outdir/matrixicons_16.json and matrixicons_5.json:
  {"_key": "...", "m00": {"index": 0, "rows": ["..XX..", ...], "pal": {"A": "#rrggbb"}}, ...}
`.` = off; pal letters are per icon. Colours are the SVG's SCREEN colours (as drawn),
not LED duty bytes. Icon ids are the Illustrator order (m00..); matrixicons/names.json maps id -> name and is used for file names.
Also writes json16/ and json5/ (one icon per file, for File > Open in the Icon Maker).
--png also writes outdir/png16/mNN.png: 512x512, 32 px cells -- importable in the Icon Maker.
"""
import argparse, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(HERE, "matrix_review.py")
ns = {"__name__": "matrix_review", "__file__": path}
exec(compile(open(path).read().replace("\nmain()\n", "\n"), path, "exec"), ns)

NAMES = {}
_np = os.path.join(HERE, "matrixicons", "names.json")
if os.path.exists(_np): NAMES = {k: v for k, v in json.load(open(_np)).items() if v}  # id -> name; edit to rename

def to_json(icons):
    out = {"_key": "'.' = off; pal maps a letter to a screen colour hex. From the Illustrator matrixicons export; ids follow its icon order."}
    for i, d in enumerate(icons):
        pal, rows = {}, []
        for row in d["grid"]:
            rows.append("".join("." if sum(c) == 0 else pal.setdefault(c, chr(65 + len(pal))) for c in row))
        out[f"m{i:02d}"] = dict(index=i, **({"name": NAMES[f"m{i:02d}"]} if f"m{i:02d}" in NAMES else {}), rows=rows, pal={k: "#%02x%02x%02x" % c for c, k in pal.items()})
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("svg16"); ap.add_argument("svg5")
    ap.add_argument("-o", "--out", default=os.path.join(HERE, "matrixicons")); ap.add_argument("--png", action="store_true")
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    g16 = ns["parse_grids"](a.svg16, 16); g5 = ns["parse_grids"](a.svg5, 5)
    for n, g in ((16, g16), (5, g5)):
        js = to_json(g); json.dump(js, open(os.path.join(a.out, f"matrixicons_{n}.json"), "w"), indent=1); print(n, len(g))
        one = os.path.join(a.out, f"json{n}"); os.makedirs(one, exist_ok=True)  # one file per icon: what the Icon Maker opens directly
        for k, v in js.items():
            if not k.startswith("_"): json.dump(v, open(os.path.join(one, NAMES.get(k, k) + ".json"), "w"), indent=1)
    if a.png:
        from PIL import Image
        os.makedirs(os.path.join(a.out, "png16"), exist_ok=True)
        for i, d in enumerate(g16):
            im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
            for y, row in enumerate(d["grid"]):
                for x, c in enumerate(row):
                    if sum(c): im.putpixel((x, y), c + (255,))
            im.resize((512, 512), Image.NEAREST).save(os.path.join(a.out, "png16", NAMES.get(f"m{i:02d}", f"m{i:02d}") + ".png"))
main()
