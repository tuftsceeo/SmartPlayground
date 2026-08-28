#!/usr/bin/env python3
"""
icon_editor.py -- local web editor for turning a PNG/JPEG icon source into
a maps/<name>.json (the committed per-segment color decisions), with a
live simulated-LED preview.

    python3 icon_editor.py assets/apple.png
        -> serves http://localhost:8756, opens it in your default browser

The editor is stdlib-only (http.server) on the backend; the frontend is
plain HTML/CSS/JS in iconlib/editor_assets/ -- no build step, no framework.
Everything it does is re-runnable headless afterwards via image_to_icon.py
against the same maps/<name>.json it writes.
"""

import argparse
import base64
import io
import json
import os
import subprocess
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "iconlib"))

from PIL import Image  # noqa: E402

import mapio  # noqa: E402
from segment import W, H, MAX_SEGMENTS, segment_coverage  # noqa: E402
from raster import rasterize, apply_overlay, cells_won as compute_cells_won, CELL_ON, score_grid  # noqa: E402
from emit import enforce_floor, write_icon, lint, CH_FLOOR, MAX_LIT_COLORS, MIN_FEATURE_CELLS  # noqa: E402
from preview import render_preview  # noqa: E402
from palette import PALETTE  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(HERE, "iconlib", "editor_assets")
ICONS_DIR = os.path.join(HERE, "icons")
MAPS_DIR = os.path.join(HERE, "maps")
PREVIEWS_DIR = os.path.join(HERE, "previews")

# Distinct debug swatches for the segmented view -- deliberately NOT the
# same as PALETTE (that would look like an already-final color choice).
DEBUG_SWATCHES = [
    (230, 25, 75), (60, 180, 75), (255, 225, 25), (0, 130, 200), (245, 130, 48),
    (145, 30, 180), (70, 240, 240), (240, 50, 230), (210, 245, 60), (250, 190, 212),
    (0, 128, 128), (220, 190, 255),
]


class State:
    """All mutable session state lives here -- single icon per editor
    process, matching `python3 icon_editor.py assets/apple.png`."""

    def __init__(self, png_path, max_segments):
        self.png_path = png_path
        self.name = os.path.splitext(os.path.basename(png_path))[0]
        self.map_path = os.path.join(MAPS_DIR, self.name + ".json")
        self.max_segments = max_segments
        self.overlay = {}
        self.reload()

    def reload(self, max_segments=None):
        if max_segments is not None:
            self.max_segments = max_segments
        existing = mapio.load_map(self.map_path)
        (self.img, self.fills, self.labels, self.decisions,
         overlay, self.mode, self.intensity) = mapio.build(
            self.png_path, existing_map=existing, max_segments=self.max_segments)
        if existing is not None:
            self.overlay = overlay  # only trust the file's overlay on a fresh reload
        self.recompute()

    def recompute(self):
        self.pixels_raw = rasterize(self.fills, self.labels, self.decisions)
        self.pixels = enforce_floor(apply_overlay(self.pixels_raw, self.overlay))
        self.won = compute_cells_won(self.fills, self.labels, self.decisions)
        self.problems = lint(self.pixels, self.fills, self.decisions, self.won, self.intensity)
        _, score_by_seg = score_grid(self.fills, self.labels, self.decisions)
        winner = [None] * (W * H)
        coverage_by_seg = [segment_coverage(self.labels, i, W, H) for i in range(len(self.fills))]
        for y in range(H):
            for x in range(W):
                best_seg, best_score = None, 0.0
                for i in range(len(self.fills)):
                    if score_by_seg[i] is None:
                        continue
                    if coverage_by_seg[i][y][x] < CELL_ON:
                        continue
                    s = score_by_seg[i][y][x]
                    if s > best_score:
                        best_score, best_seg = s, i
                winner[y * W + x] = best_seg
        self.winner = winner

    def segmented_view_data_url(self):
        w, h = self.img.size
        out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        opx = out.load()
        px = self.img.load()
        for y in range(h):
            row = self.labels[y]
            for x in range(w):
                seg = row[x]
                if seg is None:
                    continue
                r, g, b = DEBUG_SWATCHES[seg % len(DEBUG_SWATCHES)]
                opx[x, y] = (r, g, b, px[x, y][3])
        buf = io.BytesIO()
        out.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    def source_data_url(self):
        buf = io.BytesIO()
        self.img.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    def preview_data_url(self):
        img = render_preview(self.pixels, self.intensity)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    def to_json(self):
        return {
            "name": self.name,
            "png_path": self.png_path,
            "mode": self.mode,
            "max_segments": self.max_segments,
            "intensity": self.intensity,
            "source_data_url": self.source_data_url(),
            "segmented_data_url": self.segmented_view_data_url(),
            "preview_data_url": self.preview_data_url(),
            "debug_swatches": DEBUG_SWATCHES,
            "fills": [{"rgb": list(rgb), "count": cnt, "frac": frac} for rgb, cnt, frac in self.fills],
            "decisions": [
                {
                    "role": d["role"],
                    "color": list(d["color"]) if d.get("color") else None,
                    "priority": d.get("priority", 1.0),
                    "merge_into": d.get("merge_into"),
                }
                for d in self.decisions
            ],
            "overlay": self.overlay,
            "cells_won": self.won,
            "winner": self.winner,
            "pixels": [list(p) for p in self.pixels],
            "problems": self.problems,
            "palette": {k: list(v) for k, v in PALETTE.items()},
            "limits": {
                "CELL_ON": CELL_ON, "CH_FLOOR": CH_FLOOR,
                "MAX_LIT_COLORS": MAX_LIT_COLORS, "MIN_FEATURE_CELLS": MIN_FEATURE_CELLS,
                "MAX_SEGMENTS": MAX_SEGMENTS,
            },
        }


