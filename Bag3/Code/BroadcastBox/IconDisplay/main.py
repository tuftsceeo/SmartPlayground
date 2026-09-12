"""
main.py -- Broadcast icon display.

Boots, idles, and loads/runs/switches/unloads single-file game modules the
way MockWand does. The pattern is copied from MockWand/main.py rather than
shared with it: the two devices have nothing in common below the loop shape,
and a game you can read on its own is worth more than one loop that serves
both.

Game entry point:

    def play(nfc, panel, enow):

    nfc   -- NfcReader, or None until the card reader is fitted (has_nfc)
    panel -- the icon_matrix.Matrix itself: set_pixels, draw_bytes, clear,
             set_intensity, redraw, and .src as a scratch frame
    enow  -- ESPNowManager (already initialized; poll every loop iteration)

This device has no buzzer and no accelerometer, so everything it says it
says on the panel or over serial.

BOOT ORDER IS LOAD-BEARING. The radio is claimed before icon_matrix is even
imported. esp_wifi_init()/esp_wifi_start() need tens of KB of contiguous
internal IDF heap, MicroPython's GC heap is carved out of that same heap in
splits that are never returned, and Matrix() takes a 768-byte NeoPixel
buffer, a 512-byte offset table, a 256-byte LUT and a 768-byte frame before
a single pixel lights. Building the panel first is the same mistake that
produced "OSError: WiFi Out of Memory" on the wand.
"""

import gc
import sys
import time
import machine

# ─────────────────────────────────────────────
# PULL MODE -- must be the first thing main() does
# ─────────────────────────────────────────────
# A getcode tap queues a pull and resets; the next boot runs it here, before
# ESPNowManager is ever constructed. A WiFi join only succeeds on a radio
# ESP-NOW has never touched this boot. See pull_flag.py.
import pull_flag
import game_store
from display_tags import GAME_TAGS, CONTROL_TAGS
import memprobe  # BENCH: see lib/memprobe.py docstring

# Safe this early: hubtype.py imports nothing and touches no pins, it only
# reads /hubtype.txt. icon_matrix and icon_store are NOT -- importing
# icon_store pulls in icon_matrix, and that is what must wait for the radio.
from hubtype import HUB_TYPE, HUB_CONFIG

DEBUG = False

PULL_GRACE_S = 3          # seconds at the REPL before a queued pull starts
NFC_POLL_FRAMES = 12      # idle frames between card reads -- a read is 200-500ms
UID_REPEAT_MS = 1200      # ignore the same uid until it has been away this long
IDLE_FRAME_MS = 80

# Pulled games live in /games/<slug>.py. Putting that directory on sys.path
# is what lets _load_play() import a pulled game with the same bare
# __import__(name) it uses for a built-in.
game_store.ensure_dir()
if game_store.GAMES_DIR not in sys.path:
    sys.path.append(game_store.GAMES_DIR)

# ─────────────────────────────────────────────
# GAME MODULES (lazy import on tap)
# ─────────────────────────────────────────────
# tag name -> module basename. NOT a callable: the module is compiled only
# when its tag is actually tapped or an ESP-NOW start_game names it. Every
# game held resident at boot is heap the radio cannot have.
GAME_MODULES = {
    "goalrace": "goalrace",
}

if set(GAME_MODULES.keys()) != GAME_TAGS:
    print("  [ERR] GAME_MODULES keys do not match GAME_TAGS in display_tags.py")
    print("        modules:  %s" % sorted(GAME_MODULES.keys()))
    print("        expected: %s" % sorted(GAME_TAGS))

# Every tag the reader should recognise: built-ins, whatever has been pulled,
# and the controls. Rebuilt after a pull-driven reset, not during a session.
ALL_COMMANDS = set(GAME_MODULES.keys()) | set(game_store.slugs()) | CONTROL_TAGS


