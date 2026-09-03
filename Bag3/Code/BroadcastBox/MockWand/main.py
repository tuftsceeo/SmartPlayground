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
import json

from hubtype import HUB_TYPE, HUB_CONFIG
from pn532 import PN532
from lis2dw12 import LIS2DW12, RANGE_4G
from max17048 import MAX17048

from leds import (
    Leds, TRIGGER_ORDER, battery_color, WHITE, OFF,
    SHAPE_CHECK, SHAPE_X, RED, GREEN, CYAN, BLUE_DIM,
)
from power_led import PowerLed
from buzzer import Buzzer
from nfc_reader import NfcReader
from actions import ActionRunner, ACTIONS, ANIMAL_SOUNDS, ACTION_RESOURCE, resolve_and_group, chain_to_str
from battery import show_battery
from espnow_manager import ESPNowManager
from color_quest import play as play_color_quest
from freeze_dance import play as play_freeze_dance
from jumpin import play as play_jumpin
from cooking import play as play_cooking
from melody import play as play_melody
from shake import play as play_shake
from shake_rainbow import play as play_shake_rainbow
from rainbow import play as play_rainbow
from jump import play as play_jump
from sound import play as play_sound
from nfc_sound import play as play_nfc_sound
from simpleicecream import play as play_simpleicecream
from multiicecream import play as play_multiicecream
from gestures import play as play_gestures
from finddevice import play as play_finddevice
from game_tags import GAME_TAGS, CONTROL_TAGS, HIDDEN_TAGS
import brightness
import pull_flag

# ─────────────────────────────────────────────
# GAME DISPATCH
# ─────────────────────────────────────────────
GAME_DISPATCH = {
    "colorquest":     play_color_quest,
    "freezedance":    play_freeze_dance,
    "jumpin":         play_jumpin,
    "cooking":        play_cooking,
    "melody":         play_melody,
    "shake":          play_shake,
    "shakerainbow":   play_shake_rainbow,
    "rainbow":        play_rainbow,
    "jump":           play_jump,
    "sound":          play_sound,
    "nfcsound":       play_nfc_sound,
    "simpleicecream": play_simpleicecream,
    "multiicecream":  play_multiicecream,
    "gestures":       play_gestures,
    # Hidden (ESP-NOW only, never NFC): targeted identify animation.
    "finddevice":     play_finddevice,
}

if set(GAME_DISPATCH.keys()) != (GAME_TAGS | HIDDEN_TAGS):
    print("  [ERR] GAME_DISPATCH keys do not match GAME_TAGS|HIDDEN_TAGS in game_tags.py")
    print("        dispatch: %s" % sorted(GAME_DISPATCH.keys()))
    print("        expected: %s" % sorted(GAME_TAGS | HIDDEN_TAGS))

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
CONTROLS       = GAME_TAGS | CONTROL_TAGS
UTILITY        = {"battery"}
BROADCAST      = {"getcode"}
ALL_COMMANDS   = FIXED_TRIGGERS | ACTIONS | ANIMAL_SOUNDS | COMBINATORS | CONTROLS | UTILITY | BROADCAST

# ─────────────────────────────────────────────
# ADDING A NEW GAME
# ─────────────────────────────────────────────
# Each game is a separate module in this folder that exposes a single
# `play(...)` entry point. To add a new game named "yourgame":
#
#   1. Create `Wand Module/yourgame.py` exposing
#      `def play(nfc, leds, buz, accel, i2c, enow): ...` returning when
#      "stop" NFC tag, ESP-NOW stop, or ESP-NOW start_game is received
#      (poll enow every loop).
#   2. Add the line `from yourgame import play as play_yourgame` near
#      the existing `play_jumpin` import at the top of this file.
#   3. Add the tag name `"yourgame"` to GAME_TAGS in lib/game_tags.py.
#   4. Add `"yourgame": play_yourgame` to GAME_DISPATCH in this file.
#   5. In yourgame.py, union EXIT_TAGS into COMMANDS and exit when
#      `cmd in EXIT_TAGS` so kids can switch games via any game tag.
#   6. The teacher prints an NFC tag whose NDEF text payload is
#      `yourgame`. Tapping it from idle enters the game; tapping the
#      `stop` tag or another game tag exits back to programming mode.
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
# GAME LAUNCH (NFC + ESP-NOW force-switch)
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