def make_handler(state):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

        def _send_json(self, obj, code=200):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_file(self, path, ctype):
            with open(path, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self):
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            return json.loads(raw or b"{}")

        def do_GET(self):
            if self.path == "/" or self.path == "/index.html":
                return self._send_file(os.path.join(ASSETS_DIR, "index.html"), "text/html")
            if self.path == "/app.js":
                return self._send_file(os.path.join(ASSETS_DIR, "app.js"), "application/javascript")
            if self.path == "/style.css":
                return self._send_file(os.path.join(ASSETS_DIR, "style.css"), "text/css")
            if self.path == "/api/state":
                return self._send_json(state.to_json())
            self.send_response(404)
            self.end_headers()

        def do_POST(self):
            try:
                if self.path == "/api/decisions":
                    body = self._read_json()
                    for i, d in enumerate(body.get("decisions", [])):
                        if i >= len(state.decisions):
                            break
                        target = state.decisions[i]
                        target["role"] = d.get("role", target["role"])
                        target["priority"] = float(d.get("priority", target.get("priority", 1.0)))
                        color = d.get("color")
                        target["color"] = tuple(color) if color else None
                        if target["role"] == "merge":
                            target["merge_into"] = d.get("merge_into")
                    state.recompute()
                    return self._send_json(state.to_json())

                if self.path == "/api/overlay":
                    body = self._read_json()
                    state.overlay = {str(k): list(v) for k, v in body.get("overlay", {}).items()}
                    state.recompute()
                    return self._send_json(state.to_json())

                if self.path == "/api/segments":
                    body = self._read_json()
                    n = int(body.get("max_segments", state.max_segments))
                    n = max(1, min(MAX_SEGMENTS, n))
                    # preserve current in-memory decisions as if they'd been
                    # saved, so re-segmenting doesn't discard un-saved edits
                    state_map = mapio.to_map_obj(state.png_path, state.fills, state.decisions,
                                                  state.overlay, state.intensity, state.max_segments)
                    existing_before = state_map
                    state.max_segments = n
                    (state.img, state.fills, state.labels, state.decisions,
                     overlay, state.mode, state.intensity) = mapio.build(
                        state.png_path, existing_map=existing_before, max_segments=n)
                    state.recompute()
                    return self._send_json(state.to_json())

                if self.path == "/api/save":
                    os.makedirs(ICONS_DIR, exist_ok=True)
                    os.makedirs(PREVIEWS_DIR, exist_ok=True)
                    icon_path = os.path.join(ICONS_DIR, state.name + ".py")
                    preview_path = os.path.join(PREVIEWS_DIR, state.name + ".png")
                    write_icon(state.pixels, icon_path,
                               name_comment="Generated by icon_editor.py from %s -- edit maps/%s.json (via the editor), not this file."
                                             % (os.path.relpath(state.png_path, HERE), state.name))
                    render_preview(state.pixels, state.intensity, preview_path)
                    map_obj = mapio.to_map_obj(state.png_path, state.fills, state.decisions,
                                                state.overlay, state.intensity, state.max_segments)
                    mapio.save_map(state.map_path, map_obj)
                    return self._send_json({"ok": True, "icon_path": icon_path, "preview_path": preview_path,
                                             "map_path": state.map_path})

                if self.path == "/api/push":
                    body = self._read_json()
                    port = body.get("port", "/dev/cu.usbmodem1101")
                    icon_path = os.path.join(ICONS_DIR, state.name + ".py")
                    if not os.path.exists(icon_path):
                        return self._send_json({"ok": False, "error": "save the icon first (no icons/%s.py yet)" % state.name})
                    try:
                        result = subprocess.run(
                            ["python3", "-m", "mpremote", "connect", port, "cp", icon_path, ":icons/%s.py" % state.name],
                            capture_output=True, text=True, timeout=30)
                    except FileNotFoundError:
                        return self._send_json({"ok": False, "error": "mpremote not found -- pip install mpremote, "
                                                                        "and run this on the machine with the device attached."})
                    except Exception as e:
                        return self._send_json({"ok": False, "error": str(e)})
                    return self._send_json({"ok": result.returncode == 0, "stdout": result.stdout, "stderr": result.stderr})

                self.send_response(404)
                self.end_headers()
            except Exception as e:
                self._send_json({"ok": False, "error": "%s: %s" % (type(e).__name__, e)}, code=500)

    return Handler


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("png_path", help="source PNG/JPEG, e.g. assets/apple.png")
    ap.add_argument("--port", type=int, default=8756)
    ap.add_argument("--segments", type=int, default=MAX_SEGMENTS)
    ap.add_argument("--no-open", action="store_true", help="don't auto-open a browser tab")
    args = ap.parse_args()

    if not os.path.exists(args.png_path):
        print("no such file:", args.png_path, file=sys.stderr)
        return 1

    state = State(args.png_path, args.segments)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(state))
    url = "http://127.0.0.1:%d/" % args.port
    print("Icon editor for %s -- serving %s" % (state.name, url))
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
