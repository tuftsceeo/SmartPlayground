#!/usr/bin/env python3
"""
Generate ChatBroadcast/js/splat/splatActions.js from the Splat Companion's
own action tables.

Usage:
    python3 tools/sync_splat_actions.py          # rewrite splatActions.js
    python3 tools/sync_splat_actions.py --check  # exit 1 if splatActions.js drifts

Bag3/Code/BroadcastCode/SplatCompanion/splat_api.py is the source of truth:
its module-level COLOR_RGB, NOTE_VALUES and ANIMAL_SOUNDS dicts are the
names splat.color(), splat.note() and splat.sound() accept on the device.
splatActions.js is the generated browser copy that ChatBroadcast puts in
the system prompt and checks a Splat game against before sending.

The tables are read with ast and literal_eval, never imported: splat_api.py
is MicroPython and imports nothing that exists here anyway. A table that is
missing, assigned twice, or not a plain dict literal with string keys
aborts the run naming it, and nothing is written.
"""

import argparse
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CHATBROADCAST = os.path.dirname(HERE)
BROADCASTCODE = os.path.dirname(CHATBROADCAST)

SOURCE = os.path.join(BROADCASTCODE, "SplatCompanion", "splat_api.py")
OUT_PATH = os.path.join(CHATBROADCAST, "js", "splat", "splatActions.js")

# (table in splat_api.py, export name in splatActions.js)
TABLES = (
    ("COLOR_RGB", "COLORS"),
    ("NOTE_VALUES", "NOTES"),
    ("ANIMAL_SOUNDS", "SOUNDS"),
)

DOCSTRING = """/**
 * Splat action names the Splat Companion accepts, by category.
 *
 * Generated from Bag3/Code/BroadcastCode/SplatCompanion/splat_api.py
 * (COLOR_RGB, NOTE_VALUES, ANIMAL_SOUNDS) by
 * ChatBroadcast/tools/sync_splat_actions.py -- do not hand-edit. Read by
 * js/splat/splatActionCheck.js for the system prompt and the send-time
 * check.
 */
"""


class TableError(Exception):
    """A source table that cannot be trusted. Always names the table."""


def read_tables(path=SOURCE):
    """Return {table_name: sorted list of names} for every entry in TABLES."""
    try:
        with open(path, "r") as f:
            tree = ast.parse(f.read(), filename=path)
    except OSError as exc:
        raise TableError("%s: cannot read (%s)" % (path, exc))

    found = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in dict(TABLES):
                if target.id in found:
                    raise TableError("%s: %s is assigned more than once"
                                     % (path, target.id))
                found[target.id] = node.value

    out = {}
    for name, _ in TABLES:
        if name not in found:
            raise TableError("%s: no module-level %s" % (path, name))
        try:
            value = ast.literal_eval(found[name])
        except ValueError:
            raise TableError("%s: %s is not a literal" % (path, name))
        if not isinstance(value, dict) or not value:
            raise TableError("%s: %s is not a non-empty dict" % (path, name))
        bad = [k for k in value if not isinstance(k, str)]
        if bad:
            raise TableError("%s: %s has non-string keys %r" % (path, name, bad))
        out[name] = sorted(value)
    return out


def render(tables):
    """The full text of splatActions.js for these tables."""
    parts = [DOCSTRING]
    for name, export in TABLES:
        parts.append("export const %s = [\n" % export)
        for n in tables[name]:
            parts.append("    '%s',\n" % n)
        parts.append("];\n")
    return "".join(parts)


def read_current():
    try:
        with open(OUT_PATH, "r") as f:
            return f.read()
    except OSError:
        return None


def check(tables):
    wanted = render(tables)
    current = read_current()
    rel = os.path.relpath(OUT_PATH, BROADCASTCODE)
    if current is None:
        print("FAIL: %s missing -- run sync_splat_actions.py" % rel, file=sys.stderr)
        return 1
    if current == wanted:
        n = sum(len(v) for v in tables.values())
        print("OK: splatActions.js matches SplatCompanion/splat_api.py (%d names)" % n)
        return 0
    print("FAIL: %s has drifted from SplatCompanion/splat_api.py" % rel,
          file=sys.stderr)
    print("  run: python3 ChatBroadcast/tools/sync_splat_actions.py", file=sys.stderr)
    return 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if splatActions.js differs from splat_api.py")
    args = ap.parse_args(argv)
    try:
        tables = read_tables()
    except TableError as exc:
        print("FAIL: %s" % exc, file=sys.stderr)
        return 1
    if args.check:
        return check(tables)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        f.write(render(tables))
    print("wrote %s" % os.path.relpath(OUT_PATH, BROADCASTCODE))
    return 0


if __name__ == "__main__":
    sys.exit(main())
