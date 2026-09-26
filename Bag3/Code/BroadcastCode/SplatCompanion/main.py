"""
Splat Companion — ESP-NOW <-> BLE bridge and game station
============================================================
Board: Seeed XIAO ESP32-C6 (hubtype.txt: splat_companion), paired over
UART1 (GPIO0 TX / GPIO1 RX) with a second board (M5StickS3 or XIAO C6)
running EspnowModem/modem/main.py. ESP-NOW never runs on this board's own
radio -- it goes to the modem over UART (lib/espnow_manager.py, the EUM
drop-in). This board's own radio is BLE only, to one Splat.

Games get: def play(splat, leds, enow, batt=None)
    splat  a splat_api.SplatAPI: connected, poll() -> "press"/"release"/None
           (call every loop!), color(name), sound(name), note(name),
           play(names), off(). No NFC, buzzer, motor or accelerometer here.
    leds   this device's 3-pixel status strip (status_leds.StatusLeds):
           fill(color), off().
    enow   an already-initialised espnow_manager.ESPNowManager (the EUM
           drop-in). Poll every loop; return on "stop" or a start_game
           naming another game.
    batt   a max17048.MAX17048, or None if the gauge failed at boot.

Idle (no game running), this device also runs the ESP-NOW<->BLE bridge
from companion.py: splat_config/splat_cmd/stop from a wand play the Splat
directly, and every press/release relays back as splat_event. A game tag,
tapped or arriving as ESP-NOW start_game, pauses the bridge and hands the
same BLE link to the game; the bridge resumes when the game returns.
"""

import sys
import time
import machine

import pull_flag

# ── Nothing above this line, and nothing before the check below runs, may
# import ubluetooth, espnow_manager, or any other radio-claiming module.
# is_pending() itself only stats a file. See pull_flag.py's docstring for
# the measurement this rests on: a cold radio joins the Box/Dial's SoftAP
# first try, every time; a radio BLE or ESP-NOW has already touched this
# boot failed 3/3 on real taps.
from status_leds import StatusLeds
from hubtype import HUB_TYPE, HUB_CONFIG

status = StatusLeds(HUB_CONFIG["led_pin"], HUB_CONFIG["num_leds"])
status.fill((0, 0, 15))

import game_store
from splat_tags import GAME_TAGS, CONTROL_TAGS
from nfc_reader import NfcReader, split_prefixed
import memprobe  # BENCH: see lib/memprobe.py's docstring

# Games pulled from a Box/Dial live in /games/<slug>.py -- same convention
# as MockWand, so a pulled game imports with the same bare __import__(name)
# as a built-in. Done before ALL_COMMANDS below reads game_store.slugs().
game_store.ensure_dir()
if game_store.GAMES_DIR not in sys.path:
    sys.path.append(game_store.GAMES_DIR)

# ─────────────────────────────────────────────
# GAME MODULES (lazy import on tap or start_game)
# ─────────────────────────────────────────────
GAME_MODULES = {
    "splatwhack": "splatwhack",
}

if set(GAME_MODULES.keys()) != GAME_TAGS:
    print("  [ERR] GAME_MODULES keys do not match GAME_TAGS in lib/splat_tags.py")
    print("        modules:  %s" % sorted(GAME_MODULES.keys()))
    print("        expected: %s" % sorted(GAME_TAGS))


def _module_on_flash(mod):
    for ext in (".py", ".mpy"):
        try:
            import os
            os.stat(mod + ext)
            return True
        except OSError:
            continue
    return False


def game_module(name):
    """Module basename for a game tag, or None if unplayable here.

    Same contract as MockWand's: every game is optional. A built-in whose
    file is missing, or a tag naming neither a built-in nor a pulled slug,
    reads as "not a game here" -- see docs_and_design/DEVICE_ONBOARDING_SURFACES.md
    rule 10, "games are optional skills".
    """
    if name in GAME_MODULES:
        mod = GAME_MODULES[name]
        if _module_on_flash(mod):
            return mod
    if game_store.exists(name):
        return name
    return None


def is_game(name):
    return name is not None and game_module(name) is not None


# ─────────────────────────────────────────────
# JSON TELEMETRY (output-only, mirrors MockWand's)
# ─────────────────────────────────────────────
SPLAT_VERSION = "0.1.0"


def _emit(obj):
    """One JSON line. No try/except -- a bad payload is a bug here, not a
    runtime condition to hide."""
    import json
    print(json.dumps(obj))


memprobe.probe("after-imports")  # BENCH

