"""
Wand game simulator runtime.

Installs MicroPython shims, transforms verbatim libs + game sources to async,
builds fake hardware objects, and runs play() as a cancellable asyncio task.
"""

from __future__ import annotations

import asyncio
import importlib
import io
import os
import sys
import types
import traceback

# Paths relative to this file
_PY_DIR = os.path.dirname(os.path.abspath(__file__))
_SIM_ROOT = os.path.dirname(_PY_DIR)
_SHIMS = os.path.join(_PY_DIR, "shims")
_DEVICES = os.path.join(_PY_DIR, "devices")
_VENDOR = os.path.join(_SIM_ROOT, "vendor")
_VENDOR_LIB = os.path.join(_VENDOR, "lib")
_VENDOR_GAMES = os.path.join(_VENDOR, "games")

# Libs that sleep internally — must be AST-transformed to async.
_TRANSFORM_LIBS = (
    "brightness",
    "leds",
    "buzzer",
    "actions",
    "battery",
)

# Libs with module-level calls / no sleeps — load verbatim (sync).
_RAW_LIBS = (
    "hubtype",
    "game_tags",
)

_SHIM_MODULES = (
    "sim_state",  # must be first — other shims import it at load time
    "machine",
    "neopixel",
    "_thread",
    "network",
    "espnow",
    "ubluetooth",
    "micropython",
)

_DEVICE_MODULES = (
    "lis2dw12",
    "max17048",
    "opt3002",
    "pn532",
    "nfc_reader",
    "espnow_manager",
)

# All named poses/gestures the motion controls can offer. Used verbatim as
# the "show everything" fallback when a game has no _TEACHER_TABLE entry
# (e.g. a freshly generated jumpin.py) — degrade to unfiltered rather than
# guess at what the code needs.
_ALL_MOTION = [
    "tip_up", "tip_down", "left_up", "right_up", "face_up", "face_down",
    "jump", "shake", "flip",
]

# Hand-written per-game copy: button *kind* and motion vocabulary aren't
# reliably inferable from source (a busy-wait-until-release reads the same
# as a tap; "hold" vs "tap" is a UX call, not a fact in the code), and a
# one-line "how to play" hint has to be written by a person regardless. A
# game name absent from this table gets the "show everything" default
# below rather than an empty panel — see get_capabilities().
_TEACHER_TABLE = {
    "jump": {
        "button": "tap",
        "motion": ["jump"],
        "hint": "Jump (freefall) to light one more LED. Press the button to reset.",
    },
    "shake": {
        "button": "tap",
        "motion": ["shake"],
        "hint": "Shake to fill the LEDs — your best shake sticks. Press the button to reset.",
    },
    "shake_rainbow": {
        "button": "tap",
        "motion": ["shake"],
        "hint": "Shake to advance the rainbow color — your best color sticks. Press the button to reset.",
    },
    "sound": {
        "button": "hold",
        "motion": [],
        "hint": "Hold the button to ring your bell note. Release to stop.",
    },
    "rainbow": {
        "button": "none",
        "motion": [],
        "hint": "Watch the battery bar, then the rainbow pattern play.",
    },
    "jumpin": {
        "button": "tap",
        "motion": [],
        "hint": "Press the button to blink all LEDs green.",
    },
    "nfc_sound": {
        "button": "hold",
        "motion": [],
        "hint": "Tap a note tag to pick your bell, then hold the button to play it.",
    },
    "gestures": {
        "button": "hold",
        "motion": ["jump", "shake", "flip", "tip_up", "tip_down", "left_up", "right_up", "face_up", "face_down"],
        "hint": "Hold the button while moving the wand to train a color (up to 8 times each). Tap PLAY, then hold + move to test.",
    },
    "simpleicecream": {
        "button": "tap",
        "motion": ["left_up", "right_up"],
        "hint": "While upright, press the button to count scoops. Roll the wand onto its other side to scoop!",
    },
    "melody": {
        "button": "tap",
        "motion": [],
        "hint": "Tap note tags to build a melody. Tap erase to clear. Press the button to play it back.",
    },
    "cooking": {
        "button": "hold",
        "motion": [],
        "hint": "Tap ingredient tags to collect them. Hold the button to preview the recipe.",
    },
    "multiicecream": {
        "button": "tap",
        "motion": ["left_up", "right_up"],
        "hint": "Press the button to count scoops (up to 3), then roll to the other side to commit each scoop.",
    },
}


