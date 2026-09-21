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
import shapes


def _px(pnl, x, y):
    o = (y * 16 + x) * 3
    return (pnl.src[o], pnl.src[o + 1], pnl.src[o + 2])


# The waiting display is the wand's: a static green square, not an animation.
panel.src[0] = 99
main.show_idle(panel, 0)
check("the idle display is a green square in the middle",
      _px(panel, 8, 8) == main.IDLE_GREEN, str(_px(panel, 8, 8)))
check("...with the edges dark", _px(panel, 0, 0) == (0, 0, 0), str(_px(panel, 0, 0)))

_writes = panel.np.writes
main.show_idle(panel, 1)
check("...repainted on a cadence, not every frame, since it never changes",
      panel.np.writes == _writes)
main.show_idle(panel, main.IDLE_REPAINT_FRAMES)
check("...and it does come back", panel.np.writes == _writes + 1)

# ── Boot screen: the wand's stage column, same colour language ──
_boot = shapes.BootScreen(panel)
_boot.stage_start(0)
check("a started stage is dim white", _px(panel, 1, 1) == shapes.WHITE_DIM,
      str(_px(panel, 1, 1)))
_boot.stage_ok(0, [None, None, None, shapes.STAGE_OK])
check("a finished stage turns green", _px(panel, 1, 1) == shapes.STAGE_OK)
check("...and its data cell lights beside it", _px(panel, 13, 1) == shapes.STAGE_OK,
      str(_px(panel, 13, 1)))
_boot.stage_warn(4)
check("a warned stage is amber", _px(panel, 1, 13) == shapes.STAGE_WARN,
      str(_px(panel, 1, 13)))
check("...and earlier stages stay lit, so the column reads as a record",
      _px(panel, 1, 1) == shapes.STAGE_OK)
_boot.clear()
check("clearing the boot screen blanks the panel",
      all(v == 0 for v in panel.src))
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
_load_fail_draws = []
_orig_draw_shape_early = shapes.draw_shape
shapes.draw_shape = lambda p, shape, rgb: (
    _load_fail_draws.append((shape, rgb)), _orig_draw_shape_early(p, shape, rgb))[-1]

main._launch_game("noplay", None, panel, enow)
check("a module with no play() fails loudly and returns", "noplay" not in sys.modules)
main._launch_game("broken", None, panel, enow)
check("a module that will not compile fails loudly and returns", "broken" not in sys.modules)
check("panel still usable after a load failure", panel.np.writes > 0)
check("both load failures light SHAPE_X in red",
      _load_fail_draws == [(shapes.SHAPE_X, main.RED)] * 2, str(_load_fail_draws))

shapes.draw_shape = _orig_draw_shape_early

# ── A game named in GAME_MODULES is only playable if its file exists ──
# The tree ships goalrace in games/, which is also where a pull writes, so
# both copies have to be out of the way for "not installed" to be true.
_root_game = os.path.join(FLASH, "goalrace.py")
_pulled_game = os.path.join(game_store.GAMES_DIR, "goalrace.py")
os.rename(_root_game, _root_game + ".away")
_had_pulled = os.path.exists(_pulled_game)
if _had_pulled:
    os.rename(_pulled_game, _pulled_game + ".away")

check("a built-in with no file anywhere is not a game",
      main.game_module("goalrace") is None and not main.is_game("goalrace"))
check("...and the other built-ins are unaffected",
      main.game_module("noplay") == "noplay")

# A name in GAME_MODULES must not hide a copy in games/. That is where the
# tree now ships the display's own games AND where a pull writes, so the
# hardware symptom was "no game 'goalrace' on this display" immediately
# after a pull that had just written the file.
with open(_pulled_game, "w") as f:
    f.write("COMMANDS = {'stop'}\n\n\ndef play(nfc, panel, enow):\n    pass\n")
check("a copy in games/ is playable even with nothing in the flash root",
      main.is_game("goalrace") is True and main.game_module("goalrace") == "goalrace")
os.remove(_pulled_game)
if _had_pulled:
    os.rename(_pulled_game + ".away", _pulled_game)

os.rename(_root_game + ".away", _root_game)
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

# ── Pull mode: each outcome lights the glyph the phase 6 plan calls for ──
import machine
import pull_flag
import icon_store
import types


class _Reset(Exception):
    """Stands in for machine.reset(): the pull-mode branches that end in a
    reset never return, so the test needs a way to stop execution there
    without actually rebooting the process."""


machine.reset = lambda: (_ for _ in ()).throw(_Reset())


# noap/nojoin/norequest/budget-spent all go through flash_glyph(), which
# draws, holds, then clears and restores idle intensity before returning --
# so the glyph is gone by the time _run_pull_mode() itself returns. Spying
# on shapes.draw_shape() (which flash_glyph and the success/retry branches
# both call) records what was actually asked for, transient or not.
_draw_calls = []
_orig_draw_shape = shapes.draw_shape
def _spy_draw_shape(panel, shape, rgb):
    _draw_calls.append((shape, rgb))
    return _orig_draw_shape(panel, shape, rgb)
shapes.draw_shape = _spy_draw_shape


