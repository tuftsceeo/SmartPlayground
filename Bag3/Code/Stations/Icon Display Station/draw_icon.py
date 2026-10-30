#!/usr/bin/env python3
"""
draw_icon.py -- draw a 16x16 icon from a text grid, preview it, and install it
into every copy of the icon display's built-in set.

A spec is a JSON file:

    {
      "name": "bus",
      "key":  {"Y": [255, 150, 0], "K": [30, 20, 10], "W": [255, 171, 93]},
      "rows": ["................", "..YYYYYYYYYYYY..", ... 16 rows of 16 chars]
    }

Each character in `rows` is a key letter or `.` for off. Key values are
authored LED duty (r, g, b), the same values the device files hold. Neutrals
need the warm ratio: white (255,171,93), light grey (180,120,65), grey
(110,74,40), near black (30,20,10) -- equal RGB shows as cyan.

    python3 draw_icon.py spec.json                   # preview PNG beside the spec
    python3 draw_icon.py spec.json --out bus.png     # preview to a chosen path
    python3 draw_icon.py --export dog > dog.json     # existing icon -> spec to edit
    python3 draw_icon.py spec.json --install         # write and sync every copy

--install writes:
  - ../IconDisplay/icons/<name>.py   device icon (source of truth)
  - maps/<name>.json                 full design as a 256-cell overlay, which
                                     both Icon Makers reopen as painted cells;
                                     also ChatBroadcast/iconmaker/maps/<name>.json
                                     when that copy has one
  - previews/<name>.png              gallery preview
then runs ChatBroadcast/tools/sync_icons.py (defaultIcons.js and --station,
each with --check) and copies defaultIcons.js into Live_Page/ChatBroadcast.
A new name also needs a row in gallery.html to appear there.

Preview colours come from iconlib/preview.py: the icon editor's LED model at
full duty, square cells on a dark diffuser.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "iconlib"))

from preview import render_preview  # noqa: E402

W = H = 16
OFF = (0, 0, 0)
CODE = os.path.normpath(os.path.join(HERE, "..", ".."))
DEVICE_ICONS = os.path.join(CODE, "Stations", "IconDisplay", "icons")
MAPS_DIR = os.path.join(HERE, "maps")
PREVIEWS_DIR = os.path.join(HERE, "previews")
CHAT = os.path.join(CODE, "BroadcastCode", "ChatBroadcast")
ICONMAKER_MAPS = os.path.join(CHAT, "iconmaker", "maps")
DEFAULT_ICONS = os.path.join(CHAT, "js", "ledicons", "defaultIcons.js")
LIVE_DEFAULT_ICONS = os.path.join(CODE, "..", "..", "Live_Page", "ChatBroadcast", "js", "ledicons", "defaultIcons.js")
HEADER = "# Hand-edited 16x16 icon -- linear PWM duty bytes, row-major from top-left.\n"
KEY_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"


def pixels_from_spec(spec):
    name = spec.get("name", "")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        raise ValueError("name must be lowercase letters, digits and _: %r" % name)
    rows = spec["rows"]
    if len(rows) != H or any(len(r) != W for r in rows):
        raise ValueError("rows must be %d strings of %d characters" % (H, W))
    key = {k: tuple(v) for k, v in spec["key"].items()}
    for k, v in key.items():
        if len(k) != 1 or k == "." or len(v) != 3 or not all(0 <= c <= 255 for c in v):
            raise ValueError("bad key entry %r: %r" % (k, v))
    pixels = []
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            if ch == ".":
                pixels.append(OFF)
            elif ch in key:
                pixels.append(key[ch])
            else:
                raise ValueError("row %d col %d: %r is not in key" % (r, c, ch))
    return name, pixels


def read_icon(path):
    with open(path) as f:
        found = re.findall(r"\((\d+),\s*(\d+),\s*(\d+)\)", f.read())
    pixels = [tuple(int(v) for v in t) for t in found][-W * H:]
    if len(pixels) != W * H:
        raise ValueError("%s: expected %d pixels, found %d" % (path, W * H, len(pixels)))
    return pixels


def spec_from_pixels(name, pixels):
    colours = sorted(set(p for p in pixels if p != OFF))
    if len(colours) > len(KEY_CHARS):
        raise ValueError("too many colours to key")
    key = dict(zip(KEY_CHARS, colours))
    char = {v: k for k, v in key.items()}
    rows = ["".join("." if p == OFF else char[p] for p in pixels[r * W:(r + 1) * W]) for r in range(H)]
    return {"name": name, "key": {k: list(v) for k, v in key.items()}, "rows": rows}


def format_spec(spec):
    """JSON with one key colour and one grid row per line, so the grid reads as a picture."""
    keys = ",\n".join('    "%s": %s' % (k, json.dumps(v)) for k, v in spec["key"].items())
    rows = ",\n".join('    "%s"' % r for r in spec["rows"])
    return '{\n  "name": "%s",\n  "key": {\n%s\n  },\n  "rows": [\n%s\n  ]\n}' % (spec["name"], keys, rows)


def write_device_icon(path, pixels):
    with open(path, "w") as f:
        f.write(HEADER)
        f.write("SIZE = (%d, %d)\n" % (W, H))
        f.write("ICON = (\n")
        for r in range(H):
            f.write("    " + ", ".join("(%d, %d, %d)" % p for p in pixels[r * W:(r + 1) * W]) + ",\n")
        f.write(")\n")


def map_text(path, pixels):
    """Keep a photo-derived map's segmentation; otherwise a hand-authored map.
    Either way the overlay carries every cell, so reopening shows this design."""
    overlay = {str(i): list(p) for i, p in enumerate(pixels)}
    existing = None
    if os.path.exists(path):
        with open(path) as f:
            existing = json.load(f)
    if existing and existing.get("source") != "hand-authored":
        existing["overlay"] = overlay
        obj = existing
    else:
        lit = sorted(set(p for p in pixels if p != OFF))
        obj = {
            "source": "hand-authored",
            "max_segments": len(lit),
            "intensity": 0.3,
            "fills": [{"rgb": list(c), "count": pixels.count(c), "frac": round(pixels.count(c) / float(W * H), 5)} for c in lit],
            "decisions": {"%d,%d,%d" % c: {"role": "color", "priority": 1.0, "color": list(c)} for c in lit},
            "overlay": overlay,
        }
    return json.dumps(obj, indent=2) + "\n"


def sync():
    tool = os.path.join("tools", "sync_icons.py")
    for args in ([], ["--check"], ["--station"], ["--station", "--check"]):
        subprocess.run([sys.executable, tool] + args, cwd=CHAT, check=True)
    if os.path.isdir(os.path.dirname(LIVE_DEFAULT_ICONS)):
        shutil.copyfile(DEFAULT_ICONS, LIVE_DEFAULT_ICONS)
        print("copied defaultIcons.js to Live_Page/ChatBroadcast")


def install(name, pixels):
    icon_path = os.path.join(DEVICE_ICONS, name + ".py")
    is_new = not os.path.exists(icon_path)
    write_device_icon(icon_path, pixels)
    text = map_text(os.path.join(MAPS_DIR, name + ".json"), pixels)
    with open(os.path.join(MAPS_DIR, name + ".json"), "w") as f:
        f.write(text)
    if os.path.exists(os.path.join(ICONMAKER_MAPS, name + ".json")):
        with open(os.path.join(ICONMAKER_MAPS, name + ".json"), "w") as f:
            f.write(text)
    render_preview(pixels, None, os.path.join(PREVIEWS_DIR, name + ".png"))
    print("wrote %s, maps/%s.json and previews/%s.png" % (os.path.relpath(icon_path, CODE), name, name))
    sync()
    with open(os.path.join(HERE, "gallery.html")) as f:
        if '["%s",' % name not in f.read():
            print("note: add [\"%s\", \"<category>\", true] to gallery.html to show it there" % name)
    if is_new:
        print("new icon: games can now name %r" % name)


def main():
    ap = argparse.ArgumentParser(description="Draw a 16x16 icon from a text grid.")
    ap.add_argument("spec", nargs="?", help="spec JSON file")
    ap.add_argument("--out", help="preview PNG path (default: <spec>.png)")
    ap.add_argument("--install", action="store_true", help="write the icon into every copy and sync")
    ap.add_argument("--export", metavar="NAME", help="print an existing device icon as a spec")
    a = ap.parse_args()

    if a.export:
        pixels = read_icon(os.path.join(DEVICE_ICONS, a.export + ".py"))
        print(format_spec(spec_from_pixels(a.export, pixels)))
        return 0
    if not a.spec:
        ap.error("give a spec file or --export NAME")

    with open(a.spec) as f:
        name, pixels = pixels_from_spec(json.load(f))
    out = a.out or os.path.splitext(a.spec)[0] + ".png"
    render_preview(pixels, None, out)
    print("preview: %s" % out)
    if a.install:
        install(name, pixels)
    return 0


if __name__ == "__main__":
    sys.exit(main())
