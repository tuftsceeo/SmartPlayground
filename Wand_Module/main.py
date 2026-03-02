"""
PlaygroundV5 – NFC Multi-Trigger Event Engine
==============================================
Board: Seeed XIAO ESP32-C6

Program multiple trigger→action rules by tapping NFC tags,
then START to run them all simultaneously as an event loop.

Triggers: buttondown, buttonup, shake
Actions:  playnote, notea-g, turnred/green/blue/purple/yellow/white/off
Combinators: and (simultaneous), then (sequential)
Controls: start, stop
Utility: battery

Requires in /lib/:
    pn532.py, lis2dw12.py, max17048.py, opt3002.py,
    leds.py, buzzer.py, nfc_reader.py, actions.py, battery.py
"""

import machine
import time
import sys

from pn532 import PN532
from lis2dw12 import LIS2DW12, RANGE_4G
from max17048 import MAX17048

from leds import Leds, TRIGGER_ORDER
from buzzer import Buzzer
from nfc_reader import NfcReader
from actions import ActionRunner, ACTIONS, ACTION_RESOURCE, resolve_and_group, chain_to_str
from battery import show_battery

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
TRIGGERS    = {"buttondown", "buttonup", "shake"}
COMBINATORS = {"and", "then"}
CONTROLS    = {"start", "stop"}
UTILITY     = {"battery"}
ALL_COMMANDS = TRIGGERS | ACTIONS | COMBINATORS | CONTROLS | UTILITY

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
    """Called when tag is first detected, before data read."""
    pass  # animation starts on first progress call

def on_scan_progress(frame):
    """Called during data read — drives scanning animation."""
    leds.scan_animate(frame)

def on_scan_complete(command):
    """Called when scan finishes — flash, ding, haptic."""
    leds.scan_complete()
    if command:
        buz.beep(1200, 50)
        motor.value(1)
        time.sleep_ms(60)
        motor.value(0)
    else:
        # Tag found but no recognized command
        buz.beep(400, 80)


def read_with_feedback(reader):
    """Read a tag with scanning animation + completion feedback."""
    return reader.read_command(
        on_detect=on_tag_detect,
        on_progress=on_scan_progress,
        on_complete=on_scan_complete,
    )


def read_quiet(reader):
    """Read a tag with no animation (for event loop STOP polling)."""
    return reader.read_command()


# ─────────────────────────────────────────────
# PRINT HELPERS
# ─────────────────────────────────────────────

def print_rules(rules, editing):
    print("  ┌─ Rules ────────────────────────────")
    for trig in TRIGGER_ORDER:
        marker = " *" if trig == editing else ""
        if trig in rules and len(rules[trig]) > 0:
            print("  │ %s -> [%s]%s" % (trig, chain_to_str(rules[trig]), marker))
        elif trig == editing:
            print("  │ %s -> (awaiting actions)%s" % (trig, marker))
    if not any(rules.get(t) for t in TRIGGER_ORDER):
        print("  │ (empty — tap a trigger tag to begin)")
    print("  └────────────────────────────────────")


# ─────────────────────────────────────────────
# EVENT LOOP (RUNNING PHASE)
# ─────────────────────────────────────────────

def run_event_loop(reader, rules, runner, accel_ref):
    """
    Poll all trigger sources in a single loop.
    Fire action chains when triggers activate.
    Returns when a STOP tag is scanned.
    """
    btn_was_down = (btn.value() == 0)

    if accel_ref and "shake" in rules:
        accel_ref.clear_wake()

    nfc_poll_counter = 0

    print("  Event loop active — listening for:")
    for trig in TRIGGER_ORDER:
        if trig in rules and len(rules[trig]) > 0:
            print("    %s -> [%s]" % (trig, chain_to_str(rules[trig])))

    while True:
        fired_trigger = None

        # ── Button edge detection ──
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

        # ── Shake detection ──
        if (fired_trigger is None and accel_ref
                and "shake" in rules and len(rules["shake"]) > 0):
            if int1_pin.value() == 1:
                accel_ref.clear_wake()
                time.sleep_ms(100)
                accel_ref.clear_wake()
                fired_trigger = "shake"

        # ── Fire action chain ──
        if fired_trigger:
            chain = rules[fired_trigger]
            print("  * %s -> [%s]" % (fired_trigger, chain_to_str(chain)))
            runner.run_chain(chain)

        # ── Poll NFC for STOP tag ──
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
    print("  PlaygroundV5 — Multi-Trigger Event Engine")
    print("  Triggers: buttondown, buttonup, shake")
    print("  Tap START to run all rules simultaneously")
    print("=" * 50)

    # NFC
    nfc = PN532(i2c, PN532_ADDR)
    try:
        ic, ver, rev = nfc.begin()
        print("  PN5%02X fw %d.%d — NFC ready" % (ic, ver, rev))
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
    print("\n  Tap a TRIGGER tag to start programming a rule\n")

    while True:
        try:
            # Quick detect — no animation yet
            uid_peek, sak_peek = reader.detect_tag()

            if uid_peek is None:
                if last_uid is not None:
                    last_uid = None  # tag removed, allow re-read
                time.sleep_ms(200)
                continue

            # Same tag still on reader — skip
            if uid_peek == last_uid:
                time.sleep_ms(200)
                continue

            # New tag! Do the full animated read
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

            print("  >> %s" % cmd)

            # ── TRIGGER TAG ──
            if cmd in TRIGGERS:
                if cmd == "shake" and not accel_ok:
                    print("  [SKIP] Accelerometer not available!")
                    buz.warn(); continue

                if cmd == editing:
                    rules.pop(cmd, None)
                    pending_combinator = None
                    print("  Cleared %s rule — tap actions" % cmd)
                else:
                    editing = cmd
                    pending_combinator = None
                    if cmd in rules:
                        print("  Switching to %s (tap action to replace)" % cmd)
                    else:
                        print("  New rule: %s — tap action tags" % cmd)

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
                    print("  > AND — tap next action (simultaneous)")

            elif cmd == "then":
                if editing is None or editing not in rules or len(rules[editing]) == 0:
                    print("  [SKIP] Tap a trigger then an action first")
                    buz.beep(200, 150)
                else:
                    pending_combinator = "then"
                    buz.beep(400, 60); time.sleep_ms(50); buz.beep(600, 60)
                    print("  > THEN — tap next action (sequential)")

            # ── START ──
            elif cmd == "start":
                if pending_combinator:
                    print("  [SKIP] Finish %s first — tap an action" % pending_combinator)
                    buz.beep(200, 150); continue

                active_rules = {t: c for t, c in rules.items() if c and len(c) > 0}
                if not active_rules:
                    print("  [SKIP] No complete rules!")
                    buz.reject(); continue

                leds.off()
                buz.start()
                leds.flash(0, 40, 0, times=3, on_ms=80, off_ms=60)
                leds.show_running(active_rules)

                print("\n  >>> RUNNING %d rule(s) — tap STOP to end\n" % len(active_rules))

                run_event_loop(reader, active_rules, runner, accel)

                # Returned = STOP was tapped
                rules = {}
                editing = None
                pending_combinator = None
                last_uid = None
                leds.off(); buz.stop()
                leds.show_programming(rules, editing)
                print("  <<< STOPPED — all rules cleared")
                print("\n  Tap a TRIGGER tag to start programming\n")

            # ── STOP (during programming = reset) ──
            elif cmd == "stop":
                rules = {}
                editing = None
                pending_combinator = None
                buz.stop()
                leds.show_programming(rules, editing)
                print("  Reset — tap a TRIGGER tag to start programming")

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