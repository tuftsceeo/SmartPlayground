"""
Icon display host for the simulator's display panel.

Runs in its own Pyodide (or a CPython test), separate from the wand's. It
does what Stations/IconDisplay/main.py does once booted -- the idle loop
that answers start_game / stop over ESP-NOW and launches a display game with
play(nfc, panel, enow) -- without running main() itself: no pull mode, no
USB icon server, no card reader (nfc is None, as on a display without one).

The panel is SimMatrix, installed as the `icon_matrix` module. It keeps the
real Matrix API (src, set_intensity, draw_bytes, redraw, set_pixels, clear)
and reports each frame as the logical row-major src plus the intensity,
which the JS side draws with iconmaker's renderPreview().

Icons are files, as on the device: set_icons() writes <slug>_icons/<name>.py
and icons/<name>.py in the working directory, and icon_store.read_icon()
parses them on every draw, so rewriting them is all a reload needs.
"""

import asyncio
import os
import sys
import time
import traceback
import types

_PY_DIR = os.path.dirname(os.path.abspath(__file__))
_SIM_ROOT = os.path.dirname(_PY_DIR)
_SHIMS = os.path.join(_PY_DIR, "shims")
_DISPLAY = os.path.join(_SIM_ROOT, "vendor", "display")
_DISPLAY_LIB = os.path.join(_DISPLAY, "lib")

_SHIM_MODULES = (
    "sim_state",
    "machine",
    "neopixel",
    "_thread",
    "network",
    "espnow",
    "micropython",
)
_RAW_LIBS = ("display_tags", "icon_store", "shapes", "draw16", "chart16")
_TRANSFORM_LIBS = ("espnow_manager",)

# Copied from IconDisplay/main.py.
IDLE_FRAME_MS = 80
IDLE_INTENSITY = 0.15
ALERT_INTENSITY = 0.15
IDLE_REPAINT_FRAMES = 12
IDLE_GREEN = (0, 120, 0)
GREEN = (0, 120, 0)
RED = (120, 0, 0)

W = 16
H = 16
N = W * H
MAX_INTENSITY = 0.50


def _make_icon_matrix_module(host):
    """A stand-in for icon_matrix.py whose Matrix reports frames to host."""
    mod = types.ModuleType("icon_matrix")
    mod.W, mod.H, mod.N = W, H, N
    mod.DEFAULT_INTENSITY = 0.30
    mod.MAX_INTENSITY = MAX_INTENSITY

    class Matrix:
        def __init__(self, pin=0, intensity=mod.DEFAULT_INTENSITY):
            self.src = bytearray(N * 3)
            self.intensity = 0.0
            self.set_intensity(intensity)
            self.clear()

        def set_intensity(self, value):
            v = 0.0 if value is None or value < 0 else min(float(value), MAX_INTENSITY)
            self.intensity = v
            return v

        def draw_bytes(self, src):
            if len(src) != N * 3:
                raise ValueError("frame must be %d bytes, got %d" % (N * 3, len(src)))
            if src is not self.src:
                self.src[:] = src
            host._emit_frame(self)

        def redraw(self):
            host._emit_frame(self)

        def set_pixels(self, triples):
            for idx, r, g, b in triples:
                if idx < 0 or idx >= N:
                    continue
                o = idx * 3
                self.src[o] = r
                self.src[o + 1] = g
                self.src[o + 2] = b
            self.draw_bytes(self.src)

        def clear(self):
            for i in range(N * 3):
                self.src[i] = 0
            host._emit_frame(self)

        def set_orientation(self, mirror_x=None, flip_y=None, serpentine=None):
            # Orientation is a wiring property; the logical frame is unaffected.
            return (True, False, True)

    mod.Matrix = Matrix
    return mod


class _StartGameCapture:
    """Copied from IconDisplay/main.py: wraps enow so a start_game polled
    inside a game is remembered for the force-switch."""

    def __init__(self, enow):
        self._enow = enow
        self.pending_name = None

    async def poll(self, timeout_ms=0):
        mt, data, mac = await self._enow.poll(timeout_ms)
        if mt == "start_game":
            self.pending_name = data.get("name") if isinstance(data, dict) else None
        return mt, data, mac

    def __getattr__(self, attr):
        return getattr(self._enow, attr)


