"""
Wand Module — NFC Multi-Trigger Event Engine
==============================================
Board: Seeed XIAO ESP32-C6
Requires hubtype.txt containing: wand

Triggers: buttondown, buttonup, whenshake
Actions:  playnote, note_a-g/note_c_high, turnred/green/blue/purple/yellow/white/off,
          cat, chicken, cow, dog, pig, duck, elephant, horse, goat
Combinators: and, then
Controls: start, stop, plus game tags (see lib/game_tags.py);
          start_game may also be received over ESP-NOW
Utility: battery (LED flash; status_poll is auto-answered by espnow_manager)
"""

import machine
import time
import sys

from hubtype import HUB_TYPE, HUB_CONFIG
from pn532 import PN532
from lis2dw12 import LIS2DW12, RANGE_4G
from max17048 import MAX17048

from leds import (
    Leds, TRIGGER_ORDER, battery_color, WHITE, OFF,
    SHAPE_CHECK, SHAPE_X, RED, GREEN, AMBER, CYAN, BLUE_DIM,
    # GAME_ICON palette/shapes (loading indicator, see below).
    PURPLE, ORANGE, LIME, SKY, TEAL, MAGENTA, PINK, ROSE, INDIGO,
    SHAPE_BULLSEYE, SHAPE_INNER_3x3, SHAPE_FLAME, SHAPE_MUSIC,
    SHAPE_ARROW_UP, SHAPE_ROW3, SHAPE_SPIRAL, SHAPE_SLASH_L, SHAPE_WIFI,
    SHAPE_WIFI_2, BLUE, ORANGE,
    SHAPE_RAINDROP, SHAPE_DIAMOND, SHAPE_POINTER, SHAPE_EXCLAIM,
)
from power_led import PowerLed
from buzzer import Buzzer
from nfc_reader import NfcReader
from actions import ActionRunner, ACTIONS, ANIMAL_SOUNDS, ACTION_RESOURCE, resolve_and_group, chain_to_str
from battery import show_battery
from espnow_manager import ESPNowManager
import gamelib
import brightness
import pull_flag
import game_store
import memprobe  # BENCH: see lib/memprobe.py docstring

# ─────────────────────────────────────────────
# GAME MODULES (lazy import on tap -- see below)
# ─────────────────────────────────────────────
# Each game used to be a top-level `from <game> import play` here: 15
# imports, 4719 lines of game source compiled to RAM-resident bytecode on
# EVERY boot, of which exactly one game ever runs in a given session. That
# was the root cause of "OSError: WiFi Out of Memory" at enow.init() below
# -- MicroPython's GC heap is carved out of the IDF heap in splits that
# are never returned, and the eager-import baseline left too little
# contiguous IDF heap for esp_wifi_init()/esp_wifi_start() to succeed.
# See Bag3/Code/BroadcastBox/design/2026-09-01-wifi-handoff-diagnosis.md.
#
# GAME_MODULES maps tag name -> module basename (not a callable -- the
# module is compiled only when its tag is actually tapped or ESP-NOW
# start_game names it). _load_play() below does the import.
GAME_MODULES = {
    "colorquest":     "color_quest",
    "freezedance":    "freeze_dance",
    "jumpin":         "jumpin",
    "cooking":        "cooking",
    "melody":         "melody",
    "shake":          "shake",
    "shakerainbow":   "shake_rainbow",
    "rainbow":        "rainbow",
    "jump":           "jump",
    "sound":          "sound",
    "nfcsound":       "nfc_sound",
    "simpleicecream": "simpleicecream",
    "multiicecream":  "multiicecream",
    "gestures":       "gestures",
    # Hidden (ESP-NOW only, never NFC): targeted identify animation.
    "finddevice":     "finddevice",
}

# GAME_MODULES is the built-in table. Games pulled from the Broadcast Box are
# discovered at runtime by game_store, and dev.resolve() checks both -- so a
# pulled game loads, chains and unloads by exactly the same path as a built-in.


def _check_game_modules():
    """Every tag maps to a module file actually on flash.

    The old eager imports proved this (and that the module compiled) as a
    side effect of running at boot. This is the cheap half of that
    guarantee: os.stat catches a typo'd or missing/renamed module file at
    boot without compiling anything. Accepts .mpy too, so a future
    mpy-cross precompile pass needs no change here. It cannot catch a
    module that exists but fails to compile, or has no play() -- that is
    what _game_load_failed()'s loud, on-tap failure path is for.
    """
    import os
    missing = []
    for tag in GAME_MODULES:
        mod = GAME_MODULES[tag]
        found = False
        for ext in (".py", ".mpy"):
            try:
                os.stat(mod + ext)
                found = True
                break
            except OSError:
                continue
        if not found:
            missing.append((tag, mod))
    if missing:
        print("  [ERR] game modules missing from flash: %s" % missing)


_check_game_modules()
memprobe.probe("after-imports")  # BENCH: the number that proves the fix