def _launch_game(name, nfc, leds, buz, accel, i2c, enow, batt_ref):
    """Run a game and chain force-switches without returning to idle."""
    while name in GAME_DISPATCH:
        wrapper = _StartGameCapture(enow)
        play_func = GAME_DISPATCH[name]
        if name == "rainbow":
            play_func(nfc, leds, buz, accel, i2c, wrapper, batt=batt_ref)
        else:
            play_func(nfc, leds, buz, accel, i2c, wrapper)
        next_name = wrapper.pending_name
        if not next_name or next_name not in GAME_DISPATCH:
            break
        name = next_name


def _clear_rules_state(enow):
    """Teardown shared with broadcast stop and start_game dispatch."""
    if enow and enow.is_active:
        enow.send_stop_all_peers()
        enow.clear_peers()


# ─────────────────────────────────────────────
# CHECK BROADCAST (used in multiple places)
# ─────────────────────────────────────────────
def check_broadcast(enow, batt_ref, leds_ref, buz_ref):
    """
    Poll ESP-NOW for broadcast stop/battery/start_game.
    Returns "stop", "battery", ("start_game", name), or None.
    """
    msg_type, data, mac_str = enow.poll()
    if msg_type == "stop":
        return "stop"
    if msg_type == "battery":
        show_battery(batt_ref, leds_ref, buz_ref)
        return "battery"
    if msg_type == "start_game":
        name = data.get("name") if isinstance(data, dict) else None
        if name in GAME_DISPATCH:
            return ("start_game", name)
        print("  ESP-NOW: ignoring unknown start_game name: %r" % name)
    return None


