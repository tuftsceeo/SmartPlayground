"""
PlaygroundV5 – NFC Multi-Trigger Event Engine + Color Quest
=============================================================
Board: Seeed XIAO ESP32-C6

Program multiple trigger->action rules by tapping NFC tags,
then START to run them all simultaneously as an event loop.
Tap COLORQUEST to enter the Color Quest scavenger hunt game.

Triggers: buttondown, buttonup, shake, gesture:<name>
Actions:  playnote, notea-g, turnred/green/blue/purple/yellow/white/off
Combinators: and (simultaneous), then (sequential)
Controls: start, stop, colorquest
Utility: battery

Requires in /lib/:
    pn532.py, lis2dw12.py, max17048.py, opt3002.py,
    leds.py, buzzer.py, nfc_reader.py, actions.py,
    battery.py, gesture_engine.py
Requires in /:
    color_quest.py
"""

import machine
import time
import sys

from pn532 import PN532
from lis2dw12 import LIS2DW12, RANGE_4G
from max17048 import MAX17048
from gesture_engine import GestureEngine, CONFIDENCE_THRESHOLD

from leds import Leds, TRIGGER_ORDER
from buzzer import Buzzer
from nfc_reader import NfcReader
from actions import ActionRunner, ACTIONS, ACTION_RESOURCE, resolve_and_group, chain_to_str
from battery import show_battery
from color_quest import play as play_color_quest

# ─────────────────────────────────────────────
# PIN CONSTANTS
# ─────────────────────────────────────────────
I2C_SDA      = 22
I2C_SCL      = 23
NEOPIXEL_PIN = 20
NUM_LEDS     = 25
BUZZER_PIN   = 19
MOTOR_PIN    = 21
SWITCH_PIN   = 0
ACCEL_INT1   = 1
PN532_ADDR   = 0x24

# ─────────────────────────────────────────────
# TAG COMMANDS
# ─────────────────────────────────────────────
FIXED_TRIGGERS = {"buttondown", "buttonup", "shake"}
COMBINATORS    = {"and", "then"}
CONTROLS       = {"start", "stop", "colorquest"}
UTILITY        = {"battery"}
ALL_COMMANDS   = FIXED_TRIGGERS | ACTIONS | COMBINATORS | CONTROLS | UTILITY