def _run_pull_mode_with(outcome, on_status_calls=None, on_progress_calls=None):
    """Drive one _run_pull_mode() call against a fake code_puller.pull()
    that returns `outcome` and, if given, exercises the status/progress
    callbacks main.py wires up. Clears _draw_calls first so each call's
    result reflects only this run."""
    del _draw_calls[:]
    pull_flag.is_pending = lambda: True
    pull_flag.budget_left = lambda: True
    pull_flag.bump = lambda: 1
    pull_flag.requested_slug = lambda: "goalrace"
    pull_flag.clear = lambda: None
    p = icon_matrix.Matrix(pin=0, intensity=main.IDLE_INTENSITY)

    fake_puller = types.ModuleType("code_puller")
    fake_puller.SSID = "SP-FILEPUSH"

    def fake_pull(**kw):
        if on_status_calls is not None and kw.get("on_status"):
            for phase, tick in on_status_calls:
                kw["on_status"](phase, tick)
        if on_progress_calls is not None and kw.get("on_progress"):
            for received, total in on_progress_calls:
                kw["on_progress"](received, total)
        return outcome
    fake_puller.pull = fake_pull
    sys.modules["code_puller"] = fake_puller

    try:
        main._run_pull_mode(p, icon_store.DIR)
    except _Reset:
        pass
    return p


_run_pull_mode_with("noap")
check("AP not up lights SHAPE_WIFI_2 in red",
      _draw_calls == [(shapes.SHAPE_WIFI_2, main.RED)], str(_draw_calls))

_run_pull_mode_with("nojoin")
check("join refused lights SHAPE_WIFI_2 in amber",
      _draw_calls == [(shapes.SHAPE_WIFI_2, main.AMBER)], str(_draw_calls))

_run_pull_mode_with("norequest")
check("no such game for this role also lights SHAPE_WIFI_2 in amber",
      _draw_calls == [(shapes.SHAPE_WIFI_2, main.AMBER)], str(_draw_calls))

_run_pull_mode_with(True)
check("success lights SHAPE_CHECK in green before resetting",
      _draw_calls == [(shapes.SHAPE_CHECK, main.GREEN)], str(_draw_calls))

_run_pull_mode_with(False)
check("a broken transfer lights SHAPE_X in red before retrying",
      _draw_calls == [(shapes.SHAPE_X, main.RED)], str(_draw_calls))

# budget-spent path never calls code_puller.pull() at all
del _draw_calls[:]
panel = icon_matrix.Matrix(pin=0, intensity=main.IDLE_INTENSITY)
pull_flag.budget_left = lambda: False
pull_flag.clear = lambda: None
main._run_pull_mode(panel, icon_store.DIR)
check("attempt budget spent lights SHAPE_X in red",
      _draw_calls == [(shapes.SHAPE_X, main.RED)], str(_draw_calls))

# on_status/on_progress are actually wired up, not just accepted: a callback
# that silently drew nothing would pass a bare "it did not raise" check.
_run_pull_mode_with(
    "noap",
    on_status_calls=[("scan", 0), ("scan", 8)],
    on_progress_calls=[(100, 400)],
)
_status_draws = _draw_calls[:2]
check("on_status draws the wifi bars in blue",
      len(_status_draws) == 2
      and all(s in shapes.WIFI_FRAMES and c == main.BLUE for s, c in _status_draws),
      str(_status_draws))
check("...and a later tick is a different bar, so the bars actually cycle",
      _status_draws[0][0] != _status_draws[1][0])

# The progress bar fills by whole rows -- sixteenths of the panel -- and
# repaints only when the row changes. The callback fires once per 512-byte
# chunk, so a per-pixel bar would put a full 256-pixel frame write inside
# the transfer loop for a bar that mostly does not move.
_pp = icon_matrix.Matrix(pin=0, intensity=main.IDLE_INTENSITY)
main._progress_row = -1
_per_row = 256 // main.PROGRESS_ROWS


def _px(panel, i):
    o = i * 3
    return (panel.src[o], panel.src[o + 1], panel.src[o + 2])


main._pull_progress(_pp, 100, 400)          # 25% -> 4 of 16 rows
_writes_at_4 = _pp.np.writes
check("a quarter of the file lights a quarter of the rows",
      _px(_pp, 4 * _per_row - 1) == main.CYAN and _px(_pp, 4 * _per_row) == main.BLUE_DIM,
      "%s then %s" % (_px(_pp, 4 * _per_row - 1), _px(_pp, 4 * _per_row)))

main._pull_progress(_pp, 101, 400)          # still inside the same sixteenth
check("another chunk in the same sixteenth costs no frame write",
      _pp.np.writes == _writes_at_4, "%d writes" % _pp.np.writes)

main._pull_progress(_pp, 400, 400)          # done
check("a finished file fills the whole panel",
      _px(_pp, 0) == main.CYAN and _px(_pp, 255) == main.CYAN)
check("...and that took one more frame write", _pp.np.writes == _writes_at_4 + 1)

shapes.draw_shape = _orig_draw_shape

shutil.rmtree(TMP, ignore_errors=True)
print()
if FAILURES:
    print("FAILED: %d" % len(FAILURES))
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("display boot smoke OK")
