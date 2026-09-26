"""
Boot SplatCompanion/main.py under MicroPython stubs.

Modeled on boot_display.py, and closes its one open gap: this test also
calls the real main() with a pending pull flag, so a future regression
that moves BLE or ESP-NOW bring-up ahead of the pull check (the bug
flagged on IconDisplay's own main() in docs/KNOWN_ISSUES.md) would fail
here as soon as it's introduced.

py_compile only proves the file parses. This runs it: boot order (pull
before any radio import), the pull-mode outcomes, game dispatch
(game_module/is_game), a game load, a game with no play(), a game that
will not compile, the _start_play arity fallback, a force-switch chain,
and the loud failure path.
"""
import os
import sys
import shutil
import tempfile
import types

_BB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEV = _BB + "/SplatCompanion"
SCRATCH = os.path.dirname(os.path.abspath(__file__))

import time as _time
_time.sleep_ms = lambda ms: None
_ticks = [0]


def _tick():
    _ticks[0] += 10
    return _ticks[0]


_time.ticks_ms = _tick
_time.ticks_diff = lambda a, b: a - b
_time.ticks_add = lambda a, b: a + b

TMP = tempfile.mkdtemp(prefix="splat-")
FLASH = os.path.join(TMP, "flash")
shutil.copytree(DEV, FLASH)
os.chdir(FLASH)

sys.path.insert(0, os.path.join(SCRATCH, "stubs"))
sys.path.insert(0, os.path.join(FLASH, "lib"))
sys.path.insert(0, FLASH)

import traceback
sys.print_exception = lambda e, *a: traceback.print_exception(type(e), e, e.__traceback__)

import gc as _gc
_gc.mem_alloc = lambda: 0
_gc.mem_free = lambda: 100_000
_gc.threshold = lambda *a: 0

import machine  # the shared stub


class _Reset(Exception):
    """Stands in for machine.reset(): every path that calls it must not
    return control to its caller, same convention as boot_display.py."""


machine.reset = lambda: (_ for _ in ()).throw(_Reset())

import game_store
game_store.GAMES_DIR = os.path.join(FLASH, "games")

FAILURES = []


def check(label, ok, detail=""):
    print("%-4s %s%s" % ("ok" if ok else "FAIL", label, (" -- " + detail) if detail else ""))
    if not ok:
        FAILURES.append(label)


class FakeSplat:
    """Just enough of splat_api.SplatAPI for a game to call."""
    def __init__(self):
        self.off_calls = 0
        self.colors = []

    def poll(self):
        return None

    def color(self, name):
        self.colors.append(name)
        return True

    def sound(self, name):
        return True

    def note(self, name):
        return True

    def play(self, names):
        return True

    def off(self):
        self.off_calls += 1
        return True


class FakeLeds:
    def fill(self, color):
        pass

    def off(self):
        pass


class FakeEnow:
    """Just enough of the EUM ESPNowManager for a game's own poll loop."""
    def __init__(self, script=()):
        self.script = list(script)
        self.sent = []

    def poll(self, timeout_ms=0):
        return self.script.pop(0) if self.script else (None, None, None)

    def broadcast(self, data):
        self.sent.append(data)
        return True


# ── A game that runs, plus two broken ones and an older 3-arg one ──
os.makedirs(game_store.GAMES_DIR, exist_ok=True)
CALLS = os.path.join(TMP, "calls.txt")
with open(os.path.join(FLASH, "gamea.py"), "w") as f:
    f.write('''
def play(splat, leds, enow, batt=None):
    with open(%r, "a") as f:
        f.write("gamea(splat=%%s, batt=%%s)\\n" %% (splat is not None, batt))
    splat.color("turnred")
    while True:
        mt, data, mac = enow.poll()
        if mt == "start_game":
            return
''' % CALLS)
with open(os.path.join(game_store.GAMES_DIR, "noplay.py"), "w") as f:
    f.write("GAME_TAGS_LOCAL = None\\n")
with open(os.path.join(game_store.GAMES_DIR, "broken.py"), "w") as f:
    f.write("def play(splat, leds, enow)\\n    pass\\n")   # syntax error
with open(os.path.join(game_store.GAMES_DIR, "oldstyle.py"), "w") as f:
    f.write('''
def play(splat, leds, enow):
    with open(%r, "a") as f:
        f.write("oldstyle(3-arg)\\n")
''' % CALLS)

import main
check("module imports", True)
check("hubtype read from the copied tree", main.HUB_TYPE == "splat_companion", main.HUB_TYPE)
check("GAME_MODULES matches GAME_TAGS at import (no [ERR])",
      set(main.GAME_MODULES.keys()) == main.GAME_TAGS)
check("built-in splatwhack resolves", main.game_module("splatwhack") == "splatwhack")
check("pulled games are discovered",
      set(game_store.slugs()) >= {"noplay", "broken", "oldstyle"},
      str(sorted(game_store.slugs())))
check("pulled game resolves", main.game_module("noplay") == "noplay")
check("unknown game is None", main.game_module("nope") is None)


