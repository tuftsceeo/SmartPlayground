"""
Boot SplatCompanion/Companion/main.py under MicroPython stubs.

Modeled on boot_display.py, and closes its one open gap: this test also
calls the real main() with a pending pull flag, so a future regression
that moves BLE or ESP-NOW bring-up ahead of the pull check (the bug
flagged on IconDisplay's own main() in docs/KNOWN_ISSUES.md) would fail
here as soon as it's introduced.

py_compile only proves the file parses. This runs it: boot order (pull
before any radio import), the pull-mode outcomes, game dispatch
(game_module/is_game), a game load, a game with no play(), a game that
will not compile, the _start_play arity fallback, a force-switch chain,
the loud failure path, in-game cards (_GameEnow: stop, another game,
getcode, the launching card ignored), the boot-time I2C scan, and the
idle loop's 1 ms sleep on a failed pull-flag write.
"""
import os
import sys
import shutil
import tempfile
import types

_BB = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEV = _BB + "/SplatCompanion/Companion"
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
check("built-in jumpin resolves", main.game_module("jumpin") == "jumpin")

# jumpin: a press blinks green, and ESP-NOW stop ends it.
class _PressSplat(FakeSplat):
    """A two-Splat group: a press on unit 1, then nothing."""
    def __init__(self):
        super().__init__()
        self.colors = []            # (who, name): "all" or a unit index
        self._evs = ["press"]
        self.last_index = None
        self._units = [self._Unit(self, 0), self._Unit(self, 1)]

    class _Unit:
        def __init__(self, group, i):
            self.group, self.i = group, i

        def color(self, name):
            self.group.colors.append((self.i, name))
            return True

    def poll(self):
        if self._evs:
            self.last_index = 1
            return self._evs.pop(0)
        return None

    def unit(self, i):
        return self._units[i]

    def color(self, name):
        self.colors.append(("all", name))
        return True


_ps = _PressSplat()
main.game_module("jumpin")
import jumpin as _jumpin
_je = FakeEnow(script=[(None, None, None)] * 3
               + [("raw", {"type": "jumpin", "from": "wand"}, "AA")]
               + [(None, None, None)] * 3 + [("stop", {}, "AA")])
_jumpin.play(_ps, FakeLeds(), _je)
check("jumpin: a Splat press broadcasts which unit was pressed",
      _je.sent == [{"type": "jumpin", "from": "splat", "unit": 1}], str(_je.sent))
check("jumpin: only the pressed Splat blinks; a wand press blinks all; stop ends it",
      _ps.colors == [(1, "turngreen"), ("all", "turngreen")], str(_ps.colors))
sys.modules.pop("jumpin", None)
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
# ── In-game cards: _GameEnow turns a tapped card into enow stop/start_game ──
class FakeReader:
    """detect_tag() consumes one step per call: None (no card) or
    (uid, cmd); read_command() returns the cmd of the step last detected."""
    def __init__(self, steps=()):
        self.steps = list(steps)
        self.timeouts = []
        self.reads = 0
        self._cur = None

    def detect_tag(self, timeout=250):
        self.timeouts.append(timeout)
        self._cur = self.steps.pop(0) if self.steps else None
        return (self._cur[0], 0) if self._cur else (None, None)

    def read_command(self, timeout=250, **kw):
        self.reads += 1
        return self._cur[1], self._cur[0]


import splat_tags
splat_tags.EXIT_TAGS = splat_tags.EXIT_TAGS | {"gamea", "oldstyle"}
main.NFC_GAME_POLL_MS = 0          # check the reader on every empty poll

w = main._GameEnow(FakeEnow(), None, "gamea", None)
check("no reader: _GameEnow is a pass-through", w.poll() == (None, None, None))

rd = FakeReader([("U1", "gamea")])
w = main._GameEnow(FakeEnow(), rd, "gamea", "U1")
check("the launching card is ignored while it stays on the reader",
      w.poll() == (None, None, None) and rd.reads == 0, str(rd.reads))
check("in-game detect_tag uses the short timeout",
      rd.timeouts == [main.NFC_GAME_TIMEOUT_MS], str(rd.timeouts))

rd = FakeReader([None, ("U2", "stop")])
w = main._GameEnow(FakeEnow(), rd, "gamea", "U1")
w.poll()
check("the launching card leaving the field clears it", w.last_uid is None)
check("a stop card mid-game arrives as enow stop", w.poll()[0] == "stop")

rd = FakeReader([("U3", "oldstyle")])
w = main._GameEnow(FakeEnow(), rd, "gamea", None)
mt, data, _ = w.poll()
check("another game's card mid-game arrives as start_game naming it",
      mt == "start_game" and data == {"name": "oldstyle"}
      and w.pending_name == "oldstyle", "%r %r" % (mt, data))

rd = FakeReader([("U4", "gamea")])
w = main._GameEnow(FakeEnow(), rd, "gamea", None)
check("the running game's own card tapped again is ignored",
      w.poll() == (None, None, None) and w.pending_name is None)