# ─────────────────────────────────────────────
# HARDWARE INIT
# ─────────────────────────────────────────────
i2c  = machine.SoftI2C(sda=machine.Pin(I2C_SDA), scl=machine.Pin(I2C_SCL), freq=100_000)
leds = Leds(NEOPIXEL_PIN, NUM_LEDS)
buz  = Buzzer(BUZZER_PIN)
btn  = machine.Pin(SWITCH_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
int1_pin = machine.Pin(ACCEL_INT1, machine.Pin.IN)
motor = machine.Pin(MOTOR_PIN, machine.Pin.OUT, value=0)


# ─────────────────────────────────────────────
# SCAN FEEDBACK CALLBACKS
# ─────────────────────────────────────────────

def on_tag_detect(uid_hex, sak):
    pass

def on_scan_progress(frame):
    leds.scan_animate(frame)

def on_scan_complete(command):
    leds.scan_complete()
    if command:
        buz.beep(1200, 50)
        motor.value(1)
        time.sleep_ms(60)
        motor.value(0)
    else:
        buz.beep(400, 80)


def read_with_feedback(reader):
    return reader.read_command(
        on_detect=on_tag_detect,
        on_progress=on_scan_progress,
        on_complete=on_scan_complete,
    )


def read_quiet(reader):
    return reader.read_command()


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def is_gesture_trigger(name):
    return name is not None and name.startswith("gesture:")

def gesture_triggers_in(rules):
    return [k for k in rules if is_gesture_trigger(k) and len(rules[k]) > 0]


# ─────────────────────────────────────────────
# PRINT HELPERS
# ─────────────────────────────────────────────

def print_rules(rules, editing):
    print("  +- Rules --------------------------------")
    has_any = False

    for trig in TRIGGER_ORDER:
        if trig == "gesture":
            continue
        marker = " *" if trig == editing else ""
        if trig in rules and len(rules[trig]) > 0:
            print("  | %s -> [%s]%s" % (trig, chain_to_str(rules[trig]), marker))
            has_any = True
        elif trig == editing:
            print("  | %s -> (awaiting actions)%s" % (trig, marker))

    for trig in sorted(rules.keys()):
        if not is_gesture_trigger(trig):
            continue
        gname = trig.split(":", 1)[1]
        marker = " *" if trig == editing else ""
        if len(rules[trig]) > 0:
            print("  | gesture:%s -> [%s]%s" % (gname, chain_to_str(rules[trig]), marker))
            has_any = True
        elif trig == editing:
            print("  | gesture:%s -> (awaiting actions)%s" % (gname, marker))

    if is_gesture_trigger(editing) and editing not in rules:
        gname = editing.split(":", 1)[1]
        print("  | gesture:%s -> (awaiting actions) *" % gname)

    if not has_any and not editing:
        print("  | (empty -- tap a trigger tag to begin)")
    print("  +----------------------------------------")


# ─────────────────────────────────────────────
# EVENT LOOP (RUNNING PHASE)
# ─────────────────────────────────────────────

def run_event_loop(reader, rules, runner, accel_ref, ge_ref):
    btn_was_down = (btn.value() == 0)

    if accel_ref and "shake" in rules:
        accel_ref.clear_wake()

    gesture_last_fire = 0

    gesture_name_to_trigger = {}
    for trig_key in rules:
        if is_gesture_trigger(trig_key) and len(rules[trig_key]) > 0:
            gname = trig_key.split(":", 1)[1]
            gesture_name_to_trigger[gname] = trig_key

    has_gesture_rules = len(gesture_name_to_trigger) > 0

    nfc_poll_counter = 0

    print("  Event loop active -- listening for:")
    for trig in sorted(rules.keys()):
        if len(rules[trig]) > 0:
            print("    %s -> [%s]" % (trig, chain_to_str(rules[trig])))

    while True:
        fired_trigger = None

        btn_is_down = (btn.value() == 0)

        if btn_is_down and not btn_was_down:
            time.sleep_ms(30)
            if btn.value() == 0:
                if "buttondown" in rules and len(rules["buttondown"]) > 0:
                    fired_trigger = "buttondown"

        elif not btn_is_down and btn_was_down:
            time.sleep_ms(30)
            if btn.value() == 1:
                if "buttonup" in rules and len(rules["buttonup"]) > 0:
                    fired_trigger = "buttonup"

        btn_was_down = btn_is_down

        if (fired_trigger is None and accel_ref
                and "shake" in rules and len(rules["shake"]) > 0):
            if int1_pin.value() == 1:
                accel_ref.clear_wake()
                time.sleep_ms(100)
                accel_ref.clear_wake()
                fired_trigger = "shake"

        if (fired_trigger is None and ge_ref
                and has_gesture_rules and ge_ref.loaded_gestures):
            now = time.ticks_ms()
            if time.ticks_diff(now, gesture_last_fire) > 800:
                if ge_ref.poll_motion():
                    name, conf, dist, all_dists = ge_ref.capture_and_classify()

                    dist_parts = []
                    for gn in sorted(all_dists, key=lambda n: all_dists[n]):
                        marker = ">" if gn == name else " "
                        dist_parts.append("%s%s=%.2f" % (marker, gn, all_dists[gn]))
                    dist_str = "  ".join(dist_parts)

                    if name is not None and conf >= CONFIDENCE_THRESHOLD:
                        trig_key = gesture_name_to_trigger.get(name)
                        if trig_key:
                            print("  * %s %.0f%% [%s]" % (name, conf * 100, dist_str))
                            fired_trigger = trig_key
                    else:
                        reason = "conf" if dist <= 2.2 else "dist"
                        print("  . miss(%s) [%s]" % (reason, dist_str))
                    gesture_last_fire = time.ticks_ms()

        if fired_trigger:
            chain = rules[fired_trigger]
            print("  * %s -> [%s]" % (fired_trigger, chain_to_str(chain)))
            runner.run_chain(chain)

        nfc_poll_counter += 1
        if nfc_poll_counter >= 15:
            nfc_poll_counter = 0
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
    print("  Triggers: buttondown, buttonup, shake, gestures")
    print("  Tap COLORQUEST for scavenger hunt game")
    print("  Tap START to run all rules simultaneously")
    print("=" * 50)

    # NFC
    nfc = PN532(i2c, PN532_ADDR)
    try:
        ic, ver, rev = nfc.begin()
        print("  PN5%02X fw %d.%d -- NFC ready" % (ic, ver, rev))
    except Exception as e:
        print("  [FAIL] NFC:"); sys.print_exception(e); return

    reader = NfcReader(nfc, ALL_COMMANDS)
    runner = ActionRunner(leds, buz)

    # Accelerometer
    accel = None
    accel_ok = False
    try:
        accel = LIS2DW12(i2c)
        accel.init(fs_range=RANGE_4G)
        accel.enable_wake_int1(threshold=8)
        accel_ok = True
        print("  Accelerometer OK (INT1, threshold=0.5g)")
    except Exception as e:
        print("  [WARN] Accel:"); sys.print_exception(e)

    # Gesture engine
    ge = None
    ge_ok = False
    try:
        from neopixel import NeoPixel as NP
        ge_np = NP(machine.Pin(NEOPIXEL_PIN), NUM_LEDS)
        ge = GestureEngine(i2c, ge_np, buzzer_pin=BUZZER_PIN)
        ge.init()
        ge_ok = True
        print("  Gesture engine OK")
    except Exception as e:
        print("  [WARN] Gesture engine:"); sys.print_exception(e)

    if ge_ok:
        reader.gesture_engine = ge

    # Battery
    batt = None
    try:
        batt = MAX17048(i2c)
        v, s = batt.read_all()
        print("  Battery OK (%.2fV, %.1f%%)" % (v, s))
    except Exception as e:
        print("  [WARN] Battery:"); sys.print_exception(e)

    # ── State ──
    rules = {}
    editing = None
    pending_combinator = None
    last_uid = None

    leds.show_programming(rules, editing)
    print("\n  Tap a TRIGGER tag (or gesture tag) to start programming\n")

    while True:
        try:
            uid_peek, sak_peek = reader.detect_tag()

            if uid_peek is None:
                if last_uid is not None:
                    last_uid = None
                time.sleep_ms(200)
                continue

            if uid_peek == last_uid:
                time.sleep_ms(200)
                continue

            cmd, uid = read_with_feedback(reader)
            last_uid = uid

            if cmd is None:
                time.sleep_ms(200)
                continue

            # ── UTILITY ──
            if cmd == "battery":
                show_battery(batt, leds, buz)
                leds.show_programming(rules, editing)
                continue

            # ── COLOR QUEST ──
            if cmd == "colorquest":
                leds.off()
                print("\n  >>> ENTERING COLOR QUEST <<<\n")

                play_color_quest(nfc, leds.np, buz)

                # Returned — restore programming state
                leds.show_programming(rules, editing)
                last_uid = None
                print("  <<< BACK TO PROGRAMMING MODE >>>")
                print("  Tap a TRIGGER tag to continue\n")
                continue

            # ── GESTURE TAG ──
            if cmd.startswith("gesture:"):
                if not ge_ok:
                    print("  [SKIP] Gesture engine not available!")
                    buz.warn(); continue

                gesture_name = cmd.split(":", 1)[1]
                trigger_key = "gesture:%s" % gesture_name

                editing = trigger_key
                pending_combinator = None

                buz.confirm()
                print("  > Gesture trigger: '%s'" % gesture_name)
                loaded = [g['name'] for g in ge.loaded_gestures]
                print("  > All loaded: %s" % ", ".join(loaded))
                print("  > Tap ACTION tags for this gesture, or another gesture tag")
                print_rules(rules, editing)
                leds.show_programming(rules, editing)
                continue

            print("  >> %s" % cmd)

            # ── FIXED TRIGGER TAG ──
            if cmd in FIXED_TRIGGERS:
                if cmd == "shake" and not accel_ok:
                    print("  [SKIP] Accelerometer not available!")
                    buz.warn(); continue

                if cmd == editing:
                    rules.pop(cmd, None)
                    pending_combinator = None
                    print("  Cleared %s rule -- tap actions" % cmd)
                else:
                    editing = cmd
                    pending_combinator = None
                    if cmd in rules:
                        print("  Switching to %s (tap action to replace)" % cmd)
                    else:
                        print("  New rule: %s -- tap action tags" % cmd)

                editing = cmd
                buz.confirm()
                print_rules(rules, editing)
                leds.show_programming(rules, editing)

            # ── ACTION TAG ──
            elif cmd in ACTIONS:
                if editing is None:
                    print("  Tap a trigger tag first!")
                    buz.reject(); continue

                chain = rules.get(editing, [])

                if pending_combinator == "and" and len(chain) > 0:
                    chain[-1].append(cmd)
                    chain[-1] = resolve_and_group(chain[-1])
                elif pending_combinator == "then" and len(chain) > 0:
                    chain.append([cmd])
                elif len(chain) == 0:
                    chain = [[cmd]]
                else:
                    chain = [[cmd]]

                rules[editing] = chain
                pending_combinator = None
                buz.confirm()
                print_rules(rules, editing)
                leds.show_programming(rules, editing)

            # ── COMBINATORS ──
            elif cmd == "and":
                if editing is None or editing not in rules or len(rules[editing]) == 0:
                    print("  [SKIP] Tap a trigger then an action first")
                    buz.beep(200, 150)
                else:
                    pending_combinator = "and"
                    buz.beep(500, 40); time.sleep_ms(30); buz.beep(500, 40)
                    print("  > AND -- tap next action (simultaneous)")

            elif cmd == "then":
                if editing is None or editing not in rules or len(rules[editing]) == 0:
                    print("  [SKIP] Tap a trigger then an action first")
                    buz.beep(200, 150)
                else:
                    pending_combinator = "then"
                    buz.beep(400, 60); time.sleep_ms(50); buz.beep(600, 60)
                    print("  > THEN -- tap next action (sequential)")

            # ── START ──
            elif cmd == "start":
                if pending_combinator:
                    print("  [SKIP] Finish %s first -- tap an action" % pending_combinator)
                    buz.beep(200, 150); continue

                active_rules = {t: c for t, c in rules.items() if c and len(c) > 0}

                for trig_key in list(active_rules.keys()):
                    if is_gesture_trigger(trig_key):
                        gname = trig_key.split(":", 1)[1]
                        found = False
                        if ge:
                            for g in ge.loaded_gestures:
                                if g['name'] == gname:
                                    found = True
                                    break
                        if not found:
                            print("  [SKIP] Gesture '%s' not loaded!" % gname)
                            buz.reject(); continue

                if not active_rules:
                    print("  [SKIP] No complete rules!")
                    buz.reject(); continue

                leds.off()
                buz.start()
                leds.flash(0, 40, 0, times=3, on_ms=80, off_ms=60)
                leds.show_running(active_rules)

                print("\n  >>> RUNNING %d rule(s) -- tap STOP to end\n" % len(active_rules))

                run_event_loop(reader, active_rules, runner, accel, ge)

                rules = {}
                editing = None
                pending_combinator = None
                last_uid = None
                if ge:
                    ge.clear_loaded()
                leds.off(); buz.stop()
                leds.show_programming(rules, editing)
                print("  <<< STOPPED -- all rules cleared")
                print("\n  Tap a TRIGGER tag to start programming\n")

            # ── STOP (during programming = reset) ──
            elif cmd == "stop":
                rules = {}
                editing = None
                pending_combinator = None
                if ge:
                    ge.clear_loaded()
                buz.stop()
                leds.show_programming(rules, editing)
                print("  Reset -- tap a TRIGGER tag to start programming")

            else:
                print("  Unknown: %s" % cmd)
                buz.beep(200, 150)

        except KeyboardInterrupt:
            leds.off(); print("\n  Exiting."); break
        except Exception as e:
            print("  [ERR]:"); sys.print_exception(e)
            time.sleep_ms(500)


if __name__ == "__main__":
    main()