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
CONTROLS       = {"start", "stop", "colorquest", "freezedance"}
UTILITY        = {"battery"}
ALL_COMMANDS   = FIXED_TRIGGERS | ACTIONS | ANIMAL_SOUNDS | COMBINATORS | CONTROLS | UTILITY

# ─────────────────────────────────────────────
# HARDWARE
# ─────────────────────────────────────────────
i2c      = machine.SoftI2C(sda=machine.Pin(I2C_SDA), scl=machine.Pin(I2C_SCL), freq=HUB_CONFIG["i2c_freq"])
leds     = Leds()
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
    print("  +- Rules --------------------------------")
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

    # Accelerometer
    accel = None
    accel_ok = False
    try:
        accel = LIS2DW12(i2c)
        accel.init(fs_range=RANGE_4G)
        accel.enable_wake_int1(threshold=8)
        accel_ok = True
        print("  Accelerometer OK")
    except Exception as e:
        print("  [WARN] Accel:"); sys.print_exception(e)

    # Gesture engine
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

    if ge_ok:
        reader.gesture_engine = ge

    # Battery
    batt = None
    try:
        batt = MAX17048(i2c)
        v, s = batt.read_all()
        print("  Battery: %.2fV, %.1f%%" % (v, s))
    except Exception as e:
        print("  [WARN] Battery:"); sys.print_exception(e)

    # ── State ──
    rules = {}
    editing = None
    pending_combinator = None
    last_uid = None

    leds.show_programming(rules, editing)
    print("\n  Tap a TRIGGER tag to start programming\n")

    while True:
        try:
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
                    buz.stop(); leds.show_programming(rules, editing)
                    print("  Reset via broadcast")
                elif result == "battery":
                    leds.show_programming(rules, editing)
                time.sleep_ms(200)
                continue

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
                leds.show_programming(rules, editing); continue

            # ── COLOR QUEST ──
            if cmd == "colorquest":
                leds.off()
                play_color_quest(nfc, leds.np, buz)
                leds.show_programming(rules, editing); last_uid = None; continue

            # ── FREEZE DANCE ──
            if cmd == "freezedance":
                leds.off()
                play_freeze_dance(nfc, leds, buz, accel, i2c)
                leds.show_programming(rules, editing); last_uid = None; continue

            # ── GESTURE TAG ──
            if cmd.startswith("gesture:"):
                if not ge_ok:
                    buz.warn(); continue
                editing = cmd; pending_combinator = None
                buz.confirm()
                print_rules(rules, editing); leds.show_programming(rules, editing); continue

            # ── SC TAG ──
            if is_sc_cmd:
                sc_mac = parse_sc_mac(cmd)
                editing = cmd; pending_combinator = None
                mgr.add_peer(sc_mac)
                buz.confirm(); leds.flash(0, 15, 15, times=2, on_ms=80, off_ms=60)
                print("  > Splat Companion: %s" % sc_mac)
                print_rules(rules, editing); leds.show_programming(rules, editing); continue

            print("  >> %s" % cmd)

            # ── FIXED TRIGGER ──
            if cmd in FIXED_TRIGGERS:
                if cmd == "shake" and not accel_ok:
                    buz.warn(); continue
                editing = cmd; pending_combinator = None
                buz.confirm()
                print_rules(rules, editing); leds.show_programming(rules, editing)

            # ── ACTION ──
            elif cmd in ACTIONS or cmd in ANIMAL_SOUNDS:
                if editing is None:
                    buz.reject(); continue
                chain = rules.get(editing, [])
                if pending_combinator == "and" and len(chain) > 0:
                    chain[-1].append(cmd)
                    chain[-1] = resolve_and_group(chain[-1])
                    rules[editing] = chain; pending_combinator = None
                elif pending_combinator == "then" and len(chain) > 0:
                    chain.append([cmd])
                    rules[editing] = chain; pending_combinator = None
                else:
                    rules[editing] = [[cmd]]
                buz.confirm()
                print_rules(rules, editing); leds.show_programming(rules, editing)

            # ── COMBINATORS ──
            elif cmd == "and":
                if editing is None or editing not in rules or len(rules[editing]) == 0:
                    buz.beep(200, 150)
                else:
                    pending_combinator = "and"
                    buz.beep(500, 40); time.sleep_ms(30); buz.beep(500, 40)

            elif cmd == "then":
                if editing is None or editing not in rules or len(rules[editing]) == 0:
                    buz.beep(200, 150)
                else:
                    pending_combinator = "then"
                    buz.beep(400, 60); time.sleep_ms(50); buz.beep(600, 60)

            # ── START ──
            elif cmd == "start":
                if pending_combinator:
                    buz.beep(200, 150); continue

                active = {t: c for t, c in rules.items() if c and len(c) > 0}
                if not active:
                    buz.reject(); continue

                # Send configs to Splat Companions
                sc_rules = {}; local_rules = {}
                for tk, ch in active.items():
                    if is_sc_trigger(tk):
                        sc_rules[tk] = ch
                    else:
                        local_rules[tk] = ch

                for tk, ch in sc_rules.items():
                    sc_mac = parse_sc_mac(tk)
                    print("  Sending config to %s: [%s]" % (sc_mac, chain_to_str(ch)))
                    mgr.send_splat_config(sc_mac, ch)
                    time.sleep_ms(50)

                leds.off(); buz.start()
                leds.flash(0, 40, 0, times=3, on_ms=80, off_ms=60)
                if local_rules:
                    leds.show_running(local_rules)

                total = len(local_rules) + len(sc_rules)
                print("\n  >>> RUNNING %d rule(s) (%d local, %d remote)\n" % (total, len(local_rules), len(sc_rules)))

                if local_rules:
                    run_event_loop(reader, local_rules, runner, accel, ge, mgr=mgr, batt_ref=batt)
                else:
                    print("  (Only remote. Tap STOP to end)")
                    while True:
                        try:
                            c2, _ = read_quiet(reader)
                            if c2 == "stop": break
                        except Exception:
                            pass
                        r2 = check_broadcast(mgr, batt, leds, buz)
                        if r2 == "stop": break
                        time.sleep_ms(200)

                mgr.send_stop_all_peers()
                rules = {}; editing = None; pending_combinator = None; last_uid = None
                mgr.clear_peers()
                if ge: ge.clear_loaded()
                leds.off(); buz.stop(); leds.show_programming(rules, editing)
                print("  <<< STOPPED\n  Tap a TRIGGER tag to reprogram\n")

            # ── STOP ──
            elif cmd == "stop":
                mgr.send_stop_all_peers(); mgr.clear_peers()
                rules = {}; editing = None; pending_combinator = None
                if ge: ge.clear_loaded()
                buz.stop(); leds.show_programming(rules, editing)

            else:
                buz.beep(200, 150)

        except KeyboardInterrupt:
            mgr.shutdown(); leds.off(); break
        except Exception as e:
            print("  [ERR]:"); sys.print_exception(e)
            time.sleep_ms(500)


if __name__ == "__main__":
    main()