# ─────────────────────────────────────────────
# IDLE DISPLAY HELPER
# ─────────────────────────────────────────────
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
def run_event_loop(reader, rules, runner, accel_ref, enow=None, batt_ref=None):
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

        # ESP-NOW broadcast check
        if enow and enow.is_active:
            espnow_cnt += 1
            if espnow_cnt >= 5:
                espnow_cnt = 0
                result = check_broadcast(enow, batt_ref, leds, buz)
                if result == "stop":
                    return None
                if isinstance(result, tuple) and result[0] == "start_game":
                    return result[1]
                if result == "battery":
                    leds.show_running(rules)

        nfc_cnt += 1
        if nfc_cnt >= 15:
            nfc_cnt = 0
            try:
                cmd, _ = read_quiet(reader)
                if cmd == "stop":
                    return
            except Exception:
                pass

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
        leds.show_shape(SHAPE_X, RED)
        buz.beep(300, 200)
        time.sleep_ms(100)
        buz.beep(200, 300)
        time.sleep_ms(1200)
        leds.off()
        return

    n = pull_flag.bump()
    print("# pull mode: attempt %d/%d -- Ctrl-C within %ds to stay at the REPL"
          % (n, pull_flag.MAX_ATTEMPTS, PULL_GRACE_S))
    for remaining in range(PULL_GRACE_S, 0, -1):
        print("# %d..." % remaining)
        time.sleep_ms(1000)

    leds.fill(BLUE_DIM)
    buz.beep(880, 80)
    time.sleep_ms(50)
    buz.beep(1100, 80)

    import gc
    import code_puller
    print("# mem_free before pull: %d" % gc.mem_free())
    # enow is deliberately not passed: there is no ESP-NOW on this boot to
    # shut down, and omitting it keeps _shutdown_espnow() out of the path.
    ok = code_puller.pull(verbose=True, on_progress=_pull_progress)
    print("# mem_free after pull: %d" % gc.mem_free())

    if ok:
        pull_flag.clear()
        leds.show_shape(SHAPE_CHECK, GREEN)
        buz.beep(300, 200)
        time.sleep_ms(100)
        buz.beep(200, 300)
        time.sleep_ms(600)
        print("# pull OK -- resetting into the new game")
        machine.reset()

    # Failed. The flag stays set, so reset rather than falling through --
    # the retry needs a cold radio too, and this boot's is no longer clean.
    print("# pull failed -- resetting to retry (%d/%d spent)"
          % (n, pull_flag.MAX_ATTEMPTS))
    leds.show_shape(SHAPE_X, RED)
    buz.beep(300, 200)
    time.sleep_ms(800)
    machine.reset()


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    # Before anything else, and before ESP-NOW claims the radio.
    if pull_flag.is_pending():
        _run_pull_mode()

    _boot_grace()
    print("\n" + "=" * 50)
    print("  PlaygroundV5 -- Multi-Trigger Event Engine")
    print("  Hub type: %s" % HUB_TYPE)
    print("=" * 50)

    # NOTE: leds.boot_power() was already called at module level — LED 0 is dim white.
    # Turning it green here confirms that main() was reached and imports succeeded.
    # If an import fails before main() runs, LED 0 stays dim white permanently.
    leds.boot_stage_ok(0)

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

    reader = NfcReader(nfc, ALL_COMMANDS)
    runner = ActionRunner(leds, buz)

    # ESP-NOW init — no LED stage, not hardware on the wand itself
    enow = ESPNowManager()
    enow.init()
    if batt is not None:
        enow.set_status_provider(lambda b=batt: int(b.soc))

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

    print("  Boot complete — all systems OK")
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
                result = check_broadcast(enow, batt, leds, buz)
                if result == "stop":
                    _clear_rules_state(enow)
                    rules = {}; editing = None; pending_combinator = None
                    buz.stop()
                    nfc_sleeping = False
                    last_activity_ms = time.ticks_ms()
                    idle_frame = 0
                    show_idle(last_soc, 0)
                    print("  Reset via broadcast")
                elif isinstance(result, tuple) and result[0] == "start_game":
                    _, name = result
                    _clear_rules_state(enow)
                    rules = {}; editing = None; pending_combinator = None
                    buz.stop()
                    nfc_sleeping = False
                    leds.off()
                    _launch_game(name, nfc, leds, buz, accel, i2c, enow, batt)
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
                    except Exception:
                        pass

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
                        except Exception:
                            pass
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
                result = check_broadcast(enow, batt, leds, buz)
                if result == "stop":
                    _clear_rules_state(enow)
                    rules = {}; editing = None; pending_combinator = None
                    buz.stop()
                    last_activity_ms = time.ticks_ms()
                    idle_frame = 0
                    show_idle(last_soc, 0)
                    print("  Reset via broadcast")
                elif isinstance(result, tuple) and result[0] == "start_game":
                    _, name = result
                    _clear_rules_state(enow)
                    rules = {}; editing = None; pending_combinator = None
                    buz.stop()
                    leds.off()
                    _launch_game(name, nfc, leds, buz, accel, i2c, enow, batt)
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
            if cmd == "getcode":
                print("# getcode tapped -- queueing pull, rebooting")
                leds.fill(BLUE_DIM)
                buz.beep(880, 80)
                time.sleep_ms(50)
                buz.beep(1100, 80)
                try:
                    pull_flag.set_pending()
                except OSError as e:
                    # Flag unwritable (full/corrupt fs). Rebooting now would
                    # just come back to the idle loop having lost the tap, so
                    # report it instead.
                    print("# could not write pull flag: %s" % e)
                    leds.show_shape(SHAPE_X, RED)
                    buz.beep(300, 200)
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
                    except Exception:
                        pass
                last_activity_ms = time.ticks_ms()
                idle_frame = 0
                show_idle(last_soc, 0); continue

            # ── GAME DISPATCH ──
            if cmd in GAME_DISPATCH:
                leds.off()
                _launch_game(cmd, nfc, leds, buz, accel, i2c, enow, batt)
                last_activity_ms = time.ticks_ms()
                idle_frame = 0
                show_idle(last_soc, 0); last_uid = None; continue

            # ── STOP ──
            if cmd == "stop":
                _clear_rules_state(enow)
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
                    buz.beep(300, 200)
                    print("  Nothing to run")
                    show_idle(last_soc, 0); continue
                print("  ── RUNNING ──")
                leds.show_running(rules)
                buz.beep(800, 60); time.sleep_ms(30); buz.beep(1200, 80)
                start_game_name = run_event_loop(reader, rules, runner, accel, enow, batt)
                print("  ── STOPPED ──")
                rules = {}; editing = None; pending_combinator = None
                last_activity_ms = time.ticks_ms()
                idle_frame = 0
                if start_game_name:
                    _clear_rules_state(enow)
                    buz.stop()
                    leds.off()
                    _launch_game(start_game_name, nfc, leds, buz, accel, i2c, enow, batt)
                    last_uid = None
                show_idle(last_soc, 0)
                print_rules(rules, editing); continue

            # ── COMBINATOR ──
            if cmd in COMBINATORS:
                if editing is None:
                    buz.beep(300, 100)
                    print("  Combinator '%s' ignored — no active trigger" % cmd)
                else:
                    pending_combinator = cmd
                    print("  Combinator: %s (next action will %s)" % (cmd, "add to group" if cmd == "and" else "start new step"))
                    buz.beep(600, 40)
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