# ─────────────────────────────────────────────
# PULL MODE — runs before BLE or ESP-NOW exist this boot
# ─────────────────────────────────────────────
PULL_COLOR = (0, 0, 40)
PULL_OK_COLOR = (0, 40, 0)
PULL_FAIL_COLOR = (40, 0, 0)
PULL_REJECT_COLOR = (40, 20, 0)


def _pull_progress(received, total):
    pct = (received / total) if total else 0
    lit = max(1, int(pct * status.np.n))
    status.np.fill((0, 0, 0))
    for i in range(lit):
        status.np[i] = (0, 30, 30)
    status.np.write()


def _pull_status(phase, tick):
    # No wifi-bar animation on a 3-pixel strip; blink instead.
    status.fill(PULL_COLOR if tick % 2 == 0 else (0, 0, 0))


def _pull_fail(color):
    status.fill(color)
    time.sleep_ms(900)
    status.off()


def _run_pull_mode():
    """Pull new game code on a cold radio, then reboot into it.

    Only reached when a previous boot tapped getcode, queued a pull and
    reset. NOTHING HERE MAY TOUCH BLE OR ESP-NOW.
    """
    if not pull_flag.budget_left():
        print("# pull: attempt budget spent -- giving up, booting normally")
        pull_flag.clear()
        _pull_fail(PULL_FAIL_COLOR)
        return

    memprobe.probe("pull-mode:entry")  # BENCH

    n = pull_flag.bump()
    wanted = pull_flag.requested_slug()
    wanted_host = pull_flag.requested_host()
    print("# pull mode: attempt %d/%d for %r on host %r"
          % (n, pull_flag.MAX_ATTEMPTS, wanted or "<active>", wanted_host or "<any>"))

    status.fill(PULL_COLOR)

    import code_puller
    memprobe.probe("pull-mode:pre-pull")  # BENCH
    ok = code_puller.pull(verbose=True, on_progress=_pull_progress,
                          on_status=_pull_status, slug=wanted,
                          host_id=wanted_host, hubtype=HUB_TYPE)
    if code_puller.DEBUG_PULL:
        import pull_probe
        print("# DBG pull boot: reset_cause=%s"
              % pull_probe.reset_cause(machine))
    memprobe.probe("pull-mode:post-pull")  # BENCH

    if ok == 'noap':
        print("# pull: %r AP not up -- giving up" % code_puller.SSID)
        pull_flag.clear()
        _pull_fail(PULL_FAIL_COLOR)
        return

    if ok == 'nojoin':
        print("# pull: AP visible but pairing failed -- giving up")
        pull_flag.clear()
        _pull_fail(PULL_REJECT_COLOR)
        return

    if ok == 'norequest':
        print("# pull: Box has no game %r -- giving up" % wanted)
        pull_flag.clear()
        _pull_fail(PULL_REJECT_COLOR)
        return

    if ok:
        pull_flag.clear()
        status.fill(PULL_OK_COLOR)
        time.sleep_ms(600)
        print("# pull OK -- resetting into the new game")
        machine.reset()

    # Only a broken transfer retries -- see pull_flag.py.
    print("# pull failed mid-transfer -- resetting to retry (%d/%d spent)"
          % (n, pull_flag.MAX_ATTEMPTS))
    status.fill(PULL_FAIL_COLOR)
    time.sleep_ms(600)
    machine.reset()


# ─────────────────────────────────────────────
# GAME LAUNCH (NFC + ESP-NOW start_game, force-switch chaining)
# ─────────────────────────────────────────────
class _StartGameCapture:
    """Wrap enow so an in-game start_game poll captures the target name."""

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


def _load_play(name):
    mod_name = game_module(name)
    status.fill((0, 20, 20))
    memprobe.probe("pre-import:%s" % name)  # BENCH
    mod = __import__(mod_name)
    memprobe.probe("post-import:%s" % name)  # BENCH
    return getattr(mod, "play")


def _unload_game(name):
    """Drop a finished game's module. See MockWand's main.py for why this
    is safe only when no game keeps a stored reference into itself."""
    mod_name = game_module(name)
    if mod_name and mod_name in sys.modules:
        del sys.modules[mod_name]
    import gc
    gc.collect()


def _is_arity_error(e):
    msg = str(e)
    return ("positional argument" in msg
            or ("argument" in msg and "given" in msg))


def _start_play(play_func, name, splat, leds, wrapper, batt_ref):
    """Call play(), tolerating an older 3-arg signature (no batt) the same
    way MockWand tolerates an older 6-arg one -- see its main.py."""
    args = (splat, leds, wrapper, batt_ref)
    code = getattr(play_func, "__code__", None)
    n = getattr(code, "co_argcount", None) if code is not None else None
    if n is not None:
        return play_func(*args[:n]) if n < len(args) else play_func(*args)
    try:
        return play_func(*args)
    except TypeError as e:
        if not _is_arity_error(e):
            raise
        print("  %s takes the older three-argument play(); calling it that way"
              % name)
        return play_func(*args[:3])


