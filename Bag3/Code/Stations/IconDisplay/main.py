"""
Icon Display — Broadcast 16x16 icon display
============================================
Board: Seeed XIAO ESP32-C6
Requires hubtype.txt containing: icon_display

Laid out like the wand's main.py (Wand Module/main.py) -- same sections, same
function names, same boot order and the same game contract -- so a fix or a
game moves between the two without translation. What differs is hardware:
a 16x16 panel instead of the 5x5 matrix, a WS1850S reader, no buzzer, button,
accelerometer or battery, and a USB link for the icon editor.

Controls: stop, getcode:<slug>[@<host>], plus game tags (lib/display_tags.py);
          start_game may also be received over ESP-NOW
Station mode (lib/display_station.py): with no game running, obeys `show` and
          `dance` messages from any wand
"""

# Radio prewarm, before any other import (AGENTS.md: nothing may allocate
# before the radio claims its memory). ESPNowManager.init() in _boot() finds
# the radio active and keeps it. Same antenna as lib/espnow_manager.py
# (EXTERNAL_ANTENNA = False: onboard, GPIO14 = 0).
try:
    import network, espnow
    from machine import Pin
    Pin(3, Pin.OUT).value(0)
    import time
    time.sleep_ms(100)
    Pin(14, Pin.OUT).value(0)
    network.WLAN(network.STA_IF).active(True)
    _e = espnow.ESPNow()
    _e.active(True)
    del _e
except Exception as _err:
    print("  [WARN] radio prewarm failed; ESPNowManager.init() will retry:", _err)

import machine
import time
import sys
import gc
import os

from hubtype import HUB_TYPE, HUB_CONFIG
from espnow_manager import ESPNowManager
from nfc_reader import NfcReader, split_prefixed
from display_tags import GAME_TAGS, CONTROL_TAGS
import game_store
import memprobe  # BENCH: see lib/memprobe.py docstring

# Pulled games live in /games/<slug>.py, on sys.path so _load_play() imports
# them with the same bare __import__(name) as a built-in.
game_store.ensure_dir()
if game_store.GAMES_DIR not in sys.path:
    sys.path.append(game_store.GAMES_DIR)

# ─────────────────────────────────────────────
# GAME MODULES (lazy import on tap)
# ─────────────────────────────────────────────
# tag name -> module basename, compiled only when its tag is tapped or an
# ESP-NOW start_game names it. A game held resident at boot is heap the radio
# cannot have.
GAME_MODULES = {
    "goalrace": "goalrace",
    "scoreboard": "scoreboard",
}

if set(GAME_MODULES.keys()) != GAME_TAGS:
    print("  [ERR] GAME_MODULES keys do not match GAME_TAGS in display_tags.py")
    print("        modules:  %s" % sorted(GAME_MODULES.keys()))
    print("        expected: %s" % sorted(GAME_TAGS))


def _module_on_flash(mod):
    """True if <mod>.py (or .mpy) is in the flash root."""
    for ext in (".py", ".mpy"):
        try:
            os.stat(mod + ext)
            return True
        except OSError:
            continue
    return False


def game_module(name):
    """Module basename for a game tag, or None if this display cannot play it.

    A built-in is playable only if its file is on flash; otherwise the name
    falls through to /games, so a missing built-in never hides a pulled game
    of the same name (goalrace is both). Built-ins win over pulled games.
    """
    if name in GAME_MODULES:
        mod = GAME_MODULES[name]
        if _module_on_flash(mod):
            return mod
    if game_store.exists(name):
        return name          # /games is on sys.path; slug == module name
    return None


def is_game(name):
    return game_module(name) is not None


memprobe.probe("after-imports")  # BENCH

# ─────────────────────────────────────────────
# PINS FROM HUBTYPE
# ─────────────────────────────────────────────
LED_PIN  = HUB_CONFIG["led_pin"]
I2C_SDA  = HUB_CONFIG["i2c_sda"]
I2C_SCL  = HUB_CONFIG["i2c_scl"]
NFC_ADDR = HUB_CONFIG["nfc_addr"]

