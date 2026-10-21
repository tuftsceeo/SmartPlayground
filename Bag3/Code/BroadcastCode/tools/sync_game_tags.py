"""Report drift between the Bag3 wand's game tags and the copies that use them.

Source of truth: BroadcastCode/MockWand/lib/game_tags.py (GAME_TAGS,
CONTROL_TAGS, HIDDEN_TAGS). Paths below are relative to Bag3/Code/.

Copies checked:
  Stations/NFC Station/game_tags.py
      Sets must match the source. Allowed extra: "unpair" (a station/control
      card, not a wand game), in any set.
  BroadcastCode/EspnowModem/MockWandEUM/lib/game_tags.py
      Sets must match the source. Allowed missing: "splatecho" (the EUM wand
      has no direct-Splat game).
  BroadcastCode/ChatBroadcast/js/gameName.js  WAND_RESERVED
      Must contain every GAME_TAGS | CONTROL_TAGS | HIDDEN_TAGS name, so a
      generated game slug can never collide with a wand tag. Extra names are
      allowed (other reserved words, e.g. "unpair", "scoreboard").
  Simulator/vendor/lib/game_tags.py
      Informational only: MANIFEST.json vendors it from Bag2, so differences
      are printed as INFO and never fail --check.

Not covered: Bag3/Code/lib/, Live_Page/, Bag1/, Bag2/.

Modes:
  (default)  print every difference; exit 0.
  --check    print every difference; exit 1 if any non-allowed one exists.
  --write    overwrite the NFC Station copy with the source, only when the
             station has no tags outside the source (an allowed extra such as
             "unpair" would be lost, so the write is refused). Nothing else is
             ever written.
"""

import ast
import re
import shutil
import sys
from pathlib import Path

CODE = Path(__file__).resolve().parents[2]  # Bag3/Code
SOURCE = CODE / "BroadcastCode/MockWand/lib/game_tags.py"
STATION = CODE / "Stations/NFC Station/game_tags.py"
EUM = CODE / "BroadcastCode/EspnowModem/MockWandEUM/lib/game_tags.py"
SIMULATOR = CODE / "Simulator/vendor/lib/game_tags.py"
GAME_NAME_JS = CODE / "BroadcastCode/ChatBroadcast/js/gameName.js"

SET_NAMES = ("GAME_TAGS", "CONTROL_TAGS", "HIDDEN_TAGS")

# path -> (allowed extra names, allowed missing names)
PY_COPIES = {
    STATION: ({"unpair"}, set()),
    EUM: (set(), {"splatecho"}),
}


def read_tag_sets(path):
    """Return {set name: set of str} from literal assignments in a .py file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in SET_NAMES:
                found[target.id] = set(ast.literal_eval(node.value))
    missing = [n for n in SET_NAMES if n not in found]
    if missing:
        raise ValueError(f"{path}: no literal assignment for {', '.join(missing)}")
    return found


def read_wand_reserved(path):
    """Return the string entries of `export const WAND_RESERVED = [...]`."""
    text = path.read_text(encoding="utf-8")
    m = re.search(r"WAND_RESERVED\s*=\s*\[(.*?)\]", text, re.S)
    if not m:
        raise ValueError(f"{path}: WAND_RESERVED array not found")
    return set(re.findall(r"""["']([^"']+)["']""", m.group(1)))


def compare_py(source, copy, allowed_extra, allowed_missing):
    """Return (errors, allowed) lists of difference lines for one copy."""
    errors, allowed = [], []
    for name in SET_NAMES:
        for tag in sorted(copy[name] - source[name]):
            line = f"{name}: extra {tag!r}"
            (allowed if tag in allowed_extra else errors).append(line)
        for tag in sorted(source[name] - copy[name]):
            line = f"{name}: missing {tag!r}"
            (allowed if tag in allowed_missing else errors).append(line)
    return errors, allowed


def rel(path):
    return path.relative_to(CODE).as_posix()


def run(write=False, out=print):
    """Print the report. Return the number of non-allowed differences."""
    source = read_tag_sets(SOURCE)
    out(f"source: {rel(SOURCE)}")
    failures = 0

    for path, (extra_ok, missing_ok) in PY_COPIES.items():
        if not path.exists():
            out(f"\n{rel(path)}: MISSING FILE")
            failures += 1
            continue
        errors, allowed = compare_py(source, read_tag_sets(path), extra_ok, missing_ok)
        status = "DRIFT" if errors else "ok"
        out(f"\n{rel(path)}: {status}")
        for line in errors:
            out(f"  DIFF    {line}")
        for line in allowed:
            out(f"  allowed {line}")
        failures += len(errors)

    reserved = read_wand_reserved(GAME_NAME_JS)
    wand_names = set().union(*source.values())
    missing = sorted(wand_names - reserved)
    out(f"\n{rel(GAME_NAME_JS)} WAND_RESERVED: {'DRIFT' if missing else 'ok'}")
    for tag in missing:
        out(f"  DIFF    missing {tag!r}")
    failures += len(missing)

    if SIMULATOR.exists():
        errors, _ = compare_py(source, read_tag_sets(SIMULATOR), set(), set())
        out(f"\n{rel(SIMULATOR)}: {'differs (INFO, vendored from Bag2)' if errors else 'ok'}")
        for line in errors:
            out(f"  info    {line}")

    if write:
        station = read_tag_sets(STATION)
        extras = sorted(set().union(*station.values()) - wand_names)
        if extras:
            out(f"\n--write refused: {rel(STATION)} has tags not in the source "
                f"({', '.join(extras)}); merge by hand.")
            return failures + 1
        shutil.copyfile(SOURCE, STATION)
        out(f"\nwrote {rel(STATION)} from source")

    return failures


def main(argv):
    args = set(argv)
    unknown = args - {"--check", "--write"}
    if unknown:
        print(f"usage: sync_game_tags.py [--check] [--write]; unknown: {' '.join(sorted(unknown))}")
        return 2
    failures = run(write="--write" in args)
    print(f"\n{failures} non-allowed difference(s)")
    if "--check" in args and failures:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