def _game_load_failed(name, exc):
    print("  [FAIL] game load: %s (module %s)" % (name, game_module(name)))
    sys.print_exception(exc)
    _emit({"type": "error", "where": "game_load", "slug": name, "err": str(exc)})
    memprobe.probe("load-fail:%s" % name)  # BENCH
    for _ in range(3):
        status.fill(PULL_FAIL_COLOR)
        time.sleep_ms(150)
        status.off()
        time.sleep_ms(150)
    _unload_game(name)


def _launch_game(name, splat, enow, batt_ref):
    """Run a game and chain force-switches without returning to idle.

    The bridge (companion.py) is not serviced while a game runs -- the
    game's `splat` object polls the same BLE link directly instead. This
    is the same "one loop owns the link at a time" rule as MockWand's
    "one loop owns enow" for games vs. the trigger/rules engine.

    splat.off() runs in `finally`, on every exit path (normal return, a
    failed load, or an exception): a game that forgets to silence the
    Splat before returning must not leave it lit or sounding once the
    bridge resumes.
    """
    try:
        while is_game(name):
            try:
                play_func = _load_play(name)
            except Exception as e:
                _game_load_failed(name, e)
                return
            wrapper = _StartGameCapture(enow)
            _emit({"type": "game_start", "slug": name})
            try:
                _start_play(play_func, name, splat, status, wrapper, batt_ref)
            except TypeError as e:
                if not _is_arity_error(e):
                    raise
                _game_load_failed(name, e)
                return
            _emit({"type": "game_end", "slug": name})
            next_name = wrapper.pending_name
            play_func = None
            wrapper = None
            memprobe.probe("post-game:%s" % name)  # BENCH
            _unload_game(name)
            memprobe.probe("post-unload:%s" % name)  # BENCH
            if not next_name or not is_game(next_name):
                break
            name = next_name
    finally:
        splat.off()


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    # Before anything else, and before BLE or ESP-NOW claim any radio.
    if pull_flag.is_pending():
        _run_pull_mode()
        # Falls through only when the attempt budget is spent.

    print("\n" + "=" * 50)
    print("  Splat Companion")
    print("  Hub type: %s" % HUB_TYPE)
    print("=" * 50)

    # ── BLE first: it must claim its controller memory before anything
    # else *activates a radio*. See AGENTS.md's memory-order rule. Module
    # imports above (game_store, splat_tags, nfc_reader/pn532's constants,
    # the 3-pixel status strip) are small, non-radio allocations, the same
    # ones MockWand's main.py makes before enow.init() -- see its
    # docstring. UNVERIFIED at this size combination; the memprobe.probe()
    # calls bracketing this block are what the first bench run checks.
    memprobe.probe("pre-ble")  # BENCH
    import ubluetooth
    ubluetooth.BLE().active(True)
    memprobe.probe("post-ble")  # BENCH
    status.fill((0, 0, 15))

    import espnow_manager
    from splat_link import SplatLink
    from companion import Companion
    from splat_api import SplatAPI

    link = SplatLink()
    mgr = espnow_manager.ESPNowManager()
    memprobe.probe("pre-enow")  # BENCH
    try:
        mgr.init()
        memprobe.probe("post-enow")  # BENCH
    except OSError as e:
        status.fill(PULL_FAIL_COLOR)
        print("  [FATAL] no EUM modem on UART%d tx=%d rx=%d: %s"
              % (espnow_manager.UART_ID, espnow_manager.UART_TX,
                 espnow_manager.UART_RX, e))
        raise

    # ── Battery + PN532, non-fatal on failure: a missing gauge or reader
    # costs only that capability (rule 9/10), and the bridge still runs.
    i2c = machine.SoftI2C(sda=machine.Pin(HUB_CONFIG["i2c_sda"]),
                          scl=machine.Pin(HUB_CONFIG["i2c_scl"]),
                          freq=HUB_CONFIG["i2c_freq"])
    batt = None
    if HUB_CONFIG.get("has_battery"):
        try:
            from max17048 import MAX17048
            batt = MAX17048(i2c)
            v, s = batt.read_all()
            print("  Battery: %.2fV, %.1f%%" % (v, s))
            mgr.set_status_provider(lambda b=batt: int(b.soc))
        except Exception as e:
            print("  [WARN] Battery:"); sys.print_exception(e)
            batt = None

    reader = None
    if HUB_CONFIG.get("has_nfc"):
        try:
            from pn532 import PN532
            nfc = PN532(i2c, HUB_CONFIG.get("nfc_addr", 0x24))
            ic, ver, rev = nfc.begin()
            print("  PN532 firmware %d.%d (IC 0x%02X) -- NFC ready" % (ver, rev, ic))
            all_commands = GAME_TAGS | CONTROL_TAGS | set(game_store.slugs())
            reader = NfcReader(nfc, all_commands, prefixes={"getcode"})
        except Exception as e:
            print("  [WARN] NFC reader not available:"); sys.print_exception(e)
            reader = None
            # Boot-time I2C scan, so a wrong address reads off the log
            # instead of the reader silently ignoring every tap.
            try:
                found = i2c.scan()
                print("  I2C devices found: %s"
                      % [hex(a) for a in found])
            except Exception:
                pass

    comp = Companion(mgr, link, status, is_game_fn=is_game)
    probe = None
    if DEBUG_PROBE:
        import companion_probe
        probe = companion_probe.Probe(comp, PROBE_EVERY_MS)
    print("  Boot complete\n")
    _emit({
        "type": "identity", "device": "splat_companion", "version": SPLAT_VERSION,
        "hub": HUB_TYPE, "games": sorted(list(GAME_MODULES.keys()) + game_store.slugs()),
    })

    _just_pulled = game_store.take_last_pulled()
    if _just_pulled:
        print("  Launching just-pulled game: %s" % _just_pulled)
        splat = SplatAPI(link)
        try:
            _launch_game(_just_pulled, splat, mgr, batt)
        except Exception as e:
            _game_load_failed(_just_pulled, e)

    run_event_loop(comp, reader, mgr, batt, probe)


