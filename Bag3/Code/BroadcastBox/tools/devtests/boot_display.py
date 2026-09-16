"""
Boot IconDisplay/main.py under MicroPython stubs.

py_compile only proves the file parses. This runs it: the boot order, the
panel construction, the idle loop, an ESP-NOW start_game dispatch, a game
load, a game with no play(), and a game that will not compile. Enough to
catch a NameError or a wrong attribute, which is most of what a first pass
gets wrong.
"""
import os, sys, tempfile, shutil, types

import os
# BroadcastBox/, two levels up from tools/devtests/.
_BB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEV = _BB + "/IconDisplay"
SCRATCH = os.path.dirname(os.path.abspath(__file__))

import time as _time
_time.sleep_ms = lambda ms: None
_ticks = [0]
def _tick():
    _ticks[0] += 10
    return _ticks[0]
_time.ticks_ms = _tick
_time.ticks_diff = lambda a, b: a - b

# Run from a scratch copy: main.py reads and writes files relative to cwd
# (hubtype.txt, icons/, /games) exactly as it would on flash.
TMP = tempfile.mkdtemp(prefix="display-")
FLASH = os.path.join(TMP, "flash")
# The repo tree now carries device names directly (goalrace.py, not
# goalrace_icon.py -- that suffix lives only in the Box/Dial staging tree),
# so flashing the tree verbatim is exactly what a real device has.
shutil.copytree(DEV, FLASH)
os.chdir(FLASH)

sys.path.insert(0, os.path.join(SCRATCH, "stubs"))
sys.path.insert(0, os.path.join(FLASH, "lib"))
sys.path.insert(0, FLASH)

# MicroPython's sys.print_exception; CPython has traceback instead.
import traceback
sys.print_exception = lambda e, *a: traceback.print_exception(type(e), e, e.__traceback__)

# MicroPython gc extras that lib/memprobe.py reads.
import gc as _gc
_gc.mem_alloc = lambda: 0
_gc.mem_free = lambda: 100_000
_gc.threshold = lambda *a: 0

import game_store
game_store.GAMES_DIR = os.path.join(FLASH, "games")

FAILURES = []
def check(label, ok, detail=""):
    print("%-4s %s%s" % ("ok" if ok else "FAIL", label, (" -- " + detail) if detail else ""))
    if not ok:
        FAILURES.append(label)

# ── A game to dispatch to, plus two broken ones ──
os.makedirs(game_store.GAMES_DIR, exist_ok=True)
CALLS = os.path.join(TMP, "calls.txt")
with open(os.path.join(FLASH, "goalrace.py"), "w") as f:
    f.write('''
COMMANDS = {"stop", "goal"}
def play(nfc, panel, enow):
    with open(%r, "a") as f:
        f.write("goalrace(nfc=%%s, panel=%%s)\\n" %% (nfc is not None, panel is not None))
    panel.set_pixels([(0, 200, 0, 0)])
    enow.poll()
''' % CALLS)
with open(os.path.join(game_store.GAMES_DIR, "noplay.py"), "w") as f:
    f.write("COMMANDS = {'stop'}\n")
with open(os.path.join(game_store.GAMES_DIR, "broken.py"), "w") as f:
    f.write("def play(nfc, panel, enow)\n    pass\n")   # syntax error

import main
check("module imports", True)
check("hubtype read from the copied tree", main.HUB_TYPE == "icon_display", main.HUB_TYPE)
check("panel config is 16x16/256", main.HUB_CONFIG["num_leds"] == 256)
check("pulled games are discovered", set(game_store.slugs()) >= {"noplay", "broken"},
      str(sorted(game_store.slugs())))
check("built-in wins over pulled", main.game_module("goalrace") == "goalrace")
check("pulled game resolves", main.game_module("noplay") == "noplay")
check("unknown game is None", main.game_module("nope") is None)

# ── Build the panel the way main() does, then drive the helpers ──
import icon_matrix
panel = icon_matrix.Matrix(pin=main.HUB_CONFIG["led_pin"], intensity=main.IDLE_INTENSITY)
check("panel built", panel.np.n == 256)

main.fill(panel, main.RED)
check("fill writes the frame", panel.src[0] == 120 and panel.src[1] == 0)
main.show_idle(panel, 5)
check("show_idle draws", panel.np.writes > 1)
import shapes
main.flash_glyph(panel, shapes.SHAPE_X, main.AMBER, hold_ms=0)
check("flash_glyph restores idle intensity", abs(panel.intensity - main.IDLE_INTENSITY) < 1e-9,
      str(panel.intensity))
check("intensity never exceeds the measured ceiling",
      panel.intensity <= icon_matrix.MAX_INTENSITY)


class FakeEnow:
    """Just enough ESPNowManager for the loop: a scripted poll queue."""
    def __init__(self, script=()):
        self.script = list(script)
        self.sent = []
    def poll(self, timeout_ms=0):
        return self.script.pop(0) if self.script else (None, None, None)
    def broadcast(self, data):
        self.sent.append(data)


# ── A game that runs, then chains to another via start_game ──
enow = FakeEnow()
main._launch_game("goalrace", None, panel, enow)
ran = open(CALLS).read() if os.path.exists(CALLS) else ""
check("game ran with (nfc, panel, enow)", "goalrace(nfc=False, panel=True)" in ran, ran.strip())
check("module unloaded after the game", "goalrace" not in sys.modules)

# ── Loud failure paths ──
main._launch_game("noplay", None, panel, enow)
check("a module with no play() fails loudly and returns", "noplay" not in sys.modules)
main._launch_game("broken", None, panel, enow)
check("a module that will not compile fails loudly and returns", "broken" not in sys.modules)
check("panel still usable after a load failure", panel.np.writes > 0)

# ── A built-in whose file is not installed is simply not a game here ──
os.rename(os.path.join(FLASH, "goalrace.py"), os.path.join(FLASH, "goalrace.py.away"))
check("a built-in with no file on flash is not a game",
      main.game_module("goalrace") is None and not main.is_game("goalrace"))
check("...and the other built-ins are unaffected",
      main.game_module("noplay") == "noplay")
os.rename(os.path.join(FLASH, "goalrace.py.away"), os.path.join(FLASH, "goalrace.py"))
check("it comes back when the file does", main.is_game("goalrace") is True)

# ── Chained force-switch: goalrace hands straight to another game ──
with open(os.path.join(game_store.GAMES_DIR, "second.py"), "w") as f:
    f.write('''
COMMANDS = {"stop"}
def play(nfc, panel, enow):
    with open(%r, "a") as f:
        f.write("second\\n")
''' % CALLS)
open(CALLS, "w").close()

class ChainEnow(FakeEnow):
    def poll(self, timeout_ms=0):
        return ("start_game", {"name": "second"}, None)

main._launch_game("goalrace", None, panel, ChainEnow())
ran = open(CALLS).read()
check("force-switch chained without returning to idle",
      "goalrace" in ran and "second" in ran, ran.replace("\n", " | "))

shutil.rmtree(TMP, ignore_errors=True)
print()
if FAILURES:
    print("FAILED: %d" % len(FAILURES))
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("display boot smoke OK")