# ─────────────────────────────────────────────
# GAME ICON (shown briefly while a game's module is being imported)
# ─────────────────────────────────────────────
# No such name -> icon table existed anywhere on the wand before this.
# Colors are grounded where a brand color is already published to
# teachers in Live_Page/wand_icons.html (colorquest, freezedance, cooking,
# melody); the rest are chosen for maximum pairwise distinction. A
# per-pixel RGB icon system is planned separately (Stations/Icon Display
# Station/wand_icon.md) and may supersede this SHAPE_*-based table --
# noted at decision time, kept anyway per request.
GAME_ICON = {
    "colorquest":     (SHAPE_BULLSEYE,   GREEN),
    "freezedance":    (SHAPE_INNER_3x3,  PURPLE),
    "cooking":        (SHAPE_FLAME,      ORANGE),
    "melody":         (SHAPE_MUSIC,      CYAN),
    "jumpin":         (SHAPE_ARROW_UP,   LIME),
    "jump":           (SHAPE_ARROW_UP,   SKY),
    "rainbow":        (SHAPE_ROW3,       TEAL),
    "shakerainbow":   (SHAPE_SPIRAL,     MAGENTA),
    "shake":          (SHAPE_SLASH_L,    AMBER),
    "sound":          (SHAPE_MUSIC,      AMBER),
    "nfcsound":       (SHAPE_WIFI,       AMBER),
    "simpleicecream": (SHAPE_RAINDROP,   PINK),
    "multiicecream":  (SHAPE_DIAMOND,    ROSE),
    "gestures":       (SHAPE_POINTER,    INDIGO),
    "finddevice":     (SHAPE_EXCLAIM,    WHITE),
}

if set(GAME_ICON.keys()) != set(GAME_MODULES.keys()):
    print("  [ERR] GAME_ICON keys do not match GAME_MODULES")
if len(set(GAME_ICON.values())) != len(GAME_ICON):
    print("  [ERR] GAME_ICON has duplicate (shape, color) pairs -- "
          "two games would look identical while loading")

# ─────────────────────────────────────────────
# PINS FROM HUBTYPE
# ─────────────────────────────────────────────
I2C_SDA      = HUB_CONFIG["i2c_sda"]
I2C_SCL      = HUB_CONFIG["i2c_scl"]
BUZZER_PIN   = HUB_CONFIG["buzzer_pin"]
MOTOR_PIN    = HUB_CONFIG["motor_pin"]
SWITCH_PIN   = HUB_CONFIG["button_pin"]
ACCEL_INT1   = HUB_CONFIG["accel_int1_pin"]
# PN532 NFC reader lives at I2C 0x24 (lib/pn532.py).
NFC_ADDR     = HUB_CONFIG.get("nfc_addr", 0x24)

# ─────────────────────────────────────────────
# TAG COMMANDS
# ─────────────────────────────────────────────
FIXED_TRIGGERS = {"buttondown", "buttonup", "whenshake"}
COMBINATORS    = {"and", "then"}
UTILITY        = {"battery"}
BROADCAST      = {"getcode"}   # NfcReader matches the head before the ":"
# The wand's own tap-coding vocabulary. Game names and pulled slugs are added
# in main() from dev.card_commands().
BASE_COMMANDS  = FIXED_TRIGGERS | ACTIONS | ANIMAL_SOUNDS | COMBINATORS | UTILITY

# ─────────────────────────────────────────────
# ADDING A NEW GAME
# ─────────────────────────────────────────────
# Each game is a separate module in this folder that exposes a single
# `play(...)` entry point, imported lazily (on tap) rather than at boot --
# see the GAME_MODULES comment above for why. To add a new game named
# "yourgame":
#
#   1. Create `Wand Module/yourgame.py` exposing
#      `def play(dev): ...` whose loop is `while dev.running():` --
#      dev.running() pumps the radio and the card reader and goes False on
#      stop, on a start for another game, or on an exit tag.
#   2. Add `"yourgame": "yourgame"` to GAME_MODULES in this file --
#      key is the tag name, value is the module's filename (no `.py`).
#      They differ for a few games (e.g. "colorquest" -> "color_quest");
#      match your actual filename.
#   3. The teacher prints an NFC tag whose NDEF text payload is
#      `yourgame`. Tapping it from idle enters the game; tapping the
#      `stop` tag or another game tag exits back to programming mode.
#   6. Do NOT have yourgame.py register a persistent callback on enow,
#      leds, nfc, or any Pin (e.g. enow.set_status_provider, Pin.irq), and
#      do not stash a reference to any object play() was passed in a
#      module-level or other long-lived name. A game is imported and
#      unloaded on every play; a callback or stored reference into it
#      keeps the whole module pinned in RAM even after unload, defeating
#      the point of lazy loading and silently doubling the module's
#      memory cost on the next tap.
#
# See `jumpin.py` for the simplest possible example and
# `freeze_dance.py` for a more complete game (ESP-NOW messaging,
# accelerometer-driven state, multi-role logic).

# ─────────────────────────────────────────────
# NFC SLEEP TIMEOUT
# ─────────────────────────────────────────────
NFC_SLEEP_MS = 30_000  # 30 seconds of inactivity before NFC sleeps