class _PrintStream(io.TextIOBase):
    def __init__(self, emit):
        self._emit = emit
        self._buf = ""

    def write(self, s):
        if not s:
            return 0
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self._emit(line)
        return len(s)

    def flush(self):
        if self._buf:
            self._emit(self._buf)
            self._buf = ""


class Runtime:
    def __init__(self):
        self._bootstrapped = False
        self._sources = {}  # optional in-memory file map: relpath -> text
        self._game_mod = None
        self._game_name = None
        self._task = None
        self._hw = None
        self._old_stdout = None
        self._loop = None
        self.sim_state = None

    # ── Bootstrap ───────────────────────────────────────────────────

    def bootstrap(self, base_url=None, file_contents=None, workdir=None):
        """Install shims, patch time, load transformed libs.

        file_contents: optional dict of relative path -> source text
            (keys like 'vendor/lib/leds.py', 'vendor/hubtype.txt',
             'py/shims/machine.py', ...). When provided, sources are
            loaded from the dict instead of the filesystem.
        workdir: directory containing hubtype.txt (default: vendor/).
        base_url: unused in CPython; reserved for the JS host.
        """
        if file_contents:
            self._sources = dict(file_contents)

        self._ensure_paths()
        self._install_shims()
        self._install_devices()
        self._patch_time()

        import sim_state
        self.sim_state = sim_state
        sim_state.reset_io()

        # hubtype.txt must be openable as a relative path.
        wd = workdir or _VENDOR
        if not os.path.isdir(wd):
            os.makedirs(wd, exist_ok=True)
        hub_text = self._read_text("vendor/hubtype.txt", os.path.join(_VENDOR, "hubtype.txt"))
        if hub_text is not None:
            hub_path = os.path.join(wd, "hubtype.txt")
            with open(hub_path, "w") as f:
                f.write(hub_text if hub_text.endswith("\n") else hub_text + "\n")
        self._workdir = wd
        self._prev_cwd = os.getcwd()
        try:
            os.chdir(wd)
        except OSError:
            pass

        # Load libs. hubtype/game_tags stay sync (module-level calls).
        for name in _RAW_LIBS:
            self._load_raw_lib(name)
        for name in _TRANSFORM_LIBS:
            self._load_transformed_lib(name)

        self._bootstrapped = True
        return self

    def _ensure_paths(self):
        for p in (_SHIMS, _DEVICES, _VENDOR_LIB, _PY_DIR):
            if p not in sys.path:
                sys.path.insert(0, p)

    def _install_shims(self):
        for name in _SHIM_MODULES:
            if name in sys.modules and getattr(sys.modules[name], "__sim_shim__", False):
                continue
            mod = self._load_raw_module(name, os.path.join(_SHIMS, name + ".py"),
                                        "py/shims/%s.py" % name)
            mod.__sim_shim__ = True
            sys.modules[name] = mod

    def _install_devices(self):
        for name in _DEVICE_MODULES:
            mod = self._load_raw_module(name, os.path.join(_DEVICES, name + ".py"),
                                        "py/devices/%s.py" % name)
            sys.modules[name] = mod

    def _patch_time(self):
        from time_patch import patch_time_module
        patch_time_module()

    def _read_text(self, rel_key, fs_path):
        if rel_key in self._sources:
            return self._sources[rel_key]
        # Also try basename-only and games/lib shortcuts.
        for alt in (rel_key, os.path.basename(rel_key),
                    rel_key.replace("vendor/", ""),
                    "games/" + os.path.basename(rel_key) if "games" in rel_key else None):
            if alt and alt in self._sources:
                return self._sources[alt]
        if fs_path and os.path.isfile(fs_path):
            with open(fs_path, "r", encoding="utf-8") as f:
                return f.read()
        return None

    def _load_raw_module(self, name, fs_path, rel_key):
        src = self._read_text(rel_key, fs_path)
        if src is None:
            raise FileNotFoundError("missing module source: %s (%s)" % (name, rel_key))
        mod = types.ModuleType(name)
        mod.__file__ = fs_path or rel_key
        mod.__sim_shim__ = True
        code = compile(src, mod.__file__, "exec")
        exec(code, mod.__dict__)
        return mod

    def _load_raw_lib(self, name):
        fs_path = os.path.join(_VENDOR_LIB, name + ".py")
        rel_key = "vendor/lib/%s.py" % name
        src = self._read_text(rel_key, fs_path)
        if src is None:
            return None
        if name in sys.modules:
            del sys.modules[name]
        mod = types.ModuleType(name)
        mod.__file__ = fs_path
        sys.modules[name] = mod
        exec(compile(src, fs_path, "exec"), mod.__dict__)
        return mod

    def _load_transformed_lib(self, name):
        from transform import transform_and_compile, runtime_namespace

        fs_path = os.path.join(_VENDOR_LIB, name + ".py")
        rel_key = "vendor/lib/%s.py" % name
        src = self._read_text(rel_key, fs_path)
        if src is None:
            return None

        if name in sys.modules:
            del sys.modules[name]

        try:
            code = transform_and_compile(src, filename=name + ".py")
        except Exception as e:
            # Optional libs shouldn't abort bootstrap.
            import sim_state
            sim_state.emit_log("skip lib %s: %s" % (name, e))
            return None
        mod = types.ModuleType(name)
        mod.__file__ = fs_path
        ns = runtime_namespace()
        mod.__dict__.update(ns)
        sys.modules[name] = mod
        try:
            exec(code, mod.__dict__)
        except Exception as e:
            del sys.modules[name]
            import sim_state
            sim_state.emit_log("exec lib %s failed: %s" % (name, e))
            return None
        return mod

    # ── Game loading ────────────────────────────────────────────────

    def load_game(self, name_or_source):
        """Load a game by module name (jump, shake, ...) or raw source string."""
        if not self._bootstrapped:
            raise RuntimeError("call bootstrap() first")

        from transform import transform_and_compile, runtime_namespace, reset_watchdog
        reset_watchdog()

        if "\n" in name_or_source or name_or_source.strip().startswith(("import ", '"""', "from ")):
            name = "custom"
            src = name_or_source
        else:
            name = name_or_source.replace(".py", "")
            fs_path = os.path.join(_VENDOR_GAMES, name + ".py")
            rel_key = "vendor/games/%s.py" % name
            src = self._read_text(rel_key, fs_path)
            if src is None:
                raise FileNotFoundError("game not found: %s" % name)

        if name in sys.modules:
            del sys.modules[name]

        code = transform_and_compile(src, filename=name + ".py")
        mod = types.ModuleType(name)
        mod.__file__ = name + ".py"
        ns = runtime_namespace()
        mod.__dict__.update(ns)
        sys.modules[name] = mod
        exec(code, mod.__dict__)
        self._game_mod = mod
        self._game_name = name
        return mod

    def get_commands(self):
        if not self._game_mod:
            return []
        cmds = getattr(self._game_mod, "COMMANDS", None)
        if cmds is None:
            return []
        return sorted(cmds)

    def get_capabilities(self):
        """Return what the loaded game actually uses, for filtering controls.

        nfcTags and battery are derived live from the loaded module; button
        and motion come from _TEACHER_TABLE (see its docstring for why), and
        default to "show everything" when the game isn't in that table —
        the important path, since a freshly generated jumpin.py never will
        be.
        """
        if not self._game_mod:
            return {"button": "tap", "motion": list(_ALL_MOTION), "nfcTags": [], "battery": False,
                    "buzzer": True, "hint": ""}

        mod = self._game_mod
        import game_tags

        commands = set(getattr(mod, "COMMANDS", None) or [])
        own_exit_tags = getattr(mod, "_EXIT_TAGS", None)
        # exit_tags_excluding(own_tag) drops exactly one tag from EXIT_TAGS;
        # recover it by diffing rather than re-parsing the game's call site.
        own_tag = (game_tags.EXIT_TAGS - own_exit_tags) if own_exit_tags is not None else set()
        game_specific = (commands - game_tags.EXIT_TAGS) | (own_tag & commands)
        nfc_tags = sorted(game_specific)

        battery = False
        play = getattr(mod, "play", None)
        if play is not None:
            try:
                import inspect
                battery = "batt" in inspect.signature(play).parameters
            except (TypeError, ValueError):
                battery = False

        table = _TEACHER_TABLE.get(self._game_name, {})
        return {
            "button": table.get("button", "tap"),
            "motion": list(table.get("motion", _ALL_MOTION)),
            "nfcTags": nfc_tags,
            "battery": battery,
            "buzzer": True,  # every wand game plays sound; not derived
            "hint": table.get("hint", ""),
        }

    # ── Hardware + run ──────────────────────────────────────────────

    async def _build_hw(self):
        import machine
        from machine import Pin
        from pn532 import PN532
        from lis2dw12 import LIS2DW12, RANGE_4G
        from max17048 import MAX17048
        from opt3002 import OPT3002
        from espnow_manager import ESPNowManager
        from leds import Leds
        from buzzer import Buzzer
        import brightness

        # Ambient light so calibrate (if called) is reasonable; for games that
        # skip calibrate, force a readable MULTIPLIER for the LED grid.
        self.sim_state.set_ambient_lux(max(self.sim_state.ambient_lux, 8000.0))
        brightness.MULTIPLIER = max(getattr(brightness, "MULTIPLIER", 0.05), 0.35)

        i2c = machine.SoftI2C(sda=Pin(22), scl=Pin(23), freq=100_000)
        nfc = PN532(i2c, 0x24)
        try:
            nfc.begin()
        except Exception:
            pass

        accel = LIS2DW12(i2c)
        accel.init(fs_range=RANGE_4G)

        batt = MAX17048(i2c)
        light = OPT3002(i2c)
        light.init()
        try:
            cal = brightness.calibrate(light)
            if asyncio.iscoroutine(cal) or asyncio.isfuture(cal):
                await cal
        except Exception:
            pass

        leds = await self._maybe_await(Leds())
        buz = await self._maybe_await(Buzzer(19))
        enow = ESPNowManager()
        enow.init()

        return {
            "nfc": nfc,
            "leds": leds,
            "buz": buz,
            "accel": accel,
            "i2c": i2c,
            "enow": enow,
            "batt": batt,
        }

    @staticmethod
    async def _maybe_await(value):
        if asyncio.iscoroutine(value) or asyncio.isfuture(value):
            return await value
        return value

    def _redirect_stdout(self):
        self._old_stdout = sys.stdout
        sys.stdout = _PrintStream(self.sim_state.emit_print)

    def _restore_stdout(self):
        if self._old_stdout is not None:
            try:
                sys.stdout.flush()
            except Exception:
                pass
            sys.stdout = self._old_stdout
            self._old_stdout = None

    async def _run_play(self):
        from transform import reset_watchdog
        reset_watchdog()
        hw = await self._build_hw()
        self._hw = hw
        play = getattr(self._game_mod, "play", None)
        if play is None:
            raise RuntimeError("game module has no play()")
        args = (hw["nfc"], hw["leds"], hw["buz"], hw["accel"], hw["i2c"], hw["enow"])
        try:
            result = play(*args, batt=hw["batt"])
        except TypeError:
            result = play(*args)
        if asyncio.iscoroutine(result) or asyncio.isfuture(result):
            await result

    async def start(self):
        """Start the loaded game as a cancellable task. Returns the task."""
        if not self._game_mod:
            raise RuntimeError("call load_game() first")
        if self._task and not self._task.done():
            await self.stop()

        self._redirect_stdout()

        async def _runner():
            try:
                await self._run_play()
            except asyncio.CancelledError:
                raise
            except Exception:
                tb = traceback.format_exc()
                self.sim_state.emit_print(tb)
                self.sim_state.emit_log("sim-error: " + tb.splitlines()[-1])
                raise
            finally:
                self._restore_stdout()

        self._task = asyncio.create_task(_runner())
        self._task.add_done_callback(self._reap_task)
        return self._task

    @staticmethod
    def _reap_task(task):
        """Retrieve the task's exception so asyncio never logs "Task exception
        was never retrieved" (which Pyodide can surface as an unhandled JS
        promise rejection) for callers that don't hold onto / await the task
        themselves — e.g. the JS host, which only calls stop() later.
        `_runner()` already logs real failures; a cancellation is expected
        during a normal stop()/game-switch and needs no further handling.
        """
        if task.cancelled():
            return
        task.exception()

    async def stop(self):
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        self._task = None
        self._restore_stdout()

    def is_running(self):
        return self._task is not None and not self._task.done()


# Module-level singleton helpers for the JS host / tests.
_runtime = None


def get_runtime():
    global _runtime
    if _runtime is None:
        _runtime = Runtime()
    return _runtime


def bootstrap(**kwargs):
    return get_runtime().bootstrap(**kwargs)


def load_game(name_or_source):
    return get_runtime().load_game(name_or_source)


async def start():
    # Deliberately don't return the asyncio Task: Pyodide auto-links a
    # returned Task/Future to a JS promise, and since the JS host doesn't
    # hold onto or await it directly (it only calls stop() later), a normal
    # cancellation on game-switch would otherwise surface as an unhandled
    # promise rejection in the browser console. CPython callers that need
    # the Task (e.g. tests) should use Runtime.start() directly instead.
    await get_runtime().start()


async def stop():
    return await get_runtime().stop()


def get_commands():
    return get_runtime().get_commands()


def get_capabilities():
    return get_runtime().get_capabilities()