def game_module(name):
    """Module basename for a game tag, or None if there is no such game.

    Built-ins win over pulled games: a pulled file can never shadow one.
    """
    if name in GAME_MODULES:
        return GAME_MODULES[name]
    if game_store.exists(name):
        return name          # /games is on sys.path; slug == module name
    return None


def is_game(name):
    return game_module(name) is not None


# ─────────────────────────────────────────────
# PANEL FEEDBACK
# ─────────────────────────────────────────────
# No buzzer and no 5x5 glyph set here, so status is whole-panel colour at low
# intensity. Nothing in this file draws above IDLE_INTENSITY: MAX_INTENSITY
# is a measured supply ceiling, not a preference, and a panel that sits lit
# continuously should run well under it.
IDLE_INTENSITY = 0.12
ALERT_INTENSITY = 0.25

BLACK = (0, 0, 0)
RED = (120, 0, 0)
GREEN = (0, 120, 0)
BLUE = (0, 20, 160)
AMBER = (120, 60, 0)


def fill(panel, rgb):
    r, g, b = rgb
    src = panel.src
    for i in range(0, len(src), 3):
        src[i] = r
        src[i + 1] = g
        src[i + 2] = b
    panel.draw_bytes(src)


def flash(panel, rgb, times=3, on_ms=180, off_ms=120):
    """Blink the whole panel. The only attention-getter this device has."""
    panel.set_intensity(ALERT_INTENSITY)
    for _ in range(times):
        fill(panel, rgb)
        time.sleep_ms(on_ms)
        panel.clear()
        time.sleep_ms(off_ms)
    panel.set_intensity(IDLE_INTENSITY)


def show_idle(panel, frame):
    """A slow dim blue breath, so an idle display is visibly alive."""
    step = frame % 32
    level = step if step < 16 else 31 - step
    panel.set_intensity(IDLE_INTENSITY)
    fill(panel, (0, 4 + level, 20 + level * 2))


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
        return mt, data, mac

    def __getattr__(self, attr):
        return getattr(self._enow, attr)


def _load_play(name, panel):
    """Compile a game's module on demand and return its play(). Raises on
    failure -- the caller turns that into the loud failure path."""
    mod_name = game_module(name)
    panel.set_intensity(IDLE_INTENSITY)
    fill(panel, GREEN)
    memprobe.probe("pre-import:%s" % name)   # BENCH
    tok = memprobe.mark()                    # BENCH
    mod = __import__(mod_name)
    memprobe.span("import:%s" % name, tok)   # BENCH
    return getattr(mod, "play")


def _unload_game(name):
    """Drop a finished game's module so the next one starts from a cleaner
    heap rather than stacking on top of it.

    Reclaims the module's globals dict, its function objects and bytecode,
    and its non-interned constants. Does NOT reclaim interned strings, so
    each distinct game loaded in one boot leaves a small permanent residual.
    Safe only because no game may hold a callback or a retained reference
    into itself.
    """
    mod_name = game_module(name)
    if mod_name and mod_name in sys.modules:
        del sys.modules[mod_name]
    gc.collect()


def _game_load_failed(name, exc, panel):
    """Loud, unmissable, non-fatal. The display returns to idle and stays
    usable.

    A pulled game is code an LLM just wrote, so a module that will not
    import or has no play() is expected input, not a device fault. With no
    buzzer here, the whole panel flashes red -- readable across a room,
    which is the point.
    """
    print("  [FAIL] game load: %s (module %s)" % (name, game_module(name)))
    sys.print_exception(exc)
    memprobe.probe("load-fail:%s" % name)   # BENCH
    flash(panel, RED, times=3)
    # A partial success (module compiled, no play()) can leave a stub entry
    # in sys.modules; clear it so the next tap recompiles cleanly instead of
    # reusing a module that will fail the same way silently.
    _unload_game(name)


UNLOAD_AFTER_GAME = True