rd = FakeReader([("U5", "nosuchgame")])
w = main._GameEnow(FakeEnow(), rd, "gamea", None)
check("an unknown card mid-game is ignored", w.poll() == (None, None, None))

rd = FakeReader([("U6", "stop")])
w = main._GameEnow(FakeEnow(script=[("start_game", {"name": "oldstyle"}, "AA")]),
                   rd, "gamea", None)
mt, data, _ = w.poll()
check("a real ESP-NOW message is passed through ahead of the reader",
      mt == "start_game" and w.pending_name == "oldstyle" and rd.timeouts == [])

_pending = []
main.pull_flag.set_pending = lambda slug, host=None: _pending.append((slug, host))
rd = FakeReader([("U7", "getcode:foo")])
w = main._GameEnow(FakeEnow(), rd, "gamea", None)
try:
    w.poll()
    check("a getcode card mid-game must reset", False)
except _Reset:
    check("a getcode card mid-game queues the pull and resets",
          len(_pending) == 1 and _pending[0][0] == "foo", str(_pending))


def _flag_write_fails(slug, host=None):
    raise OSError(28)


main.pull_flag.set_pending = _flag_write_fails
rd = FakeReader([("U8", "getcode:foo")])
w = main._GameEnow(FakeEnow(), rd, "gamea", None)
check("a getcode card whose flag write fails is printed and the game goes on",
      w.poll() == (None, None, None))

# A game run through _launch_game with a reader: a stop card ends it.
with open(os.path.join(FLASH, "loopgame.py"), "w") as f:
    f.write('''
def play(splat, leds, enow, batt=None):
    while True:
        mt, data, mac = enow.poll()
        if mt in ("stop", "start_game"):
            return
''')
main.GAME_MODULES = dict(main.GAME_MODULES, loopgame="loopgame")
splat_tags.EXIT_TAGS = splat_tags.EXIT_TAGS | {"loopgame"}
splat3 = FakeSplat()
rd = FakeReader([("U0", "loopgame"), None, ("U9", "stop")])
last = main._launch_game("loopgame", splat3, FakeEnow(), None, rd, "U0")
check("a stop card ends a game launched with a reader", "loopgame" not in sys.modules)
check("...splat.off() ran", splat3.off_calls == 1, str(splat3.off_calls))
check("...and the stop card's UID is handed back to the idle loop", last == "U9", repr(last))

if os.path.exists(CALLS):
    os.remove(CALLS)
splat4 = FakeSplat()
rd = FakeReader([("U5", "oldstyle")])
main._launch_game("loopgame", splat4, FakeEnow(), None, rd, None)
ran = open(CALLS).read() if os.path.exists(CALLS) else ""
check("another game's card mid-game chains into that game", "oldstyle(3-arg)" in ran, ran.strip())
main.NFC_GAME_POLL_MS = 150


# ── Boot-time I2C scan (finding: no swallowed errors) ──
import io
import contextlib


class _Bus:
    def __init__(self, found=None, fail=False):
        self.found = found or []
        self.fail = fail

    def scan(self):
        if self.fail:
            raise OSError(19)
        return self.found


def _captured(fn, *a):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        ret = fn(*a)
    return ret, buf.getvalue()


ret, out = _captured(main._check_i2c_for_reader, _Bus([0x36]), 0x24)
check("PN532 missing: the scan prints every address found",
      ret == [0x36] and "PN532 not at 0x24" in out and "0x36" in out, out.strip())
ret, out = _captured(main._check_i2c_for_reader, _Bus([0x24, 0x36]), 0x24)
check("PN532 present: the scan stays quiet", ret == [0x24, 0x36] and out == "", out.strip())
ret, out = _captured(main._check_i2c_for_reader, _Bus(fail=True), 0x24)
check("a scan OSError is printed, not swallowed",
      ret is None and "I2C scan failed" in out and "OSError" in out, out.strip())


# ── Idle loop: a failed pull-flag write still reaches the 1 ms sleep ──
class _LoopComp:
    def __init__(self, stop_after):
        self.n = 0
        self.stop_after = stop_after
        self.pending_start_game = None

    def step(self):
        self.n += 1
        if self.n > self.stop_after:
            raise KeyboardInterrupt


_sleeps = []
_saved_sleep = _time.sleep_ms
_time.sleep_ms = lambda ms: _sleeps.append(ms)
main.pull_flag.set_pending = _flag_write_fails
comp = _LoopComp(stop_after=main.NFC_POLL_EVERY * 2)
rd = FakeReader([("UG", "getcode:foo")] * 4)
try:
    main.run_event_loop(comp, FakeSplat(), rd, FakeEnow(), None)
except KeyboardInterrupt:
    pass
_time.sleep_ms = _saved_sleep
check("the getcode card was read in the idle loop", rd.reads >= 1, str(rd.reads))
check("every idle iteration slept 1 ms, including the failed flag write",
      _sleeps.count(1) >= comp.stop_after, "%d sleeps over %d iterations"
      % (_sleeps.count(1), comp.stop_after))


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