# ─────────────────────────────────────────────
# TAG COMMANDS
# ─────────────────────────────────────────────
CONTROLS      = GAME_TAGS | CONTROL_TAGS
BROADCAST     = {"getcode"}
# Pulled games answer to their own slug. Computed once: the display resets
# after every successful pull, so this cannot go stale.
ALL_COMMANDS  = CONTROLS | set(game_store.slugs())

# ─────────────────────────────────────────────
# ADDING A NEW GAME
# ─────────────────────────────────────────────
# Same contract as the wand (Wand Module/main.py, "ADDING A NEW GAME"):
#
#   def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
#
#   nfc   -- the raw reader (Ws1850sReader, PN532-compatible), or None when no
#            reader answered; build NfcReader(nfc, COMMANDS) as a wand game does
#   leds  -- the panel (icon_matrix.Matrix): set_pixels, draw_bytes, clear,
#            set_intensity, redraw, and .src as a scratch frame
#   buz, accel, batt -- None: this device has no buzzer, accelerometer or battery
#   i2c   -- the reader's bus
#   enow  -- ESPNowManager; poll it every loop, return on "stop"/"start_game"
#   net   -- None (no lobby games here yet)
#
# play() takes as many leading parameters as it declares. The older
# play(nfc, panel, enow) shape (exactly 3 parameters) is still called the old
# way, with a ready-built NfcReader. Same rules as the wand: no persistent
# callbacks, no references kept past return.
#
# A built-in goes in GAME_MODULES here and GAME_TAGS in lib/display_tags.py;
# a game copied to /games/<slug>.py needs neither.

# ─────────────────────────────────────────────
# HARDWARE
# ─────────────────────────────────────────────
# The panel and the reader's bus are built in _boot(), after the radio:
# Matrix() takes about 2.3 KB of buffers before a pixel lights.
panel = None
leds = None     # the panel, under the wand's name for it
i2c = None

IDLE_INTENSITY = 0.15
ALERT_INTENSITY = 0.15
IDLE_FRAME_MS = 80
NFC_POLL_FRAMES = 12      # idle frames between card reads (a read is 200-500 ms)
UID_REPEAT_MS = 1200      # ignore the same uid until it has been away this long
IDLE_REPAINT_FRAMES = 12  # ~1 s at IDLE_FRAME_MS
BOOT_SCREEN_HOLD_MS = 1200
# How long a silent USB link may hold the panel before idle takes it back.
USB_QUIET_MS = 300000     # 5 minutes

RED = (120, 0, 0)
GREEN = (0, 120, 0)
BLUE = (0, 20, 160)
AMBER = (120, 60, 0)
CYAN = (0, 180, 240)
BLUE_DIM = (0, 20, 127)
IDLE_GREEN = (0, 120, 0)


def fill(rgb):
    r, g, b = rgb
    src = panel.src
    for i in range(0, len(src), 3):
        src[i] = r
        src[i + 1] = g
        src[i + 2] = b
    panel.draw_bytes(src)


def flash_glyph(shape, rgb, hold_ms=900):
    """One 5x5 glyph (lib/shapes.py, the wand's SHAPE_* set) held, then dark.
    The display's stand-in for the wand's shape-plus-sound feedback."""
    import shapes
    panel.set_intensity(ALERT_INTENSITY)
    shapes.draw_shape(panel, shape, rgb)
    time.sleep_ms(hold_ms)
    panel.clear()
    panel.set_intensity(IDLE_INTENSITY)


# ─────────────────────────────────────────────
# GAME LOADING
# ─────────────────────────────────────────────
class _StartGameCapture:
    """Wrap enow so in-game start_game polls capture the target game name."""

    def __init__(self, enow):
        self._enow = enow
        self.pending_name = None

    def poll(self, timeout_ms=0):
        mt, data, mac = self._enow.poll(timeout_ms)
        if mt == "start_game":
            self.pending_name = data.get("name") if isinstance(data, dict) else None
        elif mt == "code_push":
            _queue_push(data)
            return "stop", data, mac            # end the game; idle loop pulls
        return mt, data, mac

    def __getattr__(self, attr):
        return getattr(self._enow, attr)


