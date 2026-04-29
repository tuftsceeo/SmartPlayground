"""
PlaygroundV5 – NFC Multi-Trigger Event Engine + Splat Companion
================================================================
Board: Seeed XIAO ESP32-C6
Requires hubtype.txt containing: wand

Triggers: buttondown, buttonup, shake, gesture:<n>, SC:<MAC>
Actions:  playnote, notea-g, turnred/green/blue/purple/yellow/white/off,
          cat, chicken, cow, dog, pig, duck, elephant, horse, goat
Combinators: and, then
Controls: start, stop, colorquest, freezedance
Utility: battery
"""

import machine
import time
import sys
import json

from hubtype import HUB_TYPE, HUB_CONFIG
from pn532 import PN532
from lis2dw12 import LIS2DW12, RANGE_4G
from max17048 import MAX17048
from gesture_engine import GestureEngine, CONFIDENCE_THRESHOLD

from leds import Leds, TRIGGER_ORDER
from buzzer import Buzzer
from nfc_reader import NfcReader
from actions import ActionRunner, ACTIONS, ANIMAL_SOUNDS, ACTION_RESOURCE, resolve_and_group, chain_to_str
from battery import show_battery
from espnow_manager import ESPNowManager
from color_quest import play as play_color_quest
from freeze_dance import play as play_freeze_dance
from jumpin import play as play_jumpin

# ─────────────────────────────────────────────
# PINS FROM HUBTYPE
# ─────────────────────────────────────────────
I2C_SDA      = HUB_CONFIG["i2c_sda"]
I2C_SCL      = HUB_CONFIG["i2c_scl"]
BUZZER_PIN   = HUB_CONFIG["buzzer_pin"]
MOTOR_PIN    = HUB_CONFIG["motor_pin"]
SWITCH_PIN   = HUB_CONFIG["button_pin"]
ACCEL_INT1   = HUB_CONFIG["accel_int1_pin"]
PN532_ADDR   = 0x24

# ─────────────────────────────────────────────
# TAG COMMANDS
# ─────────────────────────────────────────────
FIXED_TRIGGERS = {"buttondown", "buttonup", "shake"}
COMBINATORS    = {"and", "then"}
CONTROLS       = {"start", "stop", "colorquest", "freezedance", "jumpin"}
UTILITY        = {"battery"}
ALL_COMMANDS   = FIXED_TRIGGERS | ACTIONS | ANIMAL_SOUNDS | COMBINATORS | CONTROLS | UTILITY

# ─────────────────────────────────────────────
# NFC SLEEP TIMEOUT
# ─────────────────────────────────────────────
NFC_SLEEP_MS = 30_000  # 30 seconds of inactivity before NFC sleeps

# ─────────────────────────────────────────────
# HARDWARE (LEDs init FIRST for boot indicator)
# ─────────────────────────────────────────────
leds     = Leds()

# ── BOOT STEP 1: Power LED on immediately ──
leds.boot_power()