# ─────────────────────────────────────────────
# HARDWARE (LEDs init FIRST for boot indicator)
# ─────────────────────────────────────────────
leds     = Leds()

# ── BOOT STEP 1: Power-status LED + boot indicator on immediately ──
pled     = PowerLed()   # discrete power LED on Pin 2 (Bag3)
pled.on()
leds.boot_power()

i2c      = machine.SoftI2C(sda=machine.Pin(I2C_SDA), scl=machine.Pin(I2C_SCL), freq=HUB_CONFIG["i2c_freq"])
buz      = Buzzer(BUZZER_PIN)
btn      = machine.Pin(SWITCH_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
int1_pin = machine.Pin(ACCEL_INT1, machine.Pin.IN)
motor    = machine.Pin(MOTOR_PIN, machine.Pin.OUT, value=0)

# ─────────────────────────────────────────────
# SCAN FEEDBACK
# ─────────────────────────────────────────────
def on_tag_detect(uid_hex, sak):
    pass

def on_scan_progress(frame):
    leds.scan_animate(frame)

def on_scan_complete(command):
    leds.scan_complete()
    if command:
        buz.beep(1200, 50)
        motor.value(1); time.sleep_ms(60); motor.value(0)
    else:
        buz.beep(400, 80)

def read_with_feedback(reader):
    return reader.read_command(on_detect=on_tag_detect, on_progress=on_scan_progress, on_complete=on_scan_complete)

def read_quiet(reader):
    return reader.read_command()

# ─────────────────────────────────────────────
# PRINT HELPERS
# ─────────────────────────────────────────────
def print_rules(rules, editing):
    print("  +---- Rules --------------------------------")
    has_any = False
    for trig in TRIGGER_ORDER:
        marker = " *" if trig == editing else ""
        if trig in rules and len(rules[trig]) > 0:
            print("  | %s -> [%s]%s" % (trig, chain_to_str(rules[trig]), marker))
            has_any = True
        elif trig == editing:
            print("  | %s -> (awaiting actions)%s" % (trig, marker))

    if not has_any and not editing:
        print("  | (empty -- tap a trigger tag)")
    print("  +----------------------------------------")


# ─────────────────────────────────────────────
# GAME LAUNCH
# ─────────────────────────────────────────────
def _show_game_icon(name):
    """Paint a game's icon while its (blocking) import runs.

    Passed to dev.launch() as on_load, so a tap gets an immediate response
    before the module's own entry fanfare.
    """
    shape, color = GAME_ICON.get(name, (SHAPE_MUSIC, WHITE))
    leds.show_shape(shape, color)
    memprobe.probe("pre-import:%s" % name)   # BENCH


def _launch(dev, name):
    """Run a game, showing a loud non-fatal failure if it will not load.

    The one place this file catches: a pulled game is code the teacher's LLM
    just wrote, so a module that does not compile or has no play() is expected
    input, not a wand fault. The wand says so unmistakably and stays usable.
    Three flashes with a two-tone beep -- distinct from the single X plus
    descending beeps a *pull* failure uses, so field triage without a serial
    cable can tell "pull failed" from "game would not load".
    """
    try:
        dev.launch(name, on_load=_show_game_icon)
    except Exception as e:
        print("  [FAIL] game load: %s (module %s)" % (name, dev.resolve(name)))
        sys.print_exception(e)
        memprobe.probe("load-fail:%s" % name)   # BENCH
        for _ in range(3):
            leds.show_shape(SHAPE_X, RED)
            buz.error()
            leds.off()
            time.sleep_ms(120)
        leds.show_shape(SHAPE_X, RED)
        time.sleep_ms(700)
        leds.off()
    memprobe.probe("post-game:%s" % name)   # BENCH


def _pump(dev, batt_ref):
    """Service the radio between games.

    Returns "stop", "battery", ("start", slug), or None. Showing the battery is
    the wand's own business, so it arrives as an event rather than being
    handled inside the Device.
    """
    dev.pump()
    shown = False
    ev = dev.event()
    while ev is not None:
        if ev[0] == "battery":
            show_battery(batt_ref, leds, buz)
            shown = True
        ev = dev.event()
    action = dev.take_exit()
    if action is None and shown:
        return "battery"
    return action


def show_idle(last_soc, idle_frame):
    """Show the correct idle display based on battery level."""
    # Power LED: solid when healthy, ~1Hz blink when battery is low.
    pled.update(last_soc, idle_frame)
    if last_soc <= 10:
        leds.idle_low_blink(idle_frame)
    else:
        leds.idle_default(last_soc)


# ─────────────────────────────────────────────
# EVENT LOOP (RUNNING)
# ─────────────────────────────────────────────
def run_event_loop(reader, rules, runner, accel_ref, dev, batt_ref):
    btn_was_down = (btn.value() == 0)
    if accel_ref and "whenshake" in rules:
        accel_ref.clear_wake()

    nfc_cnt = 0
    espnow_cnt = 0

    print("  Event loop active:")
    for trig in sorted(rules.keys()):
        if len(rules[trig]) > 0:
            print("    %s -> [%s]" % (trig, chain_to_str(rules[trig])))

    while True:
        fired = None
        btn_down = (btn.value() == 0)

        if btn_down and not btn_was_down:
            time.sleep_ms(30)
            if btn.value() == 0:
                if "buttondown" in rules and len(rules["buttondown"]) > 0:
                    fired = "buttondown"
        elif not btn_down and btn_was_down:
            time.sleep_ms(30)
            if btn.value() == 1:
                if "buttonup" in rules and len(rules["buttonup"]) > 0:
                    fired = "buttonup"
        btn_was_down = btn_down

        if fired is None and accel_ref and "whenshake" in rules and len(rules["whenshake"]) > 0:
            if int1_pin.value() == 1:
                accel_ref.clear_wake(); time.sleep_ms(100); accel_ref.clear_wake()
                fired = "whenshake"

        if fired:
            chain = rules[fired]
            print("  * %s -> [%s]" % (fired, chain_to_str(chain)))
            runner.run_chain(chain)

        # ESP-NOW every 5th pass -- Bag2's cadence.
        espnow_cnt += 1
        if espnow_cnt >= 5:
            espnow_cnt = 0
            action = _pump(dev, batt_ref)
            if action == "stop":
                return None
            if action:
                return action[1]

        nfc_cnt += 1
        if nfc_cnt >= 15:
            nfc_cnt = 0
            try:
                cmd, _ = read_quiet(reader)
                if cmd == "stop":
                    return
            except Exception as e:
                print("  [FAIL] card read in run mode: %s" % str(e))

        time.sleep_ms(20)


GRACE_S = 5
PULL_GRACE_S = 2


def _boot_grace():
    print("# booting -- Ctrl-C within %ds to stay at the REPL" % GRACE_S)
    for remaining in range(GRACE_S, 0, -1):
        print("# %d..." % remaining)
        time.sleep_ms(1000)


# ─────────────────────────────────────────────
# PULL MODE — runs before ESP-NOW exists this boot
# ─────────────────────────────────────────────
def _pull_fail(shape, color, sound="error"):
    """Show one failure glyph, play `sound`, and go dark.

    red wifi bars = AP not up, orange wifi bars = AP up but pull refused
    (join failure or no such game), red X = transfer itself broke.
    """
    leds.show_shape(shape, color)
    buz.play(sound)
    time.sleep_ms(900)
    leds.off()


def _pull_status(phase, tick):
    """Cycle the wifi bars in blue while the radio scans and joins.

    The two phases tick at wildly different rates and need different step
    sizes, which is why this cares which phase it is:

      scan  one call per scan, and a scan blocks for ~2.5s -- there is no
            opportunity to animate *within* one. So each call advances a
            bar, making the bars a countdown of the scan budget rather than
            decoration: 0, 1, 2 bars means first, second, last look.
      join  one call per 200ms poll, so a bar every 3 calls (~600ms) reads
            as a smooth cycle.

    A single fixed rate cannot serve both: the first version used one step
    per 3 calls and sat on 0 bars for the whole 7.5s scan phase.
    """
    leds.wifi_animate(tick, BLUE, frames_per_step=1 if phase == 'scan' else 3)


def _pull_progress(received, total):
    """Light the matrix left-to-right as bytes land.

    Palette colors only: every write is scaled by brightness.MULTIPLIER
    (0.05 indoors), so a raw dim tuple like (0, 20, 40) would arrive as
    (0, 1, 2) -- invisible.
    """
    pct = (received / total) if total else 0
    lit = max(1, int(pct * leds.num))
    for i in range(leds.num):
        leds.np[i] = CYAN if i < lit else BLUE_DIM
    leds.np.write()


def _run_pull_mode():
    """Pull new game code on a cold radio, then reboot into it.

    Only reached when the previous boot tapped `getcode`, queued a pull and
    reset. NOTHING HERE MAY TOUCH ESP-NOW -- the entire reason for the
    reboot is that this join happens on a radio ESP-NOW has never
    initialised, which is the only state that joins reliably (see
    pull_flag.py for the measurements).

    Returns only when the attempt budget is spent, so the caller falls
    through to a normal boot. Success and retry both reset the chip.
    """
    if not pull_flag.budget_left():
        print("# pull: attempt budget spent -- giving up, booting normally")
        pull_flag.clear()
        _pull_fail(SHAPE_X, RED)
        return

    memprobe.probe("pull-mode:entry")  # BENCH

    n = pull_flag.bump()
    wanted = pull_flag.requested_slug()
    print("# pull mode: attempt %d/%d for %r -- Ctrl-C within %ds to stay at the REPL"
          % (n, pull_flag.MAX_ATTEMPTS, wanted or "<active>", PULL_GRACE_S))
    for remaining in range(PULL_GRACE_S, 0, -1):
        print("# %d..." % remaining)
        time.sleep_ms(1000)

    leds.fill(BLUE_DIM)
    buz.start()

    import code_puller
    # BENCH: code_puller.pull() has its own memprobe calls bracketing the
    # radio join and the transfer body (pull:pre-wifi-join, post-wifi-join,
    # pre-body, post-body, cleanup, etc.) -- these two just mark the whole
    # call's outer boundary from main.py's side of the import.
    memprobe.probe("pull-mode:pre-pull")  # BENCH
    # enow is deliberately not passed: there is no ESP-NOW on this boot to
    # shut down, and omitting it keeps _shutdown_espnow() out of the path.
    ok = code_puller.pull(verbose=True, on_progress=_pull_progress,
                          on_status=_pull_status, slug=wanted)
    memprobe.probe("pull-mode:post-pull")  # BENCH

    # Three of the four failures are certain: a second boot would scan the
    # same air, join the same AP and ask for the same missing game. Spending
    # the retry budget on them just makes the wand unresponsive for another
    # ~10s, when the teacher's fix is to retap once the Box is ready. So
    # clear the flag, show which one it was, and boot normally.
    if ok == 'noap':
        print("# pull: %r AP not up -- giving up" % code_puller.SSID)
        pull_flag.clear()
        _pull_fail(SHAPE_WIFI_2, RED)
        return

    if ok == 'nojoin':
        print("# pull: AP visible but pairing failed -- giving up")
        pull_flag.clear()
        _pull_fail(SHAPE_WIFI_2, ORANGE)
        return

    if ok == 'norequest':
        # The Box said it has no such game. Retrying cannot change that, so
        # spend no more budget.
        print("# pull: Box has no game %r -- giving up" % wanted)
        pull_flag.clear()
        _pull_fail(SHAPE_WIFI_2, ORANGE, sound="reject")
        return

    if ok:
        pull_flag.clear()
        leds.show_shape(SHAPE_CHECK, GREEN)
        buz.success()
        time.sleep_ms(600)
        print("# pull OK -- resetting into the new game")
        machine.reset()

    # Failed. The flag stays set, so reset rather than falling through --
    # the retry needs a cold radio too, and this boot's is no longer clean.
    # Only a broken *transfer* gets here, and that is the one failure a
    # fresh radio has a real chance of getting past -- so this one retries.
    print("# pull failed mid-transfer -- resetting to retry (%d/%d spent)"
          % (n, pull_flag.MAX_ATTEMPTS))
    leds.show_shape(SHAPE_X, RED)
    buz.warn()
    time.sleep_ms(600)
    machine.reset()


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    # Before anything else, and before ESP-NOW claims the radio.
    if pull_flag.is_pending():
        _run_pull_mode()

    _boot_grace()
    memprobe.probe("main-entry")  # BENCH
    print("\n" + "=" * 50)
    print("  PlaygroundV5 -- Multi-Trigger Event Engine")
    print("  Hub type: %s" % HUB_TYPE)
    print("=" * 50)

    # NOTE: leds.boot_power() was already called at module level — LED 0 is dim white.
    # Turning it green here confirms that main() was reached and imports succeeded.
    # If an import fails before main() runs, LED 0 stays dim white permanently.
    leds.boot_stage_ok(0)

    # ── ESP-NOW init — deliberately radio-first, ahead of every other ──
    # boot stage. esp_wifi_init()/esp_wifi_start() need tens of KB of
    # *contiguous* internal IDF heap, and MicroPython's GC heap is carved
    # out of that same IDF heap in splits that are NEVER returned. Every
    # splits-triggering allocation made before this point (a sensor driver
    # import, a compile) is a permanent, one-way loss against the
    # contiguity WiFi needs -- so WiFi has to ask first, while the heap is
    # least fragmented. This was measured directly: with enow.init() left
    # at its old position (after Stage 3, before Stage 4) the wand hit
    # "OSError: WiFi Out of Memory" with idf_free=12116; moved here it
    # succeeds. See design/2026-09-01-wifi-handoff-diagnosis.md.
    #
    # No stage number of its own: SHAPE_LEFT_COL has exactly five pixels
    # (stages 0-4) and none to spare. It reports into stage 0's otherwise-
    # unused data row instead (_BOOT_STAGE_DATA[0]) -- rightmost cell.
    # ESP-NOW failing is non-fatal (NFC programming mode does not need the
    # radio), unlike Stage 3's fatal NFC failure below.
    enow = ESPNowManager()
    memprobe.probe("pre-enow"); memprobe.frag("pre-enow")  # BENCH
    try:
        enow.init()
        leds.boot_stage_ok(0, row_colors=[OFF, OFF, OFF, GREEN])
    except Exception as e:
        print("  [WARN] ESP-NOW:"); sys.print_exception(e)
        leds.boot_stage_ok(0, row_colors=[OFF, OFF, OFF, AMBER])
    memprobe.probe("post-enow")  # BENCH

    # The Device is what a game receives. This file owns the hardware; gamelib
    # owns finding, running and unloading the game file.
    dev = gamelib.Device(enow, builtins=GAME_MODULES)
    dev.leds = leds
    dev.buz = buz
    dev.i2c = i2c
    dev.button = btn
    dev.motor = motor

    # ── Stage 1: Brightness calibration (OPT3002) ──
    leds.boot_stage_start(1)
    try:
        from opt3002 import OPT3002
        light = OPT3002(i2c)
        light.init()
        m, lux = brightness.calibrate(light)
        if lux is not None:
            print("  Light: %.0f lux -> brightness x%.2f" % (lux, m))
            # Build a 1-4 LED bar in WHITE_DIM representing ambient light level.
            if lux < 200:    lit = 1   # very dim indoor
            elif lux < 600:  lit = 2   # typical indoor
            elif lux < 8000: lit = 3   # bright indoor / overcast outdoor
            else:            lit = 4   # outdoor / direct light
            row = [WHITE if i < lit else OFF for i in range(4)]
            leds.boot_stage_ok(1, row_colors=row)
        else:
            print("  Light: sensor reads failed, brightness x%.2f" % m)
            leds.boot_stage_warn(1)
    except Exception as e:
        print("  [WARN] OPT3002: %s — brightness x1.00" % e)
        leds.boot_stage_warn(1)

    # ── Stage 2: Battery gauge (MAX17048) ──
    leds.boot_stage_start(2)
    batt = None
    last_soc = 100
    try:
        batt = MAX17048(i2c)
        v, s = batt.read_all()
        last_soc = max(0, min(100, int(s)))
        print("  Battery: %.2fV, %.1f%%" % (v, s))
        # Build a 1-4 LED bar in battery_color proportional to SOC.
        lit = max(1, round(last_soc / 100 * 4))
        batt_col = battery_color(last_soc)
        row = [batt_col if i < lit else OFF for i in range(4)]
        leds.boot_stage_ok(2, row_colors=row, row_flash=5 if last_soc <= 10 else 0)
    except Exception as e:
        print("  [WARN] Battery:"); sys.print_exception(e)
        leds.boot_stage_warn(2)

    # enow was init'd radio-first, above Stage 1 -- see that block. batt
    # exists only from here on, so the status-provider hookup waits for it.
    if batt is not None:
        dev.batt = batt
        enow.set_status_provider(lambda b=batt: int(b.soc))

    # ── Stage 3: NFC init (fatal on failure) ──
    leds.boot_stage_start(3)
    nfc = PN532(i2c, NFC_ADDR)
    try:
        ic, ver, rev = nfc.begin()
        print("  PN532 firmware %d.%d (IC 0x%02X) -- NFC ready" % (ver, rev, ic))
        leds.boot_stage_ok(3)
    except Exception as e:
        print("  [FAIL] NFC:"); sys.print_exception(e)
        leds.boot_stage_fail(3)
        return

    dev.nfc = nfc
    commands = BASE_COMMANDS | dev.card_commands()
    reader = NfcReader(nfc, commands, prefixes=BROADCAST)
    dev.reader = reader
    runner = ActionRunner(leds, buz)

    # ── Stage 4: Accelerometer ──
    leds.boot_stage_start(4)
    accel = None
    accel_ok = False
    try:
        accel = LIS2DW12(i2c)
        accel.init(fs_range=RANGE_4G)
        accel_ok = True
        print("  Accelerometer OK")
        leds.boot_stage_ok(4)
    except Exception as e:
        print("  [WARN] Accel:"); sys.print_exception(e)
        leds.boot_stage_warn(4)

    # Wake-up interrupt is a separate step — if it fails, sleep-on-movement
    # is disabled. Downgrade stage 4 to amber to reflect the degraded state.
    if accel_ok:
        try:
            accel.enable_wake_int1(threshold=8)
            print("  Accel wake-up (INT1) armed")
        except Exception as e:
            print("  [WARN] Accel wake:"); sys.print_exception(e)
            accel_ok = False
            leds.boot_stage_warn(4)

    dev.accel = accel if accel_ok else None

    print("  Boot complete — all systems OK")
    memprobe.probe("boot-complete")  # BENCH
    time.sleep_ms(1500)  # hold boot bar so it can be read before idle takes over

    # Transition to idle
    leds.off()
    time.sleep_ms(100)

    # ── State ──
    rules = {}
    editing = None
    pending_combinator = None
    last_uid = None

    # ── Idle / NFC sleep state ──
    last_activity_ms = time.ticks_ms()
    nfc_sleeping = False
    idle_frame = 0

    # ── Auto-launch a just-pulled game ──
    # The pull runs in its own boot and ends in machine.reset(), so this is
    # the first boot with the new file on flash. Launching it here is what
    # makes the tap feel like "tap the card, play the game" instead of "tap
    # the card, wait for two reboots, then tap a second card". take_last_pulled()
    # clears the marker as it reads, so this fires exactly once.
    _just_pulled = game_store.take_last_pulled()
    if _just_pulled:
        print("  Launching just-pulled game: %s" % _just_pulled)
        _launch(dev, _just_pulled)
        last_activity_ms = time.ticks_ms()
        last_uid = None

    show_idle(last_soc, 0)
    print("\n  Tap a TRIGGER tag to start programming\n")

    while True:
        try:
            # ─────────────────────────────────────
            # NFC SLEEPING — minimal power mode
            # ─────────────────────────────────────
            if nfc_sleeping:
                idle_frame += 1
                pled.update(last_soc, idle_frame)  # keep power LED alive while asleep
                leds.idle_sleep()  # static blue dot

                # Check ESP-NOW broadcasts while sleeping
                result = _pump(dev, batt)
                if result == "stop":
                    dev.net.clear_peers()
                    rules = {}; editing = None; pending_combinator = None
                    buz.stop()
                    nfc_sleeping = False
                    last_activity_ms = time.ticks_ms()
                    idle_frame = 0
                    show_idle(last_soc, 0)
                    print("  Reset via broadcast")
                elif isinstance(result, tuple):
                    _, name = result
                    dev.net.clear_peers()
                    rules = {}; editing = None; pending_combinator = None
                    buz.stop()
                    nfc_sleeping = False
                    leds.off()
                    _launch(dev, name)
                    last_activity_ms = time.ticks_ms()
                    idle_frame = 0
                    show_idle(last_soc, 0)
                    last_uid = None
                elif result == "battery":
                    last_activity_ms = time.ticks_ms()
                    nfc_sleeping = False

                if nfc_sleeping:
                    leds.idle_sleep()

                # Check accelerometer or button for wake
                wake = False
                if btn.value() == 0:
                    wake = True
                elif accel_ok:
                    try:
                        x, y, z = accel.read()
                        mag = abs(x) + abs(y) + abs(z)
                        # At rest mag ≈ 1.0g; movement pushes it above 1.4
                        if mag > 1.4:
                            wake = True
                    except Exception as e:
                        print("  [FAIL] accel read while asleep: %s" % str(e))

                if wake:
                    print("  Movement detected — waking NFC")
                    try:
                        nfc.begin()
                    except Exception as ex:
                        print("  NFC wake error: %s" % str(ex))
                    nfc_sleeping = False
                    last_activity_ms = time.ticks_ms()
                    idle_frame = 0
                    # Refresh battery SOC on wake
                    if batt:
                        try:
                            _, s = batt.read_all()
                            last_soc = max(0, min(100, int(s)))
                        except Exception as e:
                            print("  [FAIL] battery read: %s" % str(e))
                    show_idle(last_soc, 0)

                time.sleep_ms(100)
                continue

            # ─────────────────────────────────────
            # NORMAL NFC POLLING
            # ─────────────────────────────────────
            uid_peek, sak_peek = reader.detect_tag()

            if uid_peek is None:
                if last_uid is not None:
                    last_uid = None

                # Check broadcast while idle
                result = _pump(dev, batt)
                if result == "stop":
                    dev.net.clear_peers()
                    rules = {}; editing = None; pending_combinator = None
                    buz.stop()
                    last_activity_ms = time.ticks_ms()
                    idle_frame = 0
                    show_idle(last_soc, 0)
                    print("  Reset via broadcast")
                elif isinstance(result, tuple):
                    _, name = result
                    dev.net.clear_peers()
                    rules = {}; editing = None; pending_combinator = None
                    buz.stop()
                    leds.off()
                    _launch(dev, name)
                    last_activity_ms = time.ticks_ms()
                    idle_frame = 0
                    show_idle(last_soc, 0)
                    last_uid = None
                elif result == "battery":
                    last_activity_ms = time.ticks_ms()

                # Idle display — battery-colored inner ring (static)
                idle_frame += 1
                show_idle(last_soc, idle_frame)

                # Check if we should sleep the NFC
                if accel_ok and time.ticks_diff(time.ticks_ms(), last_activity_ms) > NFC_SLEEP_MS:
                    nfc_sleeping = True
                    print("  NFC sleeping (30s idle) — move or press button to wake")

                time.sleep_ms(200)
                continue

            # ─────────────────────────────────────
            # TAG DETECTED — reset activity timer
            # ─────────────────────────────────────
            last_activity_ms = time.ticks_ms()
            idle_frame = 0

            if uid_peek == last_uid:
                time.sleep_ms(200); continue

            cmd, uid = read_with_feedback(reader)
            last_uid = uid
            if cmd is None:
                time.sleep_ms(200); continue

            # ── BROADCAST BOX PULL ──
            # Deliberately does NOT pull here. ESP-NOW has owned the radio
            # for this entire boot, and a WiFi join from that state fails --
            # measured 3/3 on real taps, either STAT_WRONG_PASSWORD then
            # stuck STAT_CONNECTING, or STAT_IDLE for the whole 15s window.
            # A cold radio joins first try, every time. So queue the pull and
            # reboot: the next boot runs it in _run_pull_mode() before
            # ESPNowManager is ever constructed. See pull_flag.py.
            if cmd == "getcode" or cmd.startswith("getcode:"):
                # "getcode:<slug>" asks the Box for that specific game;
                # a bare "getcode" takes whatever the Box has active.
                # nfc_reader has already validated the slug's shape.
                wanted = cmd[8:] if cmd.startswith("getcode:") else ""
                print("# getcode tapped (slug=%r) -- queueing pull, rebooting"
                      % wanted)
                leds.fill(BLUE_DIM)
                buz.start()
                try:
                    pull_flag.set_pending(wanted)
                except OSError as e:
                    # Flag unwritable (full/corrupt fs). Rebooting now would
                    # just come back to the idle loop having lost the tap, so
                    # report it instead.
                    print("# could not write pull flag: %s" % e)
                    leds.show_shape(SHAPE_X, RED)
                    buz.error()
                    time.sleep_ms(800)
                    leds.off()
                    last_activity_ms = time.ticks_ms()
                    idle_frame = 0
                    show_idle(last_soc, 0)
                    last_uid = None
                    continue
                time.sleep_ms(300)   # let the beeps finish before the reset
                machine.reset()

            # ── UTILITY ──
            if cmd == "battery":
                show_battery(batt, leds, buz)
                # Refresh SOC after battery display
                if batt:
                    try:
                        _, s = batt.read_all()
                        last_soc = max(0, min(100, int(s)))
                    except Exception as e:
                        print("  [FAIL] battery read: %s" % str(e))
                last_activity_ms = time.ticks_ms()
                idle_frame = 0
                show_idle(last_soc, 0); continue

            # ── GAME DISPATCH ──
            if dev.is_game(cmd):
                leds.off()
                _launch(dev, cmd)
                last_activity_ms = time.ticks_ms()
                idle_frame = 0
                show_idle(last_soc, 0); last_uid = None; continue

            # ── STOP ──
            if cmd == "stop":
                dev.net.clear_peers()
                rules = {}; editing = None; pending_combinator = None
                buz.stop()
                last_activity_ms = time.ticks_ms()
                idle_frame = 0
                show_idle(last_soc, 0)
                print("  STOP — rules cleared")
                print_rules(rules, editing); continue

            # ── START (run mode) ──
            if cmd == "start":
                if not rules or all(len(v) == 0 for v in rules.values()):
                    buz.reject()
                    print("  Nothing to run")
                    show_idle(last_soc, 0); continue
                print("  ── RUNNING ──")
                leds.show_running(rules)
                buz.confirm()
                start_game_name = run_event_loop(reader, rules, runner, accel, dev, batt)
                print("  ── STOPPED ──")
                rules = {}; editing = None; pending_combinator = None
                last_activity_ms = time.ticks_ms()
                idle_frame = 0
                if start_game_name:
                    dev.net.clear_peers()
                    buz.stop()
                    leds.off()
                    _launch(dev, start_game_name)
                    last_uid = None
                show_idle(last_soc, 0)
                print_rules(rules, editing); continue

            # ── COMBINATOR ──
            if cmd in COMBINATORS:
                if editing is None:
                    buz.reject()
                    print("  Combinator '%s' ignored — no active trigger" % cmd)
                else:
                    pending_combinator = cmd
                    print("  Combinator: %s (next action will %s)" % (cmd, "add to group" if cmd == "and" else "start new step"))
                    buz.tick()
                show_idle(last_soc, 0); continue

            # ── TRIGGER ──
            if cmd in FIXED_TRIGGERS:
                if cmd not in rules:
                    rules[cmd] = []
                editing = cmd
                pending_combinator = None
                print("  Editing trigger: %s" % cmd)
                leds.show_programming(rules, editing)
                print_rules(rules, editing); continue

            # ── ACTION ──
            # Chain shape contract: list[list[str]] — outer list is THEN-groups,
            # inner list is AND-group of simultaneous actions.
            # ActionRunner.run_chain expects: [["turnred", "note_a"], ["playnote"]]
            if cmd in ACTIONS or cmd in ANIMAL_SOUNDS:
                if editing is None:
                    editing = "buttondown"
                    if editing not in rules:
                        rules[editing] = []
                    print("  Auto-selected trigger: buttondown")

                chain = rules[editing]

                if pending_combinator == "and" and len(chain) > 0:
                    # Add to current AND group
                    last_group = chain[-1]
                    if isinstance(last_group, list):
                        last_group.append(cmd)
                    else:
                        # Defensive: fix up legacy bare-string entries
                        chain[-1] = [last_group, cmd]
                elif pending_combinator == "then" and len(chain) > 0:
                    chain.append([cmd])
                else:
                    rules[editing] = [[cmd]]

                pending_combinator = None

                # Preview the action
                runner.run_chain([[cmd]])

                leds.show_programming(rules, editing)
                print_rules(rules, editing); continue

            print("  Unknown command: %s" % cmd)
            time.sleep_ms(200)

        except KeyboardInterrupt:
            leds.off()
            print("\n  Exiting.")
            return
        except Exception as e:
            print("  [ERR] Main loop:"); sys.print_exception(e)
            time.sleep_ms(500)
        time.sleep_ms(1)


main()