def _load_play(name):
    """Compile a game's module on demand and return its play(). Raises on
    failure -- the caller turns that into the loud failure path."""
    mod_name = game_module(name)
    panel.set_intensity(IDLE_INTENSITY)
    fill(GREEN)
    memprobe.probe("pre-import:%s" % name)   # BENCH
    tok = memprobe.mark()                    # BENCH
    mod = __import__(mod_name)
    memprobe.span("import:%s" % name, tok)   # BENCH
    return getattr(mod, "play")


def _unload_game(name):
    """Drop a finished game's module so the next one starts from a cleaner
    heap. Interned strings stay; safe only because no game keeps a callback
    or reference into itself."""
    mod_name = game_module(name)
    if mod_name and mod_name in sys.modules:
        del sys.modules[mod_name]
    gc.collect()


UNLOAD_AFTER_GAME = True


def _game_load_failed(name, exc):
    """Loud, unmissable, non-fatal: a red X, then back to idle. A pulled game
    is code an LLM just wrote, so a module that will not load is expected
    input, not a device fault."""
    print("  [FAIL] game load: %s (module %s)" % (name, game_module(name)))
    sys.print_exception(exc)
    memprobe.probe("load-fail:%s" % name)   # BENCH
    import shapes
    flash_glyph(shapes.SHAPE_X, RED)
    _unload_game(name)


def _is_arity_error(e):
    """True if this TypeError is "wrong number of arguments", not a fault
    from inside the game. MicroPython words it distinctively."""
    msg = str(e)
    return ("positional argument" in msg
            or ("argument" in msg and "given" in msg))


def _start_play(play_func, name, nfc, reader, wrapper):
    """Call play() with the wand's arguments, as many as it declares. A
    3-parameter play() is the older display shape (nfc, panel, enow) and gets
    a ready-built NfcReader. Without co_argcount: try 8, then 3."""
    args = (nfc, leds, None, None, i2c, wrapper, None, None)
    code = getattr(play_func, "__code__", None)
    n = getattr(code, "co_argcount", None) if code is not None else None
    if n == 3:
        return play_func(reader, panel, wrapper)
    if n is not None:
        return play_func(*args[:n])
    try:
        return play_func(*args)
    except TypeError as e:
        if not _is_arity_error(e):
            raise
        print("  %s does not take 8 arguments; trying the 3-argument display call" % name)
        return play_func(reader, panel, wrapper)


def _launch_game(name, nfc, reader, enow):
    _run_games(name, nfc, reader, enow)


def _run_games(name, nfc, reader, enow):
    """Run a game and chain force-switches without returning to idle."""
    while is_game(name):
        try:
            play_func = _load_play(name)
        except Exception as e:
            _game_load_failed(name, e)
            return
        wrapper = _StartGameCapture(enow)
        try:
            _start_play(play_func, name, nfc, reader, wrapper)
        except TypeError as e:
            # A game that cannot even be called is a load failure; anything
            # raised from inside a running game still propagates.
            if not _is_arity_error(e):
                raise
            _game_load_failed(name, e)
            return
        next_name = wrapper.pending_name
        # Drop the reference before unloading: play_func pins the module.
        play_func = None
        wrapper = None
        panel.clear()
        memprobe.probe("post-game:%s" % name)      # BENCH
        if UNLOAD_AFTER_GAME:
            _unload_game(name)
        memprobe.probe("post-unload:%s" % name)    # BENCH
        if next_name == "finddevice":
            _find()
            break
        if not next_name or not is_game(next_name):
            break
        name = next_name


# ─────────────────────────────────────────────
# CHECK BROADCAST
# ─────────────────────────────────────────────
_station = None                   # display_station.Station, made on the first "raw" message


def check_broadcast(enow):
    """
    Poll ESP-NOW. Returns "stop", ("start_game", name), "station", or None.
    Same shape as the wand's check_broadcast(); a "raw" payload goes to
    station mode, imported on first use (after the radio is up).
    """
    global _station
    msg_type, data, _mac = enow.poll()
    if msg_type == "stop":
        return "stop"
    if msg_type == "start_game":
        name = data.get("name") if isinstance(data, dict) else None
        if name == "finddevice" or is_game(name):
            return ("start_game", name)
        print("  no game %r on this display" % name)
    if msg_type == "code_push":
        _queue_push(data)
        return "stop"                           # idle loop runs the pull
    if msg_type == "raw":
        if _station is None:
            from display_station import Station
            _station = Station(enow)
        if _station.handle(data, panel):
            return "station"
    return None


