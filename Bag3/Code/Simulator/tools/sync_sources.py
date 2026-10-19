#!/usr/bin/env python3
"""
Bundle Bag3 MockWand lib + game sources, and the IconDisplay files the
display panel runs, into Simulator/vendor/.

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
REPO = os.path.abspath(os.path.join(ROOT, "..", "..", ".."))  # Bag3/Code/Simulator -> repo root

# Lib and games both come from the Bag3 MockWand tree. Its leds.py is the
# 5x5 row-major (25 LED) matrix the renderer and golden frames assume.
GAMES_SRC = os.path.join(REPO, "Bag3", "Code", "BroadcastCode", "MockWand")
LIB_SRC = os.path.join(GAMES_SRC, "lib")
HUBTYPE_SRC = os.path.join(GAMES_SRC, "hubtype.txt")


def _game_src(name):
    """Where a MockWand game file lives.

    They are moving out of the MockWand root into MockWand/games/ -- the same
    directory a pulled game lands in on the device -- so look in both rather
    than pinning this tool to one layout. Missing files are reported by the
    copy step, not swallowed here.
    """
    nested = os.path.join(GAMES_SRC, "games", name)
    return nested if os.path.exists(nested) else os.path.join(GAMES_SRC, name)


VENDOR = os.path.join(ROOT, "vendor")
VENDOR_LIB = os.path.join(VENDOR, "lib")
VENDOR_GAMES = os.path.join(VENDOR, "games")
MANIFEST = os.path.join(VENDOR, "MANIFEST.json")

# Modules copied verbatim from MockWand/lib.
VERBATIM_LIBS = [
    "leds.py",
    "buzzer.py",
    "brightness.py",
    "hubtype.py",
    "game_tags.py",
    "actions.py",
    "battery.py",
    "espnow_manager.py",
    # Party games: pwire/party/splatpair run through the transform; pairing
    # and splat_api run sync. Below splat_api, py/shims/splat_hub.py stands
    # in for splat_hub/splat_link/ble_splat (BLE).
    "pwire.py",
    "party.py",
    "splatpair.py",
    "pairing.py",
    "splat_api.py",
]

# The icon display's half of two-device games, for the display panel
# (py/icon_host.py). Its libs come from the IconDisplay tree, not MockWand:
# the two espnow_manager.py copies differ (antenna setting).
DISPLAY_SRC = os.path.join(REPO, "Bag3", "Code", "BroadcastCode", "IconDisplay")
DISPLAY_FILES = [
    # (source relative to DISPLAY_SRC, vendor path relative to vendor/)
    ("icon_store.py", "display/lib/icon_store.py"),
    ("lib/display_tags.py", "display/lib/display_tags.py"),
    ("lib/shapes.py", "display/lib/shapes.py"),
    ("lib/espnow_manager.py", "display/lib/espnow_manager.py"),
    ("games/goalrace.py", "display/games/goalrace.py"),
]
# Icons each display game reads, from IconDisplay/icons/, vendored as
# display/games/<game>_icons/<name>.py (the layout a pulled game has).
DISPLAY_GAME_ICONS = {
    "goalrace": ["ready", "tree", "whale"],
}

# Game modules to bundle (from Bag3/Code/BroadcastCode/MockWand).
# target.py is not a game; color_quest.py imports SCORE_MAC from it.
GAMES = [
    "jump.py",
    "shake.py",
    "shake_rainbow.py",
    "sound.py",
    "rainbow.py",
    "jumpin.py",
    "nfc_sound.py",
    "gestures.py",
    "simpleicecream.py",
    "melody.py",
    "cooking.py",
    "multiicecream.py",
    "freeze_dance.py",
    "goalrace.py",
    "color_quest.py",
    "finddevice.py",
    "partytest.py",
    "splattag.py",
    "relaycolor.py",
    "target.py",
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
        plan.append((_game_src(name), os.path.join("games", name)))
    for src_rel, dest_rel in DISPLAY_FILES:
        plan.append((os.path.join(DISPLAY_SRC, src_rel), dest_rel))
    for game, icons in DISPLAY_GAME_ICONS.items():
        for name in icons:
            plan.append((os.path.join(DISPLAY_SRC, "icons", name + ".py"),
                         "display/games/%s_icons/%s.py" % (game, name)))
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
            # A game that moved between the MockWand root and MockWand/games
            # is not missing, it is recorded at its old path -- one sync run
            # rewrites the manifest. Say which it is rather than making the
            # reader guess from a bare "missing".
            moved_to = _game_src(os.path.basename(info["source"]))
            if os.path.isfile(moved_to):
                errors.append("source moved: %s is now %s (re-run sync)"
                              % (info["source"], os.path.relpath(moved_to, REPO)))
            else:
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
        help="verify vendor/ matches the source trees; exit 1 on drift",
    )
    args = ap.parse_args()
    if args.check:
        sys.exit(check())
    print("Syncing Bag3 MockWand lib + games into Simulator/vendor/ ...")
    sync()
    print("Done.")


if __name__ == "__main__":
    main()
