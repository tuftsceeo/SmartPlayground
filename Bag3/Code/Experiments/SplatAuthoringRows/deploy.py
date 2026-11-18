"""Stage the experiment's wand files for a bench wand.

Reads wand/manifest.js (WAND_FILES), plus the host games when --host-games is
given, and copies each file to <out>/<remotePath>. Nothing touches a serial
port: it prints the mpremote commands to run by hand. Before running them,
follow Bag3/Code/HARDWARE_PROTOCOL.md and
known_issues/2026-11-12-wand-mpremote-copy-fails.md (mpremote copies to a
running Splat host wand are an open issue).

    python3 deploy.py --out /tmp/wand_stage [--host-games] [--colorpads] [--port COM7]
"""
import argparse
import glob
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WAND = os.path.join(HERE, "wand")


def manifest_files():
    text = open(os.path.join(WAND, "manifest.js")).read()
    pairs = re.findall(r"path:\s*'([^']+)',\s*remotePath:\s*'([^']+)'", text)
    if not pairs:
        sys.exit("no WAND_FILES entries found in wand/manifest.js")
    return pairs


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", required=True, help="empty directory to stage into")
    ap.add_argument("--host-games", action="store_true", help="also stage games/host_*.py")
    ap.add_argument("--colorpads", action="store_true", help="also stage games/colorpads.py (type 2)")
    ap.add_argument("--port", default="PORT", help="serial port for the printed commands")
    args = ap.parse_args()
    if os.path.exists(args.out) and os.listdir(args.out):
        sys.exit("%s is not empty" % args.out)
    pairs = manifest_files()
    if args.host_games:
        for p in sorted(glob.glob(os.path.join(WAND, "games", "host_*.py"))):
            rel = os.path.relpath(p, WAND).replace(os.sep, "/")
            pairs.append((rel, "/" + rel))
    if args.colorpads:
        pairs.append(("games/colorpads.py", "/games/colorpads.py"))
    for src, remote in pairs:
        dst = os.path.join(args.out, remote.lstrip("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(os.path.join(WAND, src), dst)
    print("staged %d files in %s" % (len(pairs), args.out))
    for _, remote in pairs:
        print("mpremote connect %s resume fs cp %s :%s"
              % (args.port, os.path.join(args.out, remote.lstrip("/")), remote))


if __name__ == "__main__":
    main()