# ─────────────────────────────────────────────
# IDLE DISPLAY HELPER
# ─────────────────────────────────────────────
def show_idle(idle_frame):
    """Station mode while it shows something, else the wand's waiting
    display: a static green square (no battery here, so always green),
    repainted every IDLE_REPAINT_FRAMES."""
    if _station is not None and _station.tick(panel):
        return
    if idle_frame % IDLE_REPAINT_FRAMES:
        return
    import shapes
    panel.set_intensity(IDLE_INTENSITY)
    shapes.idle_default(panel, IDLE_GREEN)


def _end_station():
    """A stop, a tap, a pull or a game ends whatever station mode shows."""
    global _station
    _station = None


def _find():
    import shapes
    shapes.find_blink(panel, IDLE_INTENSITY)
    panel.clear()


# ─────────────────────────────────────────────
# CODE PULL DISPLAY
# ─────────────────────────────────────────────
PROGRESS_ROWS = 16        # one panel row per sixteenth of a file
_progress_row = -1


def _pull_fail(shape, color):
    """red wifi bars = no host answered, amber = host has no such game or is
    busy, red X = transfer itself broke."""
    flash_glyph(shape, color)


def _pull_progress(received, total):
    """Fill the panel a row at a time as bytes land. Redraws only when the
    row changes: the callback fires per 512-byte chunk."""
    global _progress_row
    pct = (received / total) if total else 0
    row = int(pct * PROGRESS_ROWS)
    if row > PROGRESS_ROWS:
        row = PROGRESS_ROWS
    if row == _progress_row:
        return
    _progress_row = row
    src = panel.src
    n = len(src) // 3
    lit = row * (n // PROGRESS_ROWS)
    for i in range(n):
        o = i * 3
        if i < lit:
            src[o], src[o + 1], src[o + 2] = CYAN
        else:
            src[o], src[o + 1], src[o + 2] = BLUE_DIM
    panel.draw_bytes(src)


def _espnow_pull_and_launch(enow, slug, host_id):
    """Receive this display's game file and its icons from the Box/Dial over
    ESP-NOW (lib/espnow_code.py). Unlike the wand, success resets and main()
    launches the game after the reset has handed the heap back clean."""
    global _progress_row
    import shapes
    import espnow_code
    import icon_store
    print("# getcode (slug=%r host=%r) via espnow" % (slug, host_id))
    gc.collect()
    _progress_row = -1
    panel.set_intensity(IDLE_INTENSITY)
    fill(BLUE)
    ok = espnow_code.receive(enow, slug=slug, hubtype=HUB_TYPE,
                             on_progress=_pull_progress,
                             verbose=True, host_id=host_id, icon_dir=icon_store.DIR)
    if ok is True:
        panel.set_intensity(ALERT_INTENSITY)
        shapes.draw_shape(panel, shapes.SHAPE_CHECK, GREEN)
        stats = espnow_code.LAST_STATS or {}
        game_store.set_last_pulled(stats.get("name") or slug)
        print("# pull OK -- resetting into the new game")
        time.sleep_ms(600)
        machine.reset()
    if ok == 'nohost':
        _pull_fail(shapes.SHAPE_WIFI_2, RED)
    elif ok in ('norequest', 'busy'):
        _pull_fail(shapes.SHAPE_WIFI_2, AMBER)
    else:
        _pull_fail(shapes.SHAPE_X, RED)


_pending_push = None              # (slug, host) from a Dial code_push


def _queue_push(data):
    """Record a Dial code_push; the idle loop runs it as a getcode pull."""
    global _pending_push
    _pending_push = (data.get("slug") or "", data.get("host") or "")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def _boot():
    """Bring up every device. Returns (enow, nfc, reader, server); nfc and
    reader are None when no reader answered. Radio first, then the panel
    (stage 1), the game library (2), the USB editor link (3), NFC (4)."""
    global panel, leds, i2c
    print("\n" + "=" * 50)
    print("  Icon display")
    print("  Hub type: %s" % HUB_TYPE)
    print("=" * 50)

    # ── ESP-NOW init — radio-first, ahead of every other boot stage ──
    enow = ESPNowManager()
    memprobe.probe("pre-enow")   # BENCH
    memprobe.frag("pre-enow")    # BENCH
    radio_ok = False
    try:
        enow.init()
        radio_ok = True
        enow.set_status_provider(lambda: None, kind=HUB_TYPE)
    except Exception as e:
        print("  [WARN] ESP-NOW:")
        sys.print_exception(e)

    # ── Stage 1: panel ── the boot screen can only start once it exists.
    import icon_matrix
    import icon_store
    icon_store.ensure_dir()
    panel = icon_matrix.Matrix(pin=LED_PIN, intensity=IDLE_INTENSITY)
    leds = panel
    memprobe.probe("post-panel")  # BENCH
    import shapes
    boot = shapes.BootScreen(panel)
    panel.set_intensity(IDLE_INTENSITY)
    boot.stage_ok(0, [None, None, None,
                      shapes.STAGE_OK if radio_ok else shapes.STAGE_WARN])
    boot.stage_ok(1)

    # ── Stage 2: game library ──
    n_games = len(game_store.slugs())
    boot.stage_ok(2, [shapes.STAGE_OK if i < n_games else None for i in range(4)])

    # ── Stage 3: USB link for the icon editor web app ──
    # Given the panel already built: two NeoPixel objects on one pin fight.
    from icon_server import IconServer
    server = IconServer(panel, debug=False, is_game=is_game)
    server.start()
    boot.stage_ok(3)
    memprobe.probe("post-server")  # BENCH

    # ── Stage 4: NFC (WS1850S), when one is fitted ──
    nfc = None
    reader = None
    i2c = machine.SoftI2C(sda=machine.Pin(I2C_SDA), scl=machine.Pin(I2C_SCL),
                          freq=HUB_CONFIG["i2c_freq"])
    if HUB_CONFIG.get("has_nfc"):
        from nfc_ws1850s import Ws1850sReader
        # Scan first: a reader on the wrong address otherwise looks like a
        # display that never reads a card.
        try:
            found = i2c.scan()
        except Exception as e:
            found = []
            print("  [ERR] I2C scan failed on sda=%d scl=%d: %s" % (I2C_SDA, I2C_SCL, e))
        if NFC_ADDR not in found:
            print("  [ERR] no reader at 0x%02X -- I2C holds %s"
                  % (NFC_ADDR, [hex(a) for a in found] or "nothing"))
            print("        card taps will not work this boot; everything else still runs")
            boot.stage_warn(4)
        else:
            nfc = Ws1850sReader(i2c, addr=NFC_ADDR)
            version = nfc.begin()
            reader = NfcReader(nfc, ALL_COMMANDS, prefixes=BROADCAST)
            print("  NFC reader ready at 0x%02X (WS1850S ver 0x%02X, %d commands)"
                  % (NFC_ADDR, version, len(ALL_COMMANDS)))
            boot.stage_ok(4)
    else:
        print("  No card reader fitted (hubtype has_nfc is False)")
        boot.stage_warn(4)

    time.sleep_ms(BOOT_SCREEN_HOLD_MS)
    boot.clear()
    print("  Icon display idle. %d built-in, %d pulled." % (len(GAME_MODULES), n_games))
    return enow, nfc, reader, server


def main():
    global _pending_push
    enow, nfc, reader, server = _boot()

    # No JSON identity/heartbeat lines here, unlike the wand: this USB port
    # carries the icon editor's own JSON protocol (icon_server.py).

    # ── State ──
    idle_frame = 0
    last_uid = None
    last_uid_ms = 0

    # ── Auto-launch a just-pulled game ── (_espnow_pull_and_launch resets)
    just_pulled = game_store.take_last_pulled()
    if just_pulled and is_game(just_pulled):
        print("  Launching just-pulled game: %s" % just_pulled)
        _launch_game(just_pulled, nfc, reader, enow)
    elif just_pulled:
        print("  [WARN] just-pulled %r is not a game here" % just_pulled)

    while True:
        try:
            idle_frame += 1

            # ── USB editor link ── a running game owns the loop instead, so
            # authoring pauses while one runs.
            if not server.step():
                # "repl": get out of the way without resetting (the browser
                # holds the port); "reboot": finish() resets.
                print("  USB asked for %s -- exiting main()" % server.exit_reason)
                server.finish()
                return

            # ── DIAL CODE PUSH ── same path as a getcode card tap.
            if _pending_push is not None:
                wanted, wanted_host = _pending_push
                _pending_push = None
                server.release_panel()
                _end_station()
                _espnow_pull_and_launch(enow, wanted, wanted_host)
                idle_frame = 0
                last_uid = None
                continue

            # ── Bench start_game over USB (icon_server.do_start_game) ──
            if server.pending_start_game:
                name = server.pending_start_game
                server.pending_start_game = None
                if is_game(name):
                    _end_station()
                    panel.clear()
                    _launch_game(name, nfc, reader, enow)
                    last_uid = None
                    idle_frame = 0
                else:
                    import shapes
                    print("  [WARN] bench start_game %r is no longer a game here" % (name,))
                    flash_glyph(shapes.SHAPE_QUESTION, AMBER, hold_ms=400)

            # ── Check broadcast ── every pass: a wand starting a game must
            # not wait on a card read.
            result = check_broadcast(enow)
            if result == "stop":
                server.release_panel()
                _end_station()
                panel.clear()
                idle_frame = 0
            elif isinstance(result, tuple) and result[0] == "start_game":
                server.release_panel()
                _end_station()
                if result[1] == "finddevice":
                    _find()
                else:
                    panel.clear()
                    _launch_game(result[1], nfc, reader, enow)
                last_uid = None
                idle_frame = 0
            elif result == "station":
                server.release_panel()

            # ── Idle display ── yields to the editor once it has drawn.
            if not server.owns_panel(time.ticks_ms(), USB_QUIET_MS):
                show_idle(idle_frame)

            # ── NFC every NFC_POLL_FRAMES ── a read is 200-500 ms.
            if reader is None or idle_frame % NFC_POLL_FRAMES:
                time.sleep_ms(IDLE_FRAME_MS)
                continue
            cmd, uid = reader.read_command()
            now = time.ticks_ms()
            if uid is not None and uid == last_uid and \
                    time.ticks_diff(now, last_uid_ms) < UID_REPEAT_MS:
                cmd = None             # same card still on the reader
            if uid is not None:
                last_uid = uid
                last_uid_ms = now
            if cmd is None:
                time.sleep_ms(IDLE_FRAME_MS)
                continue
            server.release_panel()
            _end_station()

            # ── BROADCAST BOX PULL ──
            head, wanted, wanted_host = split_prefixed(cmd)
            if head == "getcode":
                if enow.is_active:
                    _espnow_pull_and_launch(enow, wanted, wanted_host)
                else:
                    import shapes
                    _pull_fail(shapes.SHAPE_WIFI_2, RED)
                last_uid = None
                idle_frame = 0
                continue

            # ── GAME DISPATCH ──
            if is_game(cmd):
                panel.clear()
                _launch_game(cmd, nfc, reader, enow)
                last_uid = None
                idle_frame = 0
                continue

            # ── STOP ──
            if cmd == "stop":
                panel.clear()
                idle_frame = 0
                continue

            # Also where a game tag lands when this display does not have it.
            print("  Unknown command: %s" % cmd)
            import shapes
            flash_glyph(shapes.SHAPE_QUESTION, AMBER, hold_ms=400)

        except KeyboardInterrupt:
            panel.clear()
            print("\n  Exiting.")
            return
        except Exception as e:
            print("  [ERR] Main loop:")
            sys.print_exception(e)
            time.sleep_ms(500)
        time.sleep_ms(1)


if __name__ == "__main__":
    main()
