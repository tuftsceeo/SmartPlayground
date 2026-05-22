"""
ARCHIVED: January 2026 wand-side code, originally at Wand Module/sp_loop.py.
Not currently used in production.

sp_loop.py — BLE-Primary Running Loop (v4)
=============================================
Split from the working unified main.py.
"""

_VERSION = "v4"

import time
from gesture_engine import CONFIDENCE_THRESHOLD
from actions import chain_to_str
from ble_splat_ctrl import (
    is_sp_trigger, sp_keepalive_all,
    sp_process_pending_all, espnow_quick_check,
)


def is_gesture_trigger(name):
    return name is not None and name.startswith("gesture:")


def run_sp_loop(reader, leds, buz, btn, int1_pin,
                mgr, batt_ref,
                check_broadcast_fn, read_quiet_fn,
                local_rules=None, runner=None,
                accel_ref=None, ge_ref=None):
    last_ka = time.ticks_ms()
    last_espnow_check = time.ticks_ms()
    frame = 0

    has_local = local_rules is not None and len(local_rules) > 0
    btn_was_down = (btn.value() == 0)
    gesture_last_fire = 0
    g_map = {}
    if has_local:
        if accel_ref and "shake" in local_rules: accel_ref.clear_wake()
        for tk in local_rules:
            if is_gesture_trigger(tk) and len(local_rules[tk]) > 0:
                g_map[tk.split(":", 1)[1]] = tk
    has_g = len(g_map) > 0
    nfc_cnt = 0

    while True:
        try:
            now = time.ticks_ms()

            if time.ticks_diff(now, last_ka) >= 2500:
                sp_keepalive_all(); last_ka = now

            sp_process_pending_all()

            if has_local:
                fired = None; btn_down = (btn.value() == 0)
                if btn_down and not btn_was_down:
                    time.sleep_ms(30)
                    if btn.value() == 0:
                        if "buttondown" in local_rules and len(local_rules["buttondown"]) > 0:
                            fired = "buttondown"
                elif not btn_down and btn_was_down:
                    time.sleep_ms(30)
                    if btn.value() == 1:
                        if "buttonup" in local_rules and len(local_rules["buttonup"]) > 0:
                            fired = "buttonup"
                btn_was_down = btn_down
                if fired is None and accel_ref and "shake" in local_rules and len(local_rules["shake"]) > 0:
                    if int1_pin.value() == 1:
                        accel_ref.clear_wake(); time.sleep_ms(100); accel_ref.clear_wake()
                        fired = "shake"
                if fired is None and ge_ref and has_g and ge_ref.loaded_gestures:
                    if time.ticks_diff(now, gesture_last_fire) > 800:
                        if ge_ref.poll_motion():
                            name, conf, dist, ad = ge_ref.capture_and_classify()
                            if name is not None and conf >= CONFIDENCE_THRESHOLD:
                                tk = g_map.get(name)
                                if tk: fired = tk; gesture_last_fire = now
                if fired and runner:
                    chain = local_rules.get(fired, [])
                    if chain:
                        print("  FIRE: %s -> [%s]" % (fired, chain_to_str(chain)))
                        runner.run_chain(chain)

            nfc_cnt += 1
            if nfc_cnt >= 5:
                nfc_cnt = 0
                c2, _ = read_quiet_fn(reader)
                if c2 == "stop":
                    print("  STOP tag scanned"); return

            if time.ticks_diff(now, last_espnow_check) >= 3000:
                last_espnow_check = now
                r2 = espnow_quick_check(mgr, check_broadcast_fn, batt_ref, leds, buz)
                if r2 == "stop":
                    print("  Stop via broadcast"); return

            if not has_local and frame % 3 == 0:
                leds.breathe(15, 0, 15, frame)
            frame += 1
            time.sleep_ms(40)
        except KeyboardInterrupt: return
        except Exception as e:
            print("  [ERR] SP loop: %s" % str(e)); time.sleep_ms(500)


print("[sp_loop %s loaded]" % _VERSION)
