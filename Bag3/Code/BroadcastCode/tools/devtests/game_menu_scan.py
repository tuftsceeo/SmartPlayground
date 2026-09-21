"""
Check the Box's and the Dial's boot-time game-menu scan against the Box/Dial
staging suffix.

A display game is staged on the Box/Dial as <slug>_icon.py (see ROLE_FILES
in code_server.py) so a wand pull and an icon_display pull for the same slug
can be served from two different files. That file is never itself a
playable game on the device running this scan -- _boot_scan_games() must
skip it, never enrol it in index.json, and never let it become the active
game by mtime.

Both firmwares run this scan with byte-identical logic (a hand-kept PEER
pair), so this drives both BboxServer and BdialServer the same way.
"""
import os, sys, tempfile, shutil

_BB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CODE_ROOT = os.path.dirname(_BB)  # Bag3/Code/, parent of BroadcastBox/ and BroadcastDial/
SCRATCH = os.path.dirname(os.path.abspath(__file__))

import time as _time
_time.sleep_ms = lambda ms: None
_time.ticks_ms = lambda: int(_time.time() * 1000)
_time.ticks_diff = lambda a, b: a - b

sys.path.insert(0, os.path.join(SCRATCH, "stubs"))

fails = []
def check(label, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + label + ("" if not detail else " -- %s" % detail))
    if not ok:
        fails.append(label)


def _write_games(games_dir, names):
    os.makedirs(games_dir, exist_ok=True)
    for name in names:
        with open(os.path.join(games_dir, name), "w") as f:
            f.write("# stub\n")


def _run_one(label, fw_dir, server_module_name, server_class_name):
    """Import <server_module_name> fresh from fw_dir, point it at a scratch
    games dir with a wand file and its staged _icon peer, run the boot scan,
    and check the peer never enters the menu or becomes active.
    """
    tmp = tempfile.mkdtemp(prefix="menu-")
    games_dir = os.path.join(tmp, "games")
    _write_games(games_dir, ["goalrace.py", "goalrace_icon.py", "tilt_tones.py"])

    # Fresh import per firmware: both define same-named globals (GAMES_DIR,
    # INDEX_PATH, ACTIVE_PATH, handlers...) and must not leak into each other.
    for mod in list(sys.modules):
        if mod in (server_module_name, "code_server", "bbox_ui", "buttons",
                    "dial_ui", "dial_input", "dial_board", "card_writer",
                    "ws1850s", "json_link", "reset_log"):
            del sys.modules[mod]

    sys.path.insert(0, fw_dir)
    try:
        server_mod = __import__(server_module_name)
    finally:
        sys.path.remove(fw_dir)

    # Point the module's own globals at the scratch tree -- these are bound
    # by `from code_server import GAMES_DIR, ACTIVE_PATH` and a local
    # INDEX_PATH computed from GAMES_DIR at import time, so all three must
    # be patched directly on the imported module.
    server_mod.GAMES_DIR = games_dir
    server_mod.INDEX_PATH = os.path.join(games_dir, "index.json")
    server_mod.ACTIVE_PATH = os.path.join(tmp, "active.txt")

    server_cls = getattr(server_mod, server_class_name)
    srv = server_cls(debug=False)
    srv._boot_scan_games()

    check("%s: staged peer never enters index.json" % label,
          "goalrace_icon" not in srv._index,
          "index: %s" % sorted(srv._index))
    check("%s: the wand game is still there" % label, "goalrace" in srv._index)
    check("%s: the other game is still there" % label, "tilt_tones" in srv._index)
    check("%s: the staged peer never becomes active" % label,
          srv._active != "goalrace_icon", "active: %r" % srv._active)

    shutil.rmtree(tmp, ignore_errors=True)


_run_one("Box", os.path.join(CODE_ROOT, "BroadcastBox", "BBoxFirmware"), "bbox_server", "BboxServer")
_run_one("Dial", os.path.join(CODE_ROOT, "BroadcastDial", "BDialFirmware"), "bdial_server", "BdialServer")

if fails:
    print("\nFAILED: %d" % len(fails))
    for f in fails:
        print("  - " + f)
    sys.exit(1)

print("\ngame menu scan OK")
