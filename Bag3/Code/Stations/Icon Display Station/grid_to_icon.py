#!/usr/bin/env python3
"""
grid_to_icon.py -- turn character-grid icon maps into device icons and
screen previews.

Input is a JSON file of {name: entry}. Each entry has a "key" mapping a
single character to an LED duty [r, g, b] ("." is always off), and either
"rows" (16 strings of 16 characters) or "frames" (a list of such row lists)
plus an optional "fps".

Run:
    python3 grid_to_icon.py drafts/grids/holiday.json            # previews only
    python3 grid_to_icon.py drafts/grids/holiday.json --write    # also drafts/icons/<name>.py

Writes previews/grids/<file>.png, a labelled sheet with animation frames side
by side, and previews/grids/<name>.gif for each animated entry. With --write
it writes drafts/icons/<name>.py (an animated entry writes <name>_1.py,
<name>_2.py, ... because the device holds one frame per icon). Promoting a
draft into the device set is in drafts/README.md.

Screen colours use the icon editor's LED model (webapp/js/pipeline/ledGamut.js
ledSwatchHex), so the preview matches what the editor and the simulator show.
"""
import json
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
W = 16
CELL = 16

_PRIM = [(0.7006, 0.2993, 400.0), (0.0743, 0.8338, 1150.0), (0.1241, 0.0578, 250.0)]
_PRIM_XYZ = [((x / y) * iv, iv, ((1 - x - y) / y) * iv) for x, y, iv in _PRIM]
_Y_WHITE = sum(p[1] for p in _PRIM_XYZ)


def led_screen_rgb(duty):
    xyz = [sum(duty[j] / 255 * _PRIM_XYZ[j][i] for j in range(3)) / _Y_WHITE for i in range(3)]
    X, Y, Z = xyz
    lin = (3.2406 * X - 1.5372 * Y - 0.4986 * Z,
           -0.9689 * X + 1.8758 * Y + 0.0415 * Z,
           0.0557 * X - 0.204 * Y + 1.057 * Z)
    out = []
    for c in lin:
        v = max(0.0, min(1.0, c))
        v = 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055
        out.append(round(v * 255))
    return tuple(out)


def frames_of(entry):
    return entry["frames"] if "frames" in entry else [entry["rows"]]


def pixels(rows, key):
    if len(rows) != W or any(len(r) != W for r in rows):
        raise ValueError("each frame needs 16 rows of 16 characters")
    out = []
    for r in rows:
        for ch in r:
            if ch == ".":
                out.append((0, 0, 0))
            elif ch in key:
                out.append(tuple(key[ch]))
            else:
                raise ValueError(f"character {ch!r} is not in the key")
    return out


def render(px):
    img = Image.new("RGB", (W * CELL + 1, W * CELL + 1), (10, 10, 11))
    d = ImageDraw.Draw(img)
    for i, duty in enumerate(px):
        x, y = (i % W) * CELL + 1, (i // W) * CELL + 1
        fill = led_screen_rgb(duty) if any(duty) else (29, 29, 33)
        d.rectangle([x, y, x + CELL - 2, y + CELL - 2], fill=fill)
    return img


def write_icon(path, px):
    lines = ["# Hand-edited 16x16 icon -- linear PWM duty bytes, row-major from top-left.",
             "SIZE = (16, 16)", "ICON = ("]
    for r in range(W):
        lines.append("    " + " ".join(f"{px[r * W + c]}," for c in range(W)))
    lines.append(")")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        sys.exit(__doc__)
    src = args[0]
    with open(src) as f:
        data = json.load(f)
    out_dir = os.path.join(HERE, "previews", "grids")
    os.makedirs(out_dir, exist_ok=True)

    tiles = []
    for name, entry in data.items():
        imgs = [render(pixels(rows, entry["key"])) for rows in frames_of(entry)]
        tiles.append((name, imgs))
        if len(imgs) > 1:
            ms = int(1000 / entry.get("fps", 4))
            imgs[0].save(os.path.join(out_dir, f"{name}.gif"), save_all=True,
                         append_images=imgs[1:], duration=ms, loop=0)
        if "--write" in sys.argv:
            for n, rows in enumerate(frames_of(entry), 1):
                fname = name if len(imgs) == 1 else f"{name}_{n}"
                write_icon(os.path.join(HERE, "drafts", "icons", f"{fname}.py"),
                           pixels(rows, entry["key"]))

    tile = W * CELL + 1
    pad, label = 12, 18
    width = pad + max(len(imgs) for _, imgs in tiles) * (tile + pad)
    sheet = Image.new("RGB", (width, pad + len(tiles) * (tile + label + pad)), (246, 244, 251))
    d = ImageDraw.Draw(sheet)
    for row, (name, imgs) in enumerate(tiles):
        y = pad + row * (tile + label + pad)
        d.text((pad, y), name, fill=(35, 31, 46))
        for col, img in enumerate(imgs):
            sheet.paste(img, (pad + col * (tile + pad), y + label))
    base = os.path.splitext(os.path.basename(src))[0]
    sheet.save(os.path.join(out_dir, f"{base}.png"))
    print(f"wrote previews/grids/{base}.png and {sum(len(i) > 1 for _, i in tiles)} gif(s)")


if __name__ == "__main__":
    main()
