#!/usr/bin/env python3
"""
Bundle Bag2 lib + wand game sources into Simulator/vendor/.

Usage:
    python tools/sync_sources.py          # copy + write MANIFEST.json
    python tools/sync_sources.py --check  # exit 1 if vendor drifts from source

This is a mitigation for the hand-duplication hazard AGENTS.md warns about —
Pyodide cannot read the real filesystem live.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO = os.path.abspath(os.path.join(ROOT, ".."))

LIB_SRC = os.path.join(REPO, "Bag2", "Code", "lib")
GAMES_SRC = os.path.join(REPO, "Bag2", "Code", "Wand Module")
HUBTYPE_SRC = os.path.join(GAMES_SRC, "hubtype.txt")

VENDOR = os.path.join(ROOT, "vendor")
VENDOR_LIB = os.path.join(VENDOR, "lib")
VENDOR_GAMES = os.path.join(VENDOR, "games")
MANIFEST = os.path.join(VENDOR, "MANIFEST.json")

# Modules run verbatim (copied from Bag2/Code/lib).
VERBATIM_LIBS = [
    "leds.py",
    "buzzer.py",
    "brightness.py",
    "hubtype.py",
    "game_tags.py",
    "actions.py",
    "battery.py",
]

# Game modules to bundle.
GAMES = [
    "jump.py",
    "shake.py",
    "shake_rainbow.py",
    "sound.py",
    "rainbow.py",
    "jumpin.py",
]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_plan():
    """Return list of (src, dest_rel) pairs."""
    plan = []
    for name in VERBATIM_LIBS:
        plan.append((os.path.join(LIB_SRC, name), os.path.join("lib", name)))
    for name in GAMES:
        plan.append((os.path.join(GAMES_SRC, name), os.path.join("games", name)))
    if os.path.isfile(HUBTYPE_SRC):
        plan.append((HUBTYPE_SRC, "hubtype.txt"))
    return plan


def build_manifest(plan):
    entries = {}
    for src, dest_rel in plan:
        if not os.path.isfile(src):
            raise FileNotFoundError("missing source: %s" % src)
        entries[dest_rel.replace("\\", "/")] = {
            "sha256": sha256_file(src),
            "source": os.path.relpath(src, REPO).replace("\\", "/"),
        }
    return {
        "version": 1,
        "files": entries,
    }


def sync():
    plan = collect_plan()
    os.makedirs(VENDOR_LIB, exist_ok=True)
    os.makedirs(VENDOR_GAMES, exist_ok=True)

    for src, dest_rel in plan:
        dest = os.path.join(VENDOR, dest_rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(src, dest)
        print("  copied %s -> vendor/%s" % (os.path.relpath(src, REPO), dest_rel))

    manifest = build_manifest(plan)
    # Also hash the vendor copies (should match source).
    for dest_rel, info in manifest["files"].items():
        info["vendor_sha256"] = sha256_file(os.path.join(VENDOR, dest_rel))

    with open(MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")
    print("  wrote vendor/MANIFEST.json (%d files)" % len(manifest["files"]))


def check():
    if not os.path.isfile(MANIFEST):
        print("FAIL: vendor/MANIFEST.json missing — run sync_sources.py", file=sys.stderr)
        return 1

    with open(MANIFEST) as f:
        manifest = json.load(f)

    plan = collect_plan()
    expected = {dest_rel.replace("\\", "/"): src for src, dest_rel in plan}
    errors = []

    for dest_rel, info in manifest["files"].items():
        src = os.path.join(REPO, info["source"])
        vendor_path = os.path.join(VENDOR, dest_rel)
        if not os.path.isfile(src):
            errors.append("source missing: %s" % info["source"])
            continue
        if not os.path.isfile(vendor_path):
            errors.append("vendor missing: %s" % dest_rel)
            continue
        src_hash = sha256_file(src)
        vendor_hash = sha256_file(vendor_path)
        if src_hash != info["sha256"]:
            errors.append(
                "source drifted from manifest: %s (re-run sync)" % info["source"]
            )
        if vendor_hash != src_hash:
            errors.append(
                "vendor/%s differs from source %s" % (dest_rel, info["source"])
            )
        expected.pop(dest_rel, None)

    for dest_rel in sorted(expected):
        errors.append("not in manifest (new file?): %s" % dest_rel)

    if errors:
        print("FAIL: vendor drift detected:", file=sys.stderr)
        for e in errors:
            print("  - %s" % e, file=sys.stderr)
        return 1

    print("OK: vendor matches sources (%d files)" % len(manifest["files"]))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check",
        action="store_true",
        help="verify vendor/ matches Bag2 sources; exit 1 on drift",
    )
    args = ap.parse_args()
    if args.check:
        sys.exit(check())
    print("Syncing Bag2 sources into Simulator/vendor/ ...")
    sync()
    print("Done.")


if __name__ == "__main__":
    main()