# ── Dispatch-check mechanism itself: exec just that slice with a
# deliberately mismatched GAME_TAGS, proving the check would actually fire
# (the real tree's tables agree, so it never prints under normal import).
def _dispatch_check_prints(modules, tags):
    import io
    import contextlib
    src = "if set(GAME_MODULES.keys()) != GAME_TAGS:\n    print('[ERR] mismatch')\n"
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        exec(compile(src, "<dispatch-check>", "exec"),
             {"GAME_MODULES": modules, "GAME_TAGS": tags})
    return "[ERR]" in out.getvalue()


check("dispatch check fires on a real mismatch",
      _dispatch_check_prints({"a": "a"}, {"a", "b"}))
check("...and stays quiet when they agree",
      not _dispatch_check_prints({"a": "a"}, {"a"}))

# ── A game that runs, then chains to another via start_game ──
main.GAME_MODULES = dict(main.GAME_MODULES, gamea="gamea", oldstyle="oldstyle")
splat = FakeSplat()
enow = FakeEnow(script=[("start_game", {"name": "oldstyle"}, "AA:BB:CC:DD:EE:FF")])
main._launch_game("gamea", splat, enow, None)
ran = open(CALLS).read() if os.path.exists(CALLS) else ""
check("game ran with (splat, batt)", "gamea(splat=True, batt=None)" in ran, ran.strip())
check("force-switch chained to oldstyle", "oldstyle(3-arg)" in ran, ran.strip())
check("module unloaded after the chain", "gamea" not in sys.modules and "oldstyle" not in sys.modules)
check("splat.off() ran on every exit from the chain", splat.off_calls >= 1, str(splat.off_calls))

# ── Loud failure paths ──
splat2 = FakeSplat()
main._launch_game("noplay", splat2, FakeEnow(), None)
check("a module with no play() fails loudly and returns", "noplay" not in sys.modules)
main._launch_game("broken", splat2, FakeEnow(), None)
check("a module that will not compile fails loudly and returns", "broken" not in sys.modules)
check("splat.off() still ran after both load failures", splat2.off_calls == 2, str(splat2.off_calls))

# ── A name in GAME_MODULES is only playable if its file exists ──
os.remove(os.path.join(FLASH, "gamea.py"))
check("a built-in with no file anywhere is not a game",
      main.game_module("gamea") is None and not main.is_game("gamea"))
check("...and the other built-ins are unaffected",
      main.game_module("oldstyle") == "oldstyle")


# ── Boot order: a pending pull must run and reset before BLE/ESP-NOW ──
def _make_fake_puller(outcome):
    fake = types.ModuleType("code_puller")
    fake.SSID = "SP-FILEPUSH"
    fake.DEBUG_PULL = False

    def fake_pull(**kw):
        return outcome
    fake.pull = fake_pull
    return fake


import pull_flag
main.pull_flag.is_pending = lambda: True
main.pull_flag.budget_left = lambda: True
main.pull_flag.bump = lambda: 1
main.pull_flag.requested_slug = lambda: ""
main.pull_flag.requested_host = lambda: ""
main.pull_flag.clear = lambda: None
main.pull_flag.MAX_ATTEMPTS = 1

sys.modules["code_puller"] = _make_fake_puller(True)   # success -> reset
for mod in ("ubluetooth", "espnow_manager"):
    sys.modules.pop(mod, None)
try:
    main.main()
    check("main() must not return past a successful pull", False)
except _Reset:
    check("a pending pull runs and resets before main() continues", True)
check("BLE was never imported on the pull boot",
      "ubluetooth" not in sys.modules)
check("ESP-NOW (the EUM manager) was never imported on the pull boot",
      "espnow_manager" not in sys.modules)


# ── Pull-mode outcomes light the right color ──
_fill_calls = []
_orig_fill = main.status.fill


def _spy_fill(color):
    _fill_calls.append(color)
    return _orig_fill(color)


main.status.fill = _spy_fill


def _run_pull_mode_with(outcome):
    del _fill_calls[:]
    sys.modules["code_puller"] = _make_fake_puller(outcome)
    try:
        main._run_pull_mode()
    except _Reset:
        pass


_run_pull_mode_with("noap")
check("AP not up ends on the fail color", _fill_calls and _fill_calls[-1] == main.PULL_FAIL_COLOR,
      str(_fill_calls))

_run_pull_mode_with("nojoin")
check("join refused ends on the reject color",
      _fill_calls and _fill_calls[-1] == main.PULL_REJECT_COLOR, str(_fill_calls))

_run_pull_mode_with("norequest")
check("no such game ends on the reject color",
      _fill_calls and _fill_calls[-1] == main.PULL_REJECT_COLOR, str(_fill_calls))

_run_pull_mode_with(True)
check("success ends on the ok color before resetting",
      _fill_calls and _fill_calls[-1] == main.PULL_OK_COLOR, str(_fill_calls))

_run_pull_mode_with(False)
check("a broken transfer ends on the fail color before retrying",
      _fill_calls and _fill_calls[-1] == main.PULL_FAIL_COLOR, str(_fill_calls))

del _fill_calls[:]
main.pull_flag.budget_left = lambda: False
try:
    main._run_pull_mode()
except _Reset:
    pass
check("attempt budget spent never touches code_puller and ends on the fail color",
      _fill_calls == [main.PULL_FAIL_COLOR], str(_fill_calls))

main.status.fill = _orig_fill

shutil.rmtree(TMP, ignore_errors=True)
print()
if FAILURES:
    print("FAILED: %d" % len(FAILURES))
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("splat companion boot smoke OK")
