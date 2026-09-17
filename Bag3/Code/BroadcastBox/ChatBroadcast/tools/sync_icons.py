#!/usr/bin/env python3
"""
Generate ChatBroadcast/js/ledicons/defaultIcons.js from the icon display's
own icons/ directory.

Usage:
    python3 tools/sync_icons.py          # rewrite defaultIcons.js
    python3 tools/sync_icons.py --check  # exit 1 if defaultIcons.js drifts

The device tree Bag3/Code/BroadcastBox/IconDisplay/icons/ is the source of
truth; defaultIcons.js is the generated browser copy. Both sides hold the
same linear PWM duty bytes, so this is a parse and a reshape -- device files
are 16 rows of 16 "(r, g, b)" tuples, the browser file is one flat 768-value
row-major array per icon. There is no colour conversion anywhere in here;
duty -> sRGB happens in the browser at render time, in ledColor.js.

Any icon file that will not parse, is not 16x16, or does not yield 768 bytes
aborts the whole run naming the file. Nothing is written on a failure, so a
partial library cannot be emitted.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

W = 16
H = 16
VALUES = W * H * 3

HERE = os.path.dirname(os.path.abspath(__file__))
CHATBROADCAST = os.path.dirname(HERE)
BROADCASTBOX = os.path.dirname(CHATBROADCAST)

ICONS_DIR = os.path.join(BROADCASTBOX, "IconDisplay", "icons")
OUT_PATH = os.path.join(CHATBROADCAST, "js", "ledicons", "defaultIcons.js")

TUPLE_RE = re.compile(r"\(\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*\)")
SIZE_RE = re.compile(r"^SIZE\s*=\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)\s*$")

DOCSTRING = """/**
 * Default 16x16 LED icons, as flat linear-PWM-duty RGB arrays (768 values,
 * row-major from top-left).
 *
 * Generated from Bag3/Code/BroadcastBox/IconDisplay/icons/ by
 * ChatBroadcast/tools/sync_icons.py -- do not hand-edit. They are the
 * starting library a teacher edits and a generated display game refers to by
 * name. Duty, NOT sRGB -- convert at the boundary with ledColor.js before
 * putting one on screen.
 */
"""


class IconError(Exception):
    """An icon file that cannot be trusted. Always names its file."""


def parse_icon_file(path):
    """Return 768 duty bytes from one icons/<name>.py.

    Mirrors what icon_store.read_icon() accepts -- an optional SIZE line and
    lines of "(r, g, b)" tuples -- but refuses anything this generator is not
    prepared to reshape instead of coercing it.
    """
    try:
        with open(path, "r") as f:
            text = f.read()
    except OSError as exc:
        raise IconError("%s: cannot read (%s)" % (path, exc))

    size = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("SIZE"):
            continue
        m = SIZE_RE.match(stripped)
        if not m:
            raise IconError("%s: unparseable SIZE line: %s" % (path, stripped))
        size = (int(m.group(1)), int(m.group(2)))
        break

    if size is not None and size != (W, H):
        raise IconError("%s: SIZE is %dx%d, expected %dx%d"
                        % (path, size[0], size[1], W, H))

    values = []
    rows = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("("):
            continue
        rows += 1
        found = TUPLE_RE.findall(stripped)
        # Every "(...)" on a pixel row has to be a triple; a stray "(1, 2)"
        # would be dropped by findall and silently shorten the row.
        if len(found) != stripped.count("("):
            raise IconError("%s: row %d has a malformed pixel tuple: %s"
                            % (path, rows, stripped))
        if len(found) != W:
            raise IconError("%s: row %d has %d pixels, expected %d"
                            % (path, rows, len(found), W))
        for triple in found:
            for component in triple:
                v = int(component)
                if v < 0 or v > 255:
                    raise IconError("%s: row %d has duty %d outside 0-255"
                                    % (path, rows, v))
                values.append(v)

    if rows != H:
        raise IconError("%s: %d pixel rows, expected %d" % (path, rows, H))
    if len(values) != VALUES:
        raise IconError("%s: parsed %d values, expected %d"
                        % (path, len(values), VALUES))
    return values


def collect_icons():
    """Every icons/<name>.py, parsed, name-sorted. Raises on the first bad one."""
    if not os.path.isdir(ICONS_DIR):
        raise IconError("%s: icon directory missing" % ICONS_DIR)

    names = sorted(
        fn[:-3] for fn in os.listdir(ICONS_DIR)
        if fn.endswith(".py") and not fn.startswith("_")
    )
    if not names:
        raise IconError("%s: no icon files found" % ICONS_DIR)

    out = []
    for name in names:
        out.append((name, parse_icon_file(os.path.join(ICONS_DIR, name + ".py"))))
    return out


def render(icons):
    """The full text of defaultIcons.js for these icons."""
    parts = [DOCSTRING, "export const DEFAULT_ICONS = {\n"]
    for name, values in icons:
        parts.append("    %s: [\n" % name)
        for row in range(H):
            row_values = values[row * W * 3:(row + 1) * W * 3]
            parts.append("        " + ",".join(str(v) for v in row_values) + ",\n")
        parts.append("    ],\n")
    parts.append("};\n")
    return "".join(parts)


def read_current():
    try:
        with open(OUT_PATH, "r") as f:
            return f.read()
    except OSError:
        return None


def check(icons):
    wanted = render(icons)
    current = read_current()
    if current is None:
        print("FAIL: %s missing -- run sync_icons.py"
              % os.path.relpath(OUT_PATH, BROADCASTBOX), file=sys.stderr)
        return 1
    if current == wanted:
        print("OK: defaultIcons.js matches IconDisplay/icons/ (%d icons)" % len(icons))
        return 0

    print("FAIL: defaultIcons.js has drifted from IconDisplay/icons/:", file=sys.stderr)
    for line in drift_report(current, wanted, icons):
        print("  - %s" % line, file=sys.stderr)
    print("  run: python3 ChatBroadcast/tools/sync_icons.py", file=sys.stderr)
    return 1


def drift_report(current, wanted, icons):
    """Say what differs, in icon terms where possible."""
    have = set(icon_names_in_js(current))
    want = set(name for name, _ in icons)
    lines = []
    for name in sorted(want - have):
        lines.append("missing from defaultIcons.js: %s" % name)
    for name in sorted(have - want):
        lines.append("in defaultIcons.js but not on the display: %s" % name)
    if not lines:
        current_lines = current.splitlines()
        wanted_lines = wanted.splitlines()
        for i in range(max(len(current_lines), len(wanted_lines))):
            a = current_lines[i] if i < len(current_lines) else "<end of file>"
            b = wanted_lines[i] if i < len(wanted_lines) else "<end of file>"
            if a != b:
                lines.append("first difference at line %d" % (i + 1))
                lines.append("  file:      %s" % a.strip()[:90])
                lines.append("  generated: %s" % b.strip()[:90])
                break
    return lines


def icon_names_in_js(text):
    return re.findall(r"^    ([a-z_][a-z0-9_]*): \[$", text, re.M)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="verify defaultIcons.js matches the device icons; exit 1 on drift")
    args = ap.parse_args()

    try:
        icons = collect_icons()
    except IconError as exc:
        print("FAIL: %s" % exc, file=sys.stderr)
        sys.exit(1)

    if args.check:
        sys.exit(check(icons))

    with open(OUT_PATH, "w") as f:
        f.write(render(icons))
    print("wrote %s (%d icons: %s)"
          % (os.path.relpath(OUT_PATH, CHATBROADCAST), len(icons),
             ", ".join(name for name, _ in icons)))


if __name__ == "__main__":
    main()