HEARTBEAT_MS = 5000
NFC_POLL_EVERY = 8   # frames between quiet NFC polls, like MockWand's cadence
DEBUG_PROBE = False          # periodic stats from companion_probe.py
PROBE_EVERY_MS = 10000


def run_event_loop(comp, reader, enow, batt_ref, probe=None):
    """Idle loop: run the ESP-NOW<->BLE bridge, poll NFC for a tag, launch
    a game or a pull on one, and launch a game on ESP-NOW start_game."""
    frame = 0
    last_heartbeat = time.ticks_ms()
    last_uid = None

    while True:
        now = time.ticks_ms()
        if time.ticks_diff(now, last_heartbeat) >= HEARTBEAT_MS:
            last_heartbeat = now
            _emit({"type": "heartbeat", "up": now})
        try:
            comp.step()
            if probe is not None:
                probe.maybe_print()

            start_name = comp.pending_start_game
            if start_name is not None:
                comp.pending_start_game = None
                print("  ESP-NOW start_game: %s" % start_name)
                splat = SplatAPI(comp.link)
                _launch_game(start_name, splat, enow, batt_ref)
                last_uid = None

            frame += 1
            if reader is not None and frame % NFC_POLL_EVERY == 0:
                uid_peek, sak_peek = reader.detect_tag()
                if uid_peek is None:
                    last_uid = None
                elif uid_peek != last_uid:
                    cmd, uid = reader.read_command()
                    last_uid = uid
                    if cmd:
                        head, wanted, wanted_host = split_prefixed(cmd)
                        if head == "getcode":
                            print("# getcode tapped (slug=%r host=%r) -- "
                                  "queueing pull, rebooting" % (wanted, wanted_host))
                            # Deliberately no comp.shutdown() here: the chip
                            # resets in a moment regardless, and the pull
                            # itself must run on a radio nothing has
                            # touched this boot -- see pull_flag.py.
                            try:
                                pull_flag.set_pending(wanted, wanted_host)
                            except OSError as e:
                                print("# could not write pull flag: %s" % e)
                                continue
                            time.sleep_ms(200)
                            machine.reset()
                        elif cmd == "stop":
                            print("  STOP tag")
                            # The bridge's own "stop" handling (splat_config
                            # cleared, splat silenced) is for ESP-NOW stop;
                            # an NFC stop while idle has nothing else to do.
                        elif is_game(cmd):
                            splat = SplatAPI(comp.link)
                            _launch_game(cmd, splat, enow, batt_ref)
                            last_uid = None
                        else:
                            print("  Unknown NFC command: %s" % cmd)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print("  [ERR] Main loop:"); sys.print_exception(e)
            time.sleep_ms(500)
        time.sleep_ms(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  Exiting.")
        status.off()