def icon_text(duty):
    """icon_store.write_icon()'s file format for a flat list of 768 bytes."""
    if len(duty) != N * 3:
        raise ValueError("icon must be %d values, got %d" % (N * 3, len(duty)))
    lines = ["SIZE = (%d, %d)" % (W, H), "ICON = ("]
    for row in range(H):
        parts = []
        for col in range(W):
            o = (row * W + col) * 3
            parts.append("(%d, %d, %d)" % (int(duty[o]), int(duty[o + 1]), int(duty[o + 2])))
        lines.append("    " + ", ".join(parts) + ",")
    lines.append(")")
    return "\n".join(lines) + "\n"


class IconHost:
    def __init__(self):
        self._sources = {}
        self._games = {}  # slug -> display game source
        self._frame_cb = None
        self._print_cb = None
        self._task = None
        self.panel = None
        self.enow = None
        self.running_game = None

    # ── Output ──────────────────────────────────────────────────────

    def set_frame_callback(self, cb):
        """cb(src_hex, intensity): src is 768 bytes, row-major from top-left."""
        self._frame_cb = cb

    def set_print_callback(self, cb):
        self._print_cb = cb

    def _emit_frame(self, matrix):
        if self._frame_cb:
            self._frame_cb(bytes(matrix.src).hex(), matrix.intensity)

    def _print(self, *args, sep=" ", end="\n", **kwargs):
        text = sep.join(str(a) for a in args)
        if self._print_cb:
            for line in text.split("\n"):
                self._print_cb(line)
        else:
            sys.stdout.write(text + end)

    # ── Bootstrap ───────────────────────────────────────────────────

    def bootstrap(self, file_contents=None, workdir=None, mac=None):
        """file_contents: optional relpath -> text map (keys like
        'py/shims/espnow.py', 'vendor/display/lib/shapes.py'); the
        filesystem is used for anything missing. workdir holds icons/."""
        if file_contents:
            self._sources = dict(file_contents)
        for p in (_SHIMS, _PY_DIR):
            if p not in sys.path:
                sys.path.insert(0, p)
        for name in _SHIM_MODULES:
            mod = self._exec_raw(name, "py/shims/%s.py" % name, os.path.join(_SHIMS, name + ".py"))
            mod.__sim_shim__ = True
        from time_patch import patch_time_module
        patch_time_module()

        import sim_state
        self.sim_state = sim_state
        sim_state.reset_io()
        if mac:
            sim_state.set_own_mac(mac)

        sys.modules["icon_matrix"] = _make_icon_matrix_module(self)
        for name in _RAW_LIBS:
            self._exec_raw(name, "vendor/display/lib/%s.py" % name,
                           os.path.join(_DISPLAY_LIB, name + ".py"))
        for name in _TRANSFORM_LIBS:
            self._exec_transformed(name, "vendor/display/lib/%s.py" % name,
                                   os.path.join(_DISPLAY_LIB, name + ".py"))

        wd = workdir or os.getcwd()
        os.makedirs(wd, exist_ok=True)
        os.chdir(wd)
        sys.modules["icon_store"].ensure_dir()
        return self

    def _read(self, rel_key, fs_path):
        if rel_key in self._sources:
            return self._sources[rel_key]
        if fs_path and os.path.isfile(fs_path):
            with open(fs_path, "r", encoding="utf-8") as f:
                return f.read()
        raise FileNotFoundError("missing display source: %s" % rel_key)

    def _new_module(self, name, path):
        mod = types.ModuleType(name)
        mod.__file__ = path
        mod.print = self._print
        sys.modules[name] = mod
        return mod

    def _exec_raw(self, name, rel_key, fs_path):
        src = self._read(rel_key, fs_path)
        mod = self._new_module(name, fs_path)
        exec(compile(src, fs_path, "exec"), mod.__dict__)
        return mod

    def _exec_transformed(self, name, rel_key, fs_path, src=None):
        from transform import transform_and_compile, runtime_namespace
        if src is None:
            src = self._read(rel_key, fs_path)
        code = transform_and_compile(src, filename=name + ".py")
        mod = self._new_module(name, fs_path or name + ".py")
        mod.__dict__.update(runtime_namespace())
        mod.print = self._print
        try:
            exec(code, mod.__dict__)
        except Exception:
            del sys.modules[name]
            raise
        return mod

    # ── Games and icons ─────────────────────────────────────────────

    def set_game(self, slug, src):
        """Install a display game (the game's _icon.py) under its slug."""
        if not slug or not isinstance(slug, str):
            raise ValueError("display game needs a slug")
        compile(src, slug + ".py", "exec")  # fail at install, not at launch
        self._games[slug] = src

    def is_game(self, name):
        return name in self._games

    def set_icons(self, slug, icons):
        """icons: name -> icon file text, or a flat list of 768 duty bytes."""
        import icon_store
        game_dir = "%s_icons" % slug
        os.makedirs(game_dir, exist_ok=True)
        icon_store.ensure_dir()
        for name, body in icons.items():
            icon_store.safe_name(name)
            text = body if isinstance(body, str) else icon_text(list(body))
            for d in (game_dir, icon_store.DIR):
                with open("%s/%s.py" % (d, name), "w") as f:
                    f.write(text)

    # ── Loop (IconDisplay/main.py's idle loop, radio and panel parts) ─

    def _show_idle(self, frame):
        if frame % IDLE_REPAINT_FRAMES:
            return
        import shapes
        self.panel.set_intensity(IDLE_INTENSITY)
        shapes.idle_default(self.panel, IDLE_GREEN)

    async def _flash_glyph(self, shape, rgb, hold_ms=900):
        import shapes
        self.panel.set_intensity(ALERT_INTENSITY)
        shapes.draw_shape(self.panel, shape, rgb)
        await self._sleep_ms(hold_ms)
        self.panel.clear()
        self.panel.set_intensity(IDLE_INTENSITY)

    @staticmethod
    async def _sleep_ms(ms):
        # Through _aw like a transformed game's sleep, so it counts as the
        # loop yielding for transform.py's busy-loop watchdog.
        from transform import _aw
        await _aw(time.sleep_ms(ms))

    def _fill(self, rgb):
        src = self.panel.src
        for i in range(0, len(src), 3):
            src[i], src[i + 1], src[i + 2] = rgb
        self.panel.draw_bytes(src)

    def _load_play(self, name):
        self.panel.set_intensity(IDLE_INTENSITY)
        self._fill(GREEN)
        mod = self._exec_transformed(name, None, None, src=self._games[name])
        return getattr(mod, "play")

    async def _game_load_failed(self, name, exc):
        import shapes
        self._print("  [FAIL] game load: %s (module %s)" % (name, name))
        self._print("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip())
        await self._flash_glyph(shapes.SHAPE_X, RED)
        sys.modules.pop(name, None)

    async def _launch_game(self, name):
        while self.is_game(name):
            try:
                play_func = self._load_play(name)
            except Exception as e:
                await self._game_load_failed(name, e)
                return
            wrapper = _StartGameCapture(self.enow)
            self.running_game = name
            try:
                result = play_func(None, self.panel, wrapper)
                if asyncio.iscoroutine(result):
                    await result
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self._print('{"type":"error","code":"game_error","name":"%s"}' % name)
                await self._game_load_failed(name, e)
                return
            finally:
                self.running_game = None
            next_name = wrapper.pending_name
            self.panel.clear()
            sys.modules.pop(name, None)
            if not next_name or not self.is_game(next_name):
                break
            name = next_name

    async def _idle_loop(self):
        from espnow_manager import ESPNowManager
        import icon_matrix
        from transform import reset_watchdog
        reset_watchdog()
        self.enow = await ESPNowManager()
        await self.enow.init()
        self.panel = icon_matrix.Matrix(intensity=IDLE_INTENSITY)
        frame = 0
        while True:
            frame += 1
            self._show_idle(frame)
            msg_type, data, _mac = await self.enow.poll()
            if msg_type == "start_game":
                name = data.get("name") if isinstance(data, dict) else None
                if name and self.is_game(name):
                    self.panel.clear()
                    await self._launch_game(name)
                    frame = 0
                elif name:
                    self._print("  no game %r on this display" % name)
            elif msg_type == "stop":
                self.panel.clear()
                frame = 0
            await self._sleep_ms(IDLE_FRAME_MS)

    async def start(self):
        if self._task and not self._task.done():
            await self.stop()

        async def _runner():
            try:
                await self._idle_loop()
            except asyncio.CancelledError:
                raise
            except Exception:
                self._print(traceback.format_exc().rstrip())
                raise

        self._task = asyncio.ensure_future(_runner())
        self._task.add_done_callback(lambda t: t.cancelled() or t.exception())
        return self._task

    async def stop(self):
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    def is_running(self):
        return self._task is not None and not self._task.done()


_host = None


def get_host():
    global _host
    if _host is None:
        _host = IconHost()
    return _host
