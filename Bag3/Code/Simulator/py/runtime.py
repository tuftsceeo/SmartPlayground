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
    "espnow_manager",
    # Lobby games (in import order: each imports the ones before it).
    "pwire",
    "splatpair",
    "lobby_game",
)

# Transformed libs a game cannot run without: a failure raises instead of
# being logged and skipped.
_REQUIRED_LIBS = ("espnow_manager",)

# Non-game modules shipped beside the games that a game imports by name
# (color_quest.py: `from target import SCORE_MAC`). Constants only, so
# loaded verbatim.
_GAME_HELPERS = ("target",)

# Libs with module-level calls / no sleeps — load verbatim (sync).
_RAW_LIBS = (
    "hubtype",
    "game_tags",
    # Lobby games. No sleeps; splat_api drives py/shims/splat_hub.py's links.
    "pairing",
    "splat_api",
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
    "splat_hub",
)

_DEVICE_MODULES = (
    "lis2dw12",
    "max17048",
    "opt3002",
    "pn532",
    "nfc_reader",
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
# as a tap; "hold" vs "tap" is a UX call, not a fact in the code). A game
# name absent from this table gets the "show everything" default below
# rather than an empty panel — see get_capabilities().
_TEACHER_TABLE = {
    "jump": {
        "button": "tap",
        "motion": ["jump"],
    },
    "shake": {
        "button": "tap",
        "motion": ["shake"],
    },
    "shake_rainbow": {
        "button": "tap",
        "motion": ["shake"],
    },
    "sound": {
        "button": "hold",
        "motion": [],
    },
    "rainbow": {
        "button": "none",
        "motion": [],
    },
    "jumpin": {
        "button": "tap",
        "motion": [],
    },
    "nfc_sound": {
        "button": "hold",
        "motion": [],
    },
    "gestures": {
        "button": "hold",
        "motion": ["jump", "shake", "flip", "tip_up", "tip_down", "left_up", "right_up", "face_up", "face_down"],
    },
    "simpleicecream": {
        "button": "tap",
        "motion": ["left_up", "right_up"],
    },
    "melody": {
        "button": "tap",
        "motion": [],
    },
    "cooking": {
        "button": "hold",
        "motion": [],
    },
    "multiicecream": {
        "button": "tap",
        "motion": ["left_up", "right_up"],
    },
    # Roles are picked with the `caller` / `player` tags, which come from
    # the game's own COMMANDS. The caller drives the round with the button;
    # a player is caught by moving during FREEZE or standing still during
    # DANCE, both read through MotionDetector, hence shake.
    "freeze_dance": {
        "button": "tap",
        "motion": ["shake"],
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
        self._game_src = None  # last loaded game's source, for _game_reads_battery
        self._display_source = None  # host-supplied display (_icon.py) code
        self._game_mod = None
        self._game_name = None
        self._task = None
        self._hw = None
        self._old_stdout = None
        self._loop = None
        self.sim_state = None
        self._local_splats = 1   # Splats paired to the simulated wand
        self._game_splats = 1    # what a newly loaded game starts with (set_game_splats)
        self._splats_key = None  # (source, _game_splats) _local_splats was last set from
        self._pair_ctl = None    # splatpair.SplatPairing, kept across games
        self.net = None          # the running lobby game's lobby_game.Net
        self.lobby_end = None    # lobby_game.last_end when the lobby gave up

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
        for name in _GAME_HELPERS:
            self._load_game_helper(name)

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
            if name in _REQUIRED_LIBS:
                raise
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
            if name in _REQUIRED_LIBS:
                raise
            import sim_state
            sim_state.emit_log("exec lib %s failed: %s" % (name, e))
            return None
        return mod

    def _load_game_helper(self, name):
        fs_path = os.path.join(_VENDOR_GAMES, name + ".py")
        src = self._read_text("vendor/games/%s.py" % name, fs_path)
        if src is None:
            raise FileNotFoundError("missing game helper module: vendor/games/%s.py" % name)
        mod = types.ModuleType(name)
        mod.__file__ = fs_path
        sys.modules[name] = mod
        exec(compile(src, fs_path, "exec"), mod.__dict__)
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
        self._display_source = None
        self._game_src = src
        self._apply_game_splats(src)
        return mod

    def set_game_splats(self, n):
        """How many Splats the wand holds when the next game loads (0..2).
        The host page sets it from the game's settings before pushing the
        source; the game code does not carry it."""
        n = int(n)
        if n < 0 or n > 2:
            raise ValueError("a wand holds 0..2 Splats, not %d" % n)
        self._game_splats = n

    def _apply_game_splats(self, src):
        """A newly loaded game starts with set_game_splats()'s count.
        Reloading the same source with the same setting (a restart) keeps
        the count, so set_local_splats() holds until either changes."""
        key = (src, self._game_splats)
        if key == self._splats_key:
            return
        self._splats_key = key
        self.set_local_splats(self._game_splats)

    def get_commands(self):
        if not self._game_mod:
            return []
        cmds = getattr(self._game_mod, "COMMANDS", None)
        if cmds is None:
            return []
        return sorted(cmds)

    def _game_reads_battery(self):
        """True when the game's play() actually reads its batt parameter.

        Every wand game declares batt now, so the signature no longer
        distinguishes them -- what matters is whether the body uses it.
        Walked with ast rather than matched with a regex so a mention in a
        comment or a string does not count.
        """
        if not self._game_src:
            return False
        import ast
        try:
            tree = ast.parse(self._game_src)
        except SyntaxError:
            return False
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef) or node.name != "play":
                continue
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name) and sub.id == "batt" and isinstance(sub.ctx, ast.Load):
                    return True
            return False
        return False

    def set_display_source(self, src):
        """The display half of the loaded game, when the host has one (a
        generated game's _icon.py). None: only a vendored display file for
        the game's name counts."""
        self._display_source = src or None

    def _has_display_file(self):
        if self._display_source:
            return True
        if not self._game_name or self._game_name == "custom":
            return False
        rel = "vendor/display/games/%s.py" % self._game_name
        return self._read_text(rel, os.path.join(_VENDOR, "display", "games",
                                                 self._game_name + ".py")) is not None

    def _game_sends_dicts(self):
        """True when the game source passes a dict literal to an ESP-NOW send
        (enow.broadcast({...}), enow.send_to(mac, {...})) -- the messages a
        display or another device reads."""
        if not self._game_src:
            return False
        import ast
        try:
            tree = ast.parse(self._game_src)
        except SyntaxError:
            return False
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ("broadcast", "send_to")
                    and any(isinstance(a, ast.Dict) for a in node.args)):
                return True
        return False

    def _splat_fields(self):
        mod = self._game_mod
        smin = getattr(mod, "SPLATS_MIN", None)
        smax = getattr(mod, "SPLATS_MAX", None)
        return {
            "lobby_game": smin is not None,
            "local_splats": self._local_splats,
            "splats_min": smin,
            "splats_max": smax,
            "uses_display": self._game_sends_dicts(),
            "has_display_file": self._has_display_file(),
        }

    def get_capabilities(self):
        """Return what the loaded game actually uses, for filtering controls.

        nfcTags and battery are derived live from the loaded module; button
        and motion come from _TEACHER_TABLE (see its comment for why), and
        default to "show everything" when the game isn't in that table —
        the important path, since a freshly generated jumpin.py never will
        be.
        """
        if not self._game_mod:
            return {"button": "tap", "motion": list(_ALL_MOTION), "nfcTags": [], "battery": False,
                    "buzzer": True, "lobby_game": False, "local_splats": self._local_splats, "splats_min": None,
                    "splats_max": None, "uses_display": False, "has_display_file": False}

        mod = self._game_mod
        import game_tags

        # main.py documents COMMANDS as the name a game unions EXIT_TAGS
        # into, and every vendored game uses it except freeze_dance.py,
        # which calls the same set GAME_COMMANDS. Read either rather than
        # show that game no tags at all — its whole role-select step is
        # tag-driven. (The naming divergence is in the Bag trees, not here.)
        commands = set(getattr(mod, "COMMANDS", None)
                       or getattr(mod, "GAME_COMMANDS", None) or [])
        own_exit_tags = getattr(mod, "_EXIT_TAGS", None)
        # exit_tags_excluding(own_tag) drops exactly one tag from EXIT_TAGS;
        # recover it by diffing rather than re-parsing the game's call site.
        own_tag = (game_tags.EXIT_TAGS - own_exit_tags) if own_exit_tags is not None else set()
        game_specific = (commands - game_tags.EXIT_TAGS) | (own_tag & commands)
        nfc_tags = sorted(game_specific)

        battery = self._game_reads_battery()

        table = _TEACHER_TABLE.get(self._game_name, {})
        return {
            "button": table.get("button", "tap"),
            "motion": list(table.get("motion", _ALL_MOTION)),
            "nfcTags": nfc_tags,
            "battery": battery,
            "buzzer": True,  # every wand game plays sound; not derived
            **self._splat_fields(),
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
        enow = await self._maybe_await(ESPNowManager())
        await self._maybe_await(enow.init())

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

    # ── Lobby games (main.py _run_games / _enter_lobby) ─────────────

    def set_local_splats(self, n):
        """Splats paired to the simulated wand (0..pairing.MAX_SPLATS). Takes
        effect at the next start, as a new pairing does after a reset."""
        n = int(n)
        if n < 0 or n > 2:
            raise ValueError("a wand holds 0..2 Splats, not %d" % n)
        if n != self._local_splats:
            self._local_splats = n
            self._pair_ctl = None

    def _splat_limits(self):
        """main.py _splat_limits: (SPLATS_MIN, SPLATS_MAX) for a lobby game,
        else None. ValueError for an invalid declaration."""
        mod = self._game_mod
        lo = getattr(mod, "SPLATS_MIN", None)
        if lo is None:
            return None
        hi = getattr(mod, "SPLATS_MAX", None)
        if (not isinstance(lo, int) or isinstance(lo, bool) or lo < 1
                or (hi is not None and (not isinstance(hi, int) or isinstance(hi, bool) or hi < lo))):
            raise ValueError("%s: SPLATS_MIN=%r SPLATS_MAX=%r (need int >= 1, and None or >= SPLATS_MIN)"
                             % (self._game_name, lo, hi))
        return lo, hi

    def local_splat_macs(self):
        """The simulated wand's Splat MACs: 5A:00:<wand's last two bytes>:00:<i>."""
        own = self.sim_state.mac_to_str(self.sim_state.own_mac).upper()
        return ["5A:00:%s:00:%02X" % (own[-5:], i) for i in range(self._local_splats)]

    async def _pairing(self, hw):
        """main.py _boot_pairing: a SplatPairing over the simulated Splats,
        built once (a boot) and kept across games. None with no Splats."""
        macs = self.local_splat_macs()
        if not macs:
            self._pair_ctl = None
            return None
        ctl = self._pair_ctl
        if ctl is None or ctl.macs != macs:
            import splatpair
            from espnow_manager import get_own_mac
            ctl = await splatpair.SplatPairing(list(macs), hw["enow"], hw["leds"], hw["buz"],
                                               await get_own_mac())
            await ctl.poll()            # the boot connect: flash, tone, glow
            self._pair_ctl = ctl
        else:
            ctl.enow, ctl.leds, ctl.buz = hw["enow"], hw["leds"], hw["buz"]
        return ctl

    async def _enter_lobby(self, limits, hw, ctl):
        """main.py _enter_lobby: the lobby. A lobby_game.Net in its game phase, or
        None (cancelled, left or lost) after the same feedback."""
        import lobby_game
        import sim_state
        from espnow_manager import get_own_mac
        from leds import SHAPE_X, RED
        leds, buz = hw["leds"], hw["buz"]
        net = await lobby_game.enter(hw["enow"], self._game_name, limits[0], limits[1], ctl,
                                await get_own_mac(), hw["nfc"], leds, buz,
                                lambda: sim_state.button_pressed)
        self.lobby_end = None if net is not None else lobby_game.last_end
        if net is None:
            print("  lobby_game: lobby ended (%s)" % lobby_game.last_end)
            if lobby_game.last_end in ("left", "external"):
                await self._maybe_await(buz.stop())
            else:
                await self._maybe_await(leds.show_shape(SHAPE_X, RED))
                await self._maybe_await(buz.reject())
                import time
                await time.sleep_ms(500)
            await self._maybe_await(leds.off())
        return net

    async def _run_lobby(self, play, hw, limits):
        ctl = await self._pairing(hw)
        try:
            net = await self._enter_lobby(limits, hw, ctl)
            if net is None:
                return
            self.net = net
            try:
                # main.py _start_play: the arity picks how many of these the game takes.
                args = (hw["nfc"], hw["leds"], hw["buz"], hw["accel"], hw["i2c"], hw["enow"],
                        hw["batt"], net)
                n = play.__code__.co_argcount
                await self._maybe_await(play(*args[:n]))
            finally:
                await net.close()
        finally:
            if ctl is not None:
                await ctl.after_game()

    async def _run_play(self):
        from transform import reset_watchdog
        reset_watchdog()
        hw = await self._build_hw()
        self._hw = hw
        self.net = None
        self.lobby_end = None
        play = getattr(self._game_mod, "play", None)
        if play is None:
            raise RuntimeError("game module has no play()")
        limits = self._splat_limits()
        if limits is not None:
            await self._run_lobby(play, hw, limits)
            return
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
                self.sim_state.emit_end()
            except asyncio.CancelledError:
                raise
            except Exception:
                tb = traceback.format_exc()
                self.sim_state.emit_print(tb)
                self.sim_state.emit_error(tb.splitlines()[-1])
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


def set_local_splats(n):
    get_runtime().set_local_splats(n)


def set_game_splats(n):
    get_runtime().set_game_splats(n)


def set_display_source(src):
    get_runtime().set_display_source(src)