def _launch_game(name, nfc, panel, enow):
    """Run a game and chain force-switches without returning to idle."""
    while is_game(name):
        try:
            play_func = _load_play(name, panel)
        except Exception as e:
            _game_load_failed(name, e, panel)
            return
        wrapper = _StartGameCapture(enow)
        play_func(nfc, panel, wrapper)
        next_name = wrapper.pending_name
        # Drop the reference before unloading -- play_func is what pins the
        # module in this frame; a chained force-switch must not compile the
        # next game on top of a still-referenced one.
        play_func = None
        wrapper = None
        panel.clear()
        memprobe.probe("post-game:%s" % name)      # BENCH
        if UNLOAD_AFTER_GAME:
            _unload_game(name)
        memprobe.probe("post-unload:%s" % name)    # BENCH
        if not next_name or not is_game(next_name):
            break
        name = next_name


# ─────────────────────────────────────────────
# PULL MODE
# ─────────────────────────────────────────────
def _run_pull_mode(panel, icon_dir):
    """Join the Box's SoftAP and fetch this display's game file and icons.

    Only reached when the previous boot tapped getcode, queued a pull and
    reset. NOTHING HERE MAY TOUCH ESP-NOW -- the whole reason for the reboot
    is that the join happens on a radio ESP-NOW has never initialised.

    Returns only when the attempt budget is spent, so the caller falls
    through to a normal boot. Success and retry both reset the chip.
    """
    if not pull_flag.budget_left():
        print("# pull: attempt budget spent -- giving up, booting normally")
        pull_flag.clear()
        flash(panel, RED)
        return

    n = pull_flag.bump()
    wanted = pull_flag.requested_slug()
    print("# pull mode: attempt %d/%d for %r -- Ctrl-C within %ds to stay at the REPL"
          % (n, pull_flag.MAX_ATTEMPTS, wanted or "<active>", PULL_GRACE_S))
    for remaining in range(PULL_GRACE_S, 0, -1):
        print("# %d..." % remaining)
        time.sleep_ms(1000)

    panel.set_intensity(IDLE_INTENSITY)
    fill(panel, BLUE)

    import code_puller
    # hubtype tells the Box which file this slug means for this device;
    # icon_dir asks for the named-icon leg after it. enow is deliberately
    # not passed: there is no ESP-NOW on this boot to shut down.
    ok = code_puller.pull(verbose=True, slug=wanted,
                          hubtype=HUB_TYPE, icon_dir=icon_dir)

    # Three of the four failures are certain -- a second boot would scan the
    # same air, join the same AP and ask for the same missing game -- so they
    # spend no more budget.
    if ok == 'noap':
        print("# pull: %r AP not up -- giving up" % code_puller.SSID)
        pull_flag.clear()
        flash(panel, RED)
        return
    if ok == 'nojoin':
        print("# pull: AP visible but pairing failed -- giving up")
        pull_flag.clear()
        flash(panel, AMBER)
        return
    if ok == 'norequest':
        print("# pull: Box has no %r for an icon display -- giving up" % wanted)
        pull_flag.clear()
        flash(panel, AMBER)
        return
    if ok:
        pull_flag.clear()
        flash(panel, GREEN, times=2)
        print("# pull OK -- resetting into the new game")
        machine.reset()

    # A broken transfer is the one failure a fresh radio has a real chance of
    # getting past, so this one retries. The flag stays set.
    print("# pull failed mid-transfer -- resetting to retry (%d/%d spent)"
          % (n, pull_flag.MAX_ATTEMPTS))
    flash(panel, RED)
    machine.reset()


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    # ── 1. Radio first ── see the module docstring. Nothing above this line
    # imports icon_matrix, and nothing below it may be moved above.
    from espnow_manager import ESPNowManager
    enow = ESPNowManager()
    memprobe.probe("pre-enow")   # BENCH
    memprobe.frag("pre-enow")    # BENCH
    try:
        enow.init()
        print("  ESP-NOW ready")
    except Exception as e:
        print("  [WARN] ESP-NOW:")
        sys.print_exception(e)

    # ── 2. Panel ──
    import icon_matrix
    import icon_store
    icon_store.ensure_dir()
    panel = icon_matrix.Matrix(pin=HUB_CONFIG["led_pin"], intensity=IDLE_INTENSITY)
    memprobe.probe("post-panel")  # BENCH

    # ── 3. A queued pull runs before the session proper ──
    if pull_flag.is_pending():
        _run_pull_mode(panel, icon_store.DIR)

    # ── 4. Card reader, when one is fitted ──
    nfc = None
    reader = None
    if HUB_CONFIG.get("has_nfc"):
        from machine import Pin, SoftI2C
        from pn532 import PN532
        from nfc_reader import NfcReader
        i2c = SoftI2C(sda=Pin(HUB_CONFIG["i2c_sda"]),
                      scl=Pin(HUB_CONFIG["i2c_scl"]),
                      freq=HUB_CONFIG["i2c_freq"])
        nfc = PN532(i2c, addr=HUB_CONFIG["nfc_addr"])
        nfc.begin()
        nfc.SAMConfig()
        reader = NfcReader(nfc, ALL_COMMANDS, prefixes={"getcode"})
        print("  NFC reader ready (%d commands)" % len(ALL_COMMANDS))
    else:
        print("  No card reader fitted (hubtype has_nfc is False)")

    # A game that just landed launches itself on this boot rather than
    # waiting for a second tap.
    pulled = game_store.take_last_pulled()
    if pulled and is_game(pulled):
        print("  launching just-pulled game %r" % pulled)
        _launch_game(pulled, reader, panel, enow)

    print("  Icon display idle. %d built-in, %d pulled."
          % (len(GAME_MODULES), len(game_store.slugs())))

    # ── 5. Idle loop ──
    frame = 0
    last_uid = None
    last_uid_ms = 0
    while True:
        frame += 1
        show_idle(panel, frame)

        # ESP-NOW every pass: a wand starting a game must not wait on a
        # card read.
        msg_type, data, _mac = enow.poll()
        if msg_type == "start_game":
            name = data.get("name") if isinstance(data, dict) else None
            if name and is_game(name):
                panel.clear()
                _launch_game(name, reader, panel, enow)
                last_uid = None
                frame = 0
            elif name:
                print("  [WARN] start_game names an unknown game: %r" % name)
        elif msg_type == "stop":
            panel.clear()
            frame = 0

        # Cards every NFC_POLL_FRAMES: a read is 200-500ms and would stall
        # the loop if it ran every frame.
        if reader is not None and frame % NFC_POLL_FRAMES == 0:
            cmd, uid = reader.read_command()
            now = time.ticks_ms()
            if uid is not None and uid == last_uid and \
                    time.ticks_diff(now, last_uid_ms) < UID_REPEAT_MS:
                # Same card still sitting on the reader -- it reads over and
                # over otherwise, and the game looks like it restarts itself.
                cmd = None
            if uid is not None:
                last_uid = uid
                last_uid_ms = now

            if cmd == "getcode" or (cmd and cmd.startswith("getcode:")):
                # Queue and reboot rather than pull here: ESP-NOW has owned
                # the radio all boot, and a WiFi join from that state fails.
                wanted = cmd[8:] if cmd.startswith("getcode:") else ""
                print("# getcode tapped (slug=%r) -- queueing pull, rebooting" % wanted)
                fill(panel, BLUE)
                try:
                    pull_flag.set_pending(wanted)
                except OSError as e:
                    # Flag unwritable. Rebooting now would lose the tap, so
                    # say so instead of silently returning to idle.
                    print("# could not write pull flag: %s" % e)
                    flash(panel, RED)
                    continue
                time.sleep_ms(300)
                machine.reset()
            elif cmd == "stop":
                panel.clear()
                frame = 0
            elif cmd and is_game(cmd):
                panel.clear()
                _launch_game(cmd, reader, panel, enow)
                last_uid = None
                frame = 0
            elif cmd:
                print("  [WARN] unrecognised card: %r" % cmd)

        time.sleep_ms(IDLE_FRAME_MS)


if __name__ == "__main__":
    main()