i2c      = machine.SoftI2C(sda=machine.Pin(I2C_SDA), scl=machine.Pin(I2C_SCL), freq=HUB_CONFIG["i2c_freq"])
buz      = Buzzer(BUZZER_PIN)
btn      = machine.Pin(SWITCH_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
int1_pin = machine.Pin(ACCEL_INT1, machine.Pin.IN)
motor    = machine.Pin(MOTOR_PIN, machine.Pin.OUT, value=0)

# ─────────────────────────────────────────────
# SC HELPERS
# ─────────────────────────────────────────────
def is_sc_trigger(name):
    return name is not None and name.startswith("SC:")

def parse_sc_mac(name):
    if not is_sc_trigger(name):
        return None
    return name[3:]

def is_gesture_trigger(name):
    return name is not None and name.startswith("gesture:")

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

    for trig in sorted(rules.keys()):
        if is_gesture_trigger(trig):
            gn = trig.split(":", 1)[1]
            marker = " *" if trig == editing else ""
            if len(rules[trig]) > 0:
                print("  | gesture:%s -> [%s]%s" % (gn, chain_to_str(rules[trig]), marker))
                has_any = True
            elif trig == editing:
                print("  | gesture:%s -> (awaiting actions)%s" % (gn, marker))

    if is_gesture_trigger(editing) and editing not in rules:
        print("  | %s -> (awaiting actions) *" % editing)

    for trig in sorted(rules.keys()):
        if is_sc_trigger(trig):
            marker = " *" if trig == editing else ""
            if len(rules[trig]) > 0:
                print("  | %s -> [%s]%s" % (trig, chain_to_str(rules[trig]), marker))
                has_any = True
            elif trig == editing:
                print("  | %s -> (awaiting actions)%s" % (trig, marker))

    if is_sc_trigger(editing) and editing not in rules:
        print("  | %s -> (awaiting actions) *" % editing)

    if not has_any and not editing:
        print("  | (empty -- tap a trigger tag)")
    print("  +----------------------------------------")


# ─────────────────────────────────────────────
# CHECK BROADCAST (used in multiple places)
# ─────────────────────────────────────────────
def check_broadcast(mgr, batt_ref, leds_ref, buz_ref):
    """
    Poll ESP-NOW for broadcast stop/battery.
    Returns "stop" if stop received, "battery" if battery shown, None otherwise.
    """
    msg_type, data, mac_str = mgr.poll()
    if msg_type == "stop":
        return "stop"
    if msg_type == "battery":
        show_battery(batt_ref, leds_ref, buz_ref)
        return "battery"
    return None


# ─────────────────────────────────────────────
# IDLE DISPLAY HELPER
# ─────────────────────────────────────────────
def show_idle(last_soc, idle_frame):
    """Show the correct idle display based on battery level."""
    if last_soc <= 10:
        leds.idle_low_blink(idle_frame)
    else:
        leds.idle_default(last_soc)


# ─────────────────────────────────────────────
# EVENT LOOP (RUNNING)
# ─────────────────────────────────────────────
def run_event_loop(reader, rules, runner, accel_ref, ge_ref, mgr=None, batt_ref=None):
    btn_was_down = (btn.value() == 0)
    if accel_ref and "shake" in rules:
        accel_ref.clear_wake()

    gesture_last_fire = 0
    g_map = {}
    for tk in rules:
        if is_gesture_trigger(tk) and len(rules[tk]) > 0:
            g_map[tk.split(":", 1)[1]] = tk
    has_g = len(g_map) > 0

    nfc_cnt = 0
    espnow_cnt = 0

    print("  Event loop active:")
    for trig in sorted(rules.keys()):
        if not is_sc_trigger(trig) and len(rules[trig]) > 0:
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

        if fired is None and accel_ref and "shake" in rules and len(rules["shake"]) > 0:
            if int1_pin.value() == 1:
                accel_ref.clear_wake(); time.sleep_ms(100); accel_ref.clear_wake()
                fired = "shake"

        if fired is None and ge_ref and has_g and ge_ref.loaded_gestures:
            now = time.ticks_ms()
            if time.ticks_diff(now, gesture_last_fire) > 800:
                if ge_ref.poll_motion():
                    name, conf, dist, ad = ge_ref.capture_and_classify()
                    if name is not None and conf >= CONFIDENCE_THRESHOLD:
                        tk = g_map.get(name)
                        if tk:
                            fired = tk
                    gesture_last_fire = time.ticks_ms()

        if fired:
            chain = rules[fired]
            print("  * %s -> [%s]" % (fired, chain_to_str(chain)))
            runner.run_chain(chain)

        # ESP-NOW broadcast check
        if mgr and mgr.is_active:
            espnow_cnt += 1
            if espnow_cnt >= 5:
                espnow_cnt = 0
                result = check_broadcast(mgr, batt_ref, leds, buz)
                if result == "stop":
                    return
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


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("\n" + "=" * 50)
    print("  PlaygroundV5 -- Multi-Trigger Event Engine")
    print("  Hub type: %s" % HUB_TYPE)
    print("=" * 50)

    # NOTE: leds.boot_power() already called at module level
    # LED 0 is already white — user sees instant power confirmation

    # ── BOOT STEP 2: Battery check ──
    batt = None
    last_soc = 100  # default if no battery gauge
    try:
        batt = MAX17048(i2c)
        v, s = batt.read_all()
        last_soc = max(0, min(100, int(s)))
        print("  Battery: %.2fV, %.1f%%" % (v, s))
    except Exception as e:
        print("  [WARN] Battery:"); sys.print_exception(e)

    # Show battery level on LEDs 0 + 1
    leds.boot_battery(last_soc)
    time.sleep_ms(300)  # brief pause so user sees the color

    # NFC
    nfc = PN532(i2c, PN532_ADDR)
    try:
        ic, ver, rev = nfc.begin()
        print("  PN5%02X fw %d.%d -- NFC ready" % (ic, ver, rev))
    except Exception as e:
        print("  [FAIL] NFC:"); sys.print_exception(e); return

    reader = NfcReader(nfc, ALL_COMMANDS)
    runner = ActionRunner(leds, buz)

    # ESP-NOW
    mgr = ESPNowManager()
    mgr.init()

    # ── Accelerometer (basic init only) ──
    # NOTE: enable_wake_int1() is called LATER, after the gesture engine,
    # because GestureEngine.init() does a soft-reset on the LIS2DW12 (writing
    # 0x40 to CTRL2), which clears CTRL4_INT1, CTRL7, and WAKE_UP_THS.
    # If we configure wake-up here, the gesture engine's reset wipes it out
    # and the shake trigger never fires (INT1 stays low forever).
    accel = None
    accel_ok = False
    try:
        accel = LIS2DW12(i2c)
        accel.init(fs_range=RANGE_4G)
        accel_ok = True
        print("  Accelerometer OK")
    except Exception as e:
        print("  [WARN] Accel:"); sys.print_exception(e)

    # Gesture engine (touches the same LIS2DW12 chip — soft-resets it!)
    ge = None
    ge_ok = False
    try:
        from neopixel import NeoPixel as NP
        ge_np = NP(machine.Pin(HUB_CONFIG["led_pin"]), HUB_CONFIG["num_leds"])
        ge = GestureEngine(i2c, ge_np, buzzer_pin=BUZZER_PIN)
        ge.init()
        ge_ok = True
        print("  Gesture engine OK")
    except Exception as e:
        print("  [WARN] Gesture engine:"); sys.print_exception(e)

    # ── Re-enable accel wake-up AFTER gesture engine has finished its soft-reset ──
    if accel_ok:
        try:
            accel.enable_wake_int1(threshold=8)
            print("  Accel wake-up (INT1) armed")
        except Exception as e:
            print("  [WARN] Accel wake:"); sys.print_exception(e)

    if ge_ok:
        reader.gesture_engine = ge

    # ── BOOT STEP 3: All init complete — LED 2 on ──
    leds.boot_ready(last_soc)
    print("  Boot complete — all systems OK")
    time.sleep_ms(800)  # hold boot display so user can read it

    # Transition to idle display
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
                leds.idle_sleep()  # static blue dot

                # Check ESP-NOW broadcasts while sleeping
                result = check_broadcast(mgr, batt, leds, buz)
                if result == "stop":
                    mgr.send_stop_all_peers(); mgr.clear_peers()
                    rules = {}; editing = None; pending_combinator = None
                    if ge: ge.clear_loaded()
                    buz.stop()
                    nfc_sleeping = False
                    last_activity_ms = time.ticks_ms()
                    idle_frame = 0
                    show_idle(last_soc, 0)
                    print("  Reset via broadcast")
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
                result = check_broadcast(mgr, batt, leds, buz)
                if result == "stop":
                    mgr.send_stop_all_peers(); mgr.clear_peers()
                    rules = {}; editing = None; pending_combinator = None
                    if ge: ge.clear_loaded()
                    buz.stop()
                    last_activity_ms = time.ticks_ms()
                    idle_frame = 0
                    show_idle(last_soc, 0)
                    print("  Reset via broadcast")
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

            # ── SC TAG ──
            is_sc_cmd = False
            if cmd.startswith("sc:") and len(cmd) > 3:
                cmd = "SC:" + cmd[3:].upper()
                is_sc_cmd = True

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

            # ── COLOR QUEST ──
            if cmd == "colorquest":
                leds.off()
                play_color_quest(nfc, leds.np, buz)
                last_activity_ms = time.ticks_ms()
                idle_frame = 0
                show_idle(last_soc, 0); last_uid = None; continue

            # ── FREEZE DANCE ──
            if cmd == "freezedance":
                leds.off()
                play_freeze_dance(nfc, leds, buz, accel, i2c)
                last_activity_ms = time.ticks_ms()
                idle_frame = 0
                show_idle(last_soc, 0); last_uid = None; continue

            # ── JUMP IN ──
            if cmd == "jumpin":
                leds.off()
                play_jumpin(nfc, leds, buz, accel, i2c)
                last_activity_ms = time.ticks_ms()
                idle_frame = 0
                show_idle(last_soc, 0); last_uid = None; continue

            # ── STOP ──
            if cmd == "stop":
                if mgr and mgr.is_active:
                    mgr.send_stop_all_peers(); mgr.clear_peers()
                rules = {}; editing = None; pending_combinator = None
                if ge: ge.clear_loaded()
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
                run_event_loop(reader, rules, runner, accel, ge, mgr, batt)
                print("  ── STOPPED ──")
                rules = {}; editing = None; pending_combinator = None
                if ge: ge.clear_loaded()
                last_activity_ms = time.ticks_ms()
                idle_frame = 0
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
            if cmd in FIXED_TRIGGERS or is_gesture_trigger(cmd) or is_sc_cmd:
                trig_key = cmd
                if is_gesture_trigger(cmd):
                    gname = cmd.split(":", 1)[1]
                    if ge and ge_ok:
                        if gname not in [g[0] for g in (ge.loaded_gestures or [])]:
                            ge.load_gesture(gname)
                    trig_key = cmd

                if trig_key not in rules:
                    rules[trig_key] = []
                editing = trig_key
                pending_combinator = None
                print("  Editing trigger: %s" % trig_key)
                leds.show_programming(rules, editing)
                print_rules(rules, editing); continue

            # ── ACTION ──
            # Chain shape contract: list[list[str]] — outer list is THEN-groups,
            # inner list is AND-group of simultaneous actions.
            # ActionRunner.run_chain expects: [["turnred", "notea"], ["playnote"]]
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
                    # Start a new group — must be a LIST, not a bare string
                    chain.append([cmd])
                else:
                    # Replace chain with a single-action single-group
                    rules[editing] = [[cmd]]

                pending_combinator = None

                # Preview the action — wrap as list-of-groups for run_chain
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


main()
