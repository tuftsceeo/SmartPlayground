# PlaygroundV5 Wand — API Reference for jumpin.py Code Generation
# ================================================================
# This file is the SOLE context for generating jumpin.py code.
# jumpin.py runs on a Seeed XIAO ESP32-C6 under MicroPython v1.27.0.
# It is called when a kid taps the "jumpin" NFC tag on their wand,
# and must exit cleanly when the "stop" tag is tapped.
#
# IMPORTANT: Do NOT use f-strings — they crash on this MicroPython build.
# Use % formatting only: "value = %d" % val

# ═══════════════════════════════════════════════════════════════════
# 1. HARDWARE OVERVIEW
# ═══════════════════════════════════════════════════════════════════
# Board:  Seeed XIAO ESP32-C6 (RISC-V 160MHz, 4MB flash, 512KB SRAM)
# Framework: MicroPython v1.27.0
# Logic: 3.3V
#
# GPIO Map:
#   GPIO0  (D0)  — Button (active LOW, internal pull-up)
#   GPIO1  (D1)  — Accelerometer INT1 (wake-up interrupt, confirmed working)
#   GPIO2  (D2)  — Accelerometer INT2 (routed but DOES NOT FIRE — do not use)
#   GPIO3        — WiFi enable (used for external antenna switching)
#   GPIO14       — Antenna config (used for external antenna switching)
#   GPIO19 (D8)  — Buzzer (piezo, PWM)
#   GPIO20 (D9)  — NeoPixel data (25× SK6812, GRB byte order)
#   GPIO21 (D3)  — Vibration motor (digital on/off or PWM)
#   GPIO22 (D4)  — I2C SDA (shared bus, 100kHz — PN532 needs slow bus)
#   GPIO23 (D5)  — I2C SCL
#
# I2C Devices (all on GPIO22/23 at 100kHz):
#   0x24 — PN532 NFC reader
#   0x19 — LIS2DW12 accelerometer (SDO/SA0=HIGH)
#   0x36 — MAX17048 battery fuel gauge
#   0x44 — OPT3002 ambient light sensor (no INT pin routed — polling only)
#
# LED Layout: 25 LEDs in a 5×5 grid:
#   [ 0  1  2  3  4]  row 0
#   [ 5  6  7  8  9]  row 1
#   [10 11 12 13 14]  row 2
#   [15 16 17 18 19]  row 3
#   [20 21 22 23 24]  row 4
#
# Pixel index = row * 5 + col.  Row 0 = top, Row 4 = bottom.
#
# Accelerometer Orientation (calibrated):
#   accel.read() -> (x, y, z) in g.
#   When a side faces UP, gravity reads ~-1g on that axis.
#
#   FACE   up -> -Z ~ -1.0g    (front of wand, where LEDs/NFC face)
#   BACK   up -> +Z ~ +1.0g    (back of wand)
#   LEFT   up -> +X ~ +1.0g
#   RIGHT  up -> -X ~ -1.0g
#   TOP    up -> +Y ~ +1.0g    (tip of the wand)
#   BOTTOM up -> -Y ~ -1.0g    (handle end)
#
#   Wand held upright (tip up, handle down):
#     Y ~ +1.0g (gravity through handle)
#     Tilt toward face  -> Z decreases (goes negative)
#     Tilt toward left  -> X increases (goes positive)
#     Tilt toward right -> X decreases (goes negative)
#     Tilt forward/back -> Z changes; tilt left/right -> X changes
#     Y drops from +1.0 as wand tilts away from vertical
#
# NeoPixel byte order is GRB but the Leds class accepts (R, G, B).
# When using raw np[i] = (g, r, b) directly, remember GRB order.
# The Leds helper methods (solid, flash, etc.) handle this correctly.
#
# Vibration Motor:
#   motor = machine.Pin(21, machine.Pin.OUT, value=0)
#   motor.value(1)  # vibrate on
#   motor.value(0)  # vibrate off
#   # Keep bursts short — draws significant current.
#   # For variable intensity, use PWM:
#   # motor_pwm = machine.PWM(machine.Pin(21)); motor_pwm.freq(1000); motor_pwm.duty_u16(32768)

# ═══════════════════════════════════════════════════════════════════
# 2. ENTRY POINT CONTRACT
# ═══════════════════════════════════════════════════════════════════
# main.py calls:
#   from jumpin import play as play_jumpin
#   play_jumpin(nfc, leds, buz, accel, i2c)
#
# def play(nfc, leds, buz, accel, i2c):
#     """
#     Args:
#         nfc   — PN532 driver instance (already initialized)
#         leds  — Leds instance (leds.np is the raw NeoPixel object)
#         buz   — Buzzer instance
#         accel — LIS2DW12 instance (already initialized at ±4g, 100Hz)
#         i2c   — machine.SoftI2C instance (for additional I2C sensors)
#
#     MUST:
#       - Poll NFC periodically for "stop" tag and return when detected
#       - Clean up LEDs (leds.off()) in a try/finally block
#       - Not block indefinitely — keep the main loop responsive
#     """

# ═══════════════════════════════════════════════════════════════════
# 3. AVAILABLE LIBRARIES AND THEIR APIs
# ═══════════════════════════════════════════════════════════════════

# ───────────────────────────────────────────────
# 3a. leds.py — from leds import Leds
# ───────────────────────────────────────────────
# leds = Leds()  (already passed into play())
#
# leds.np            — raw NeoPixel object; leds.np[i] = (r, g, b); leds.np.write()
# leds.num           — LED count (25 on wand)
# leds.off()         — all LEDs off
# leds.solid(r,g,b)  — fill all LEDs with color (0-255 per channel)
# leds.flash(r,g,b, times=2, on_ms=120, off_ms=80) — blocking flash
# leds.pulse_color(r,g,b, duration_ms=600)  — single sine pulse then off
# leds.breathe(r,g,b, frame)               — continuous breathing, call each frame
# leds.breathe_idle(frame)                  — soft purple-white idle glow (all LEDs)
# leds.breathe_sleep(frame)                 — dim single-pixel blue pulse (center LED only)
# leds.scan_animate(frame)                  — expanding ring animation
# leds.scan_complete()                      — brief bright flash
# leds.show_programming(rules, editing)     — status LEDs for programming state
# leds.show_running(rules)                  — status LEDs for running state
# leds.show_battery_level(soc)              — battery bar, returns (r,g,b,lit)
# leds.fade_out_battery(r,g,b,lit)          — smooth fadeout after battery display
#
# Common colors (R,G,B):
#   Red(127,0,0) Green(0,127,0) Blue(0,0,127) Purple(127,0,127)
#   Yellow(127,80,0) White(80,80,80)

# ───────────────────────────────────────────────
# 3b. buzzer.py — from buzzer import Buzzer, NOTE_FREQ
# ───────────────────────────────────────────────
# buz = Buzzer(pin=19)  (already passed into play())
#
# buz.beep(freq=1000, ms=100)    — single tone (blocking)
# buz.play_note(freq, ms=400)    — single note (blocking)
# buz.melody()                   — ascending C5-E5-G5-C6 (~800ms)
# buz.confirm()                  — two rising tones (tag accepted)
# buz.start()                    — three rising tones
# buz.stop()                     — descending tone
# buz.reject()                   — double low tone (invalid)
# buz.warn()                     — single low tone
#
# NOTE_FREQ dict:
#   notec=262, noted=294, notee=330, notef=349,
#   noteg=392, notea=440, noteb=494

# ───────────────────────────────────────────────
# 3c. pn532.py — from pn532 import PN532, MIFARE_AUTH_A, MIFARE_AUTH_B
# ───────────────────────────────────────────────
# nfc = PN532(i2c, addr=0x24)  (already passed into play())
#
# nfc.begin()                                — returns (ic, ver, rev)
# nfc.read_passive_target(timeout=500)       — returns dict or None
#   dict keys: uid (bytes), uid_hex (str), uid_len, atqa, sak
# nfc.mifare_auth_block(uid, block, key, type)  — returns True/False
#   uid: bytes (use tag['uid']); block: int; key: 6 bytes; type: MIFARE_AUTH_A or B
# nfc.mifare_read_block(block)               — returns 16 bytes
# nfc.ntag_read_page(page)                   — returns 4 bytes

# ───────────────────────────────────────────────
# 3d. nfc_reader.py — NFC tag reading helpers
# ───────────────────────────────────────────────
# from nfc_reader import NfcReader, _decode_ndef_text, COMMON_KEYS
# from pn532 import MIFARE_AUTH_A, MIFARE_AUTH_B
#
# COMMON_KEYS = [
#     b'\xFF\xFF\xFF\xFF\xFF\xFF',
#     b'\xD3\xF7\xD3\xF7\xD3\xF7',
#     b'\xA0\xA1\xA2\xA3\xA4\xA5',
#     b'\xB0\xB1\xB2\xB3\xB4\xB5',
#     b'\x00\x00\x00\x00\x00\x00',
# ]
#
# _decode_ndef_text(raw_bytes) — extracts text string from NDEF TLV data
#
# NfcReader(nfc, commands_set):
#   reader.detect_tag(timeout=250)   — returns (uid_hex, sak) or (None, None)
#   reader.read_command(timeout=250) — returns (command_str, uid_hex)
#
# PROVEN PATTERN for reading tags inside a game (used by color_quest,
# freeze_dance, and jumpin.py). Copy this exactly:
#
# def _read_tag_text(nfc):
#     """Quick NDEF text read. Returns (text, uid_hex) or (None, None)."""
#     tag = nfc.read_passive_target(timeout=200)
#     if tag is None:
#         return None, None
#     uid_bytes = tag['uid']
#     uid_hex = tag['uid_hex']
#     if tag['sak'] not in (0x08, 0x18):
#         return None, uid_hex
#     raw = bytearray()
#     for sector_start in (4, 8):  # sectors 1 and 2
#         authed = False
#         for key in COMMON_KEYS:
#             for auth_type in (MIFARE_AUTH_A, MIFARE_AUTH_B):
#                 resel = nfc.read_passive_target(timeout=150)
#                 if resel is None:
#                     continue
#                 if nfc.mifare_auth_block(resel['uid'], sector_start, key, auth_type):
#                     for blk in range(sector_start, sector_start + 3):
#                         try:
#                             raw.extend(nfc.mifare_read_block(blk))
#                         except Exception:
#                             raw.extend(b'\x00' * 16)
#                     authed = True; break
#             if authed: break
#         if not authed:
#             raw.extend(b'\x00' * 48)
#     if not raw:
#         return None, uid_hex
#     text = _decode_ndef_text(bytes(raw))
#     return text.lower().strip() if text else None, uid_hex

# ───────────────────────────────────────────────
# 3e. lis2dw12.py — from lis2dw12 import LIS2DW12, RANGE_4G
# ───────────────────────────────────────────────
# accel = LIS2DW12(i2c, addr=0x19)  (already passed into play())
#
# accel.read()                     — returns (x, y, z) in g units (float)
#   NOTE: The method is accel.read(), NOT accel.read_accel().
#   At rest on a table: approx (0, 0, ±1.0) due to gravity.
#   Typical shake magnitude: sum of abs(x)+abs(y)+abs(z) > 1.4
# accel.enable_wake_int1(threshold=8)  — route shake detect to INT1
# accel.clear_wake()               — clear interrupt, returns WAKE_UP_SRC
# accel.data_ready                 — bool property
# accel.device_id                  — should be 0x44
#
# Ranges: RANGE_2G, RANGE_4G, RANGE_8G, RANGE_16G
# Wake threshold: at ±4g, 1 LSB=0.0625g. threshold=8→0.5g, 12→0.75g, 16→1.0g
# Sensor runs at 100Hz in high-performance mode.

# ───────────────────────────────────────────────
# 3f. max17048.py — from max17048 import MAX17048
# ───────────────────────────────────────────────
# batt = MAX17048(i2c, addr=0x36)
#
# batt.voltage       — volts (float)
# batt.soc           — state of charge 0-100+ (float)
# batt.read_all()    — returns (voltage, soc)
# No init needed — auto-starts when battery connected.

# ───────────────────────────────────────────────
# 3g. opt3002.py — from opt3002 import OPT3002, MODE_CONTINUOUS_100MS
# ───────────────────────────────────────────────
# light = OPT3002(i2c, addr=0x44)
#
# light.init(mode=MODE_CONTINUOUS_100MS)
# light.lux                  — ambient light in lux (float)
# light.read_single()        — one-shot 800ms measurement
# light.conversion_ready     — bool
# light.shutdown()
# Modes: MODE_CONTINUOUS_100MS, MODE_CONTINUOUS_800MS, MODE_SINGLE_800MS
# NOTE: INT pin is NOT routed — use polling only.

# ───────────────────────────────────────────────
# 3h. espnow_manager.py — from espnow_manager import ESPNowManager
# ───────────────────────────────────────────────
# mgr = ESPNowManager()
# mgr.init()   # handles external antenna config automatically
#
# mgr.broadcast(data)                — sends JSON to all (data=list/dict/str)
# mgr.send_to(mac_str, data)         — send to specific peer
# mgr.send_raw(mac_bytes, raw_bytes) — send raw bytes
# mgr.add_peer(mac_str)
# mgr.remove_peer(mac_str)
# mgr.clear_peers()
# mgr.has_peers()                    — bool
# mgr.poll(timeout_ms=0)             — returns (msg_type, data, mac_str)
#   msg_type: "colors", "score", "stop", "battery", "splat_config", "raw", or None
# mgr.send_score(mac_bytes, colors, elapsed_ms)
# mgr.broadcast_stop()
# mgr.shutdown()
# mgr.drain()                        — discard all pending messages
#
# Helpers: from espnow_manager import mac_str_to_bytes, mac_bytes_to_str, get_own_mac
#
# Or use raw espnow directly (must configure antenna first):
#   from machine import Pin
#   Pin(3, Pin.OUT).value(0); time.sleep_ms(100); Pin(14, Pin.OUT).value(1)  # ext antenna
#   import network, espnow
#   sta = network.WLAN(network.STA_IF); sta.active(True); sta.disconnect()
#   e = espnow.ESPNow(); e.active(True)
#   e.add_peer(b'\xFF\xFF\xFF\xFF\xFF\xFF')  # broadcast
#   e.send(b'\xFF\xFF\xFF\xFF\xFF\xFF', b"message")
#   mac, msg = e.irecv(timeout_ms)  # non-blocking if 0

# ───────────────────────────────────────────────
# 3i. actions.py — from actions import ActionRunner, ACTIONS, ANIMAL_SOUNDS
# ───────────────────────────────────────────────
# runner = ActionRunner(leds, buzzer)
# runner.run_action("turnred")        — single action
# runner.run_and_group(["turnred", "notea"])  — simultaneous (threaded)
# runner.run_chain([["turnred","notea"],["playnote"]])  — sequential groups
#
# ACTIONS = {"playnote","turnpurple","turnred","turnblue","turngreen",
#            "turnwhite","turnyellow","turnoff","notea".."noteg"}
# ANIMAL_SOUNDS = {"cat","chicken","cow","dog","pig","duck","elephant","horse","goat"}
# ALL_ACTIONS = ACTIONS | ANIMAL_SOUNDS
# ACTION_RESOURCE = { "playnote":"buzzer", "notea":"buzzer", ..., "turnred":"led", ... }
# resolve_and_group(group) — dedup by resource, returns list
# chain_to_str(chain) — human-readable chain string

# ───────────────────────────────────────────────
# 3j. battery.py — from battery import show_battery
# ───────────────────────────────────────────────
# show_battery(batt, leds, buzzer)  — display battery level on LEDs for 2.5s

# ───────────────────────────────────────────────
# 3k. hubtype.py — from hubtype import HUB_TYPE, HUB_CONFIG
# ───────────────────────────────────────────────
# HUB_TYPE = "wand"
# HUB_CONFIG = {
#   "num_leds": 25, "led_pin": 20, "has_nfc": True, "has_accel": True,
#   "has_battery": True, "has_buzzer": True, "has_motor": True,
#   "has_button": True, "buzzer_pin": 19, "motor_pin": 21,
#   "button_pin": 0, "accel_int1_pin": 1,
#   "i2c_sda": 22, "i2c_scl": 23, "i2c_freq": 100000,
# }

# ───────────────────────────────────────────────
# 3l. gesture_engine.py — from gesture_engine import GestureEngine
# ───────────────────────────────────────────────
# ge = GestureEngine(i2c, neopixel_obj, buzzer_pin=19, accel_addr=0x19, num_leds=25)
# ge.init()
# ge.loaded_gestures      — list of loaded gesture dicts [{name, centroid}, ...]
# ge.last_gesture_name    — name of last recognized gesture
# ge.poll_motion()        — non-blocking: True if motion exceeds threshold NOW
# ge.capture_and_classify() — blocking (~1.5s): returns (name, conf, dist, all_dists)
# ge.capture_gesture()    — blocking: returns 17-float feature vector or None
# ge.classify(fv)         — returns (name, confidence, distance)
# ge.load_gesture(name, centroid)
# ge.clear_loaded()
# ge.extract_features(samples) — [(x,y,z),...] → 17-float vector
# CONFIDENCE_THRESHOLD = 0.60

# ───────────────────────────────────────────────
# 3m. target.py — from target import SCORE_MAC
# ───────────────────────────────────────────────
# SCORE_MAC = b'\xB4\x3A\x45\x86\x1A\x5C'  # scoreboard MAC for sending scores
# Usage: mgr.send_score(SCORE_MAC, colors_list, elapsed_ms)

# ═══════════════════════════════════════════════════════════════════
# 4. ECOSYSTEM: OTHER ESP-NOW DEVICES jumpin.py CAN TALK TO
# ═══════════════════════════════════════════════════════════════════
#
# Speaker (standalone I2S WAV player on ESP32-C6):
#   Listens for ESP-NOW broadcasts. Responds to:
#     "FD_GO"     → start/resume playing audio
#     "FD_FREEZE" → pause audio
#     "stop"      → stop audio
#   Plays songN.wav files from SD card in a loop.
#
# DialSpeaker (M5Stack Dial with AudioPlayer Unit):
#   Same ESP-NOW commands as Speaker: FD_GO, FD_FREEZE, stop
#   Has a song browser — user selects a song on the dial first.
#
# Slide Score Station (40-LED serpentine bar graph):
#   Receives score messages: mgr.send_score(SCORE_MAC, colors, elapsed_ms)
#   Receives color broadcasts: mgr.broadcast(["turnred","turnblue",...])
#   Receives stop: mgr.broadcast_stop()
#
# To control music from jumpin.py (e.g. musical chairs game):
#   import network, espnow
#   from machine import Pin
#   Pin(3, Pin.OUT).value(0); time.sleep_ms(100); Pin(14, Pin.OUT).value(1)
#   sta = network.WLAN(network.STA_IF); sta.active(True); sta.disconnect()
#   e = espnow.ESPNow(); e.active(True)
#   e.add_peer(b'\xFF\xFF\xFF\xFF\xFF\xFF')
#   e.send(b'\xFF\xFF\xFF\xFF\xFF\xFF', b"FD_GO")      # start music
#   e.send(b'\xFF\xFF\xFF\xFF\xFF\xFF', b"FD_FREEZE")   # pause music
#   e.send(b'\xFF\xFF\xFF\xFF\xFF\xFF', b"stop")        # stop music

# ═══════════════════════════════════════════════════════════════════
# 5. STANDARD MICROPYTHON MODULES AVAILABLE
# ═══════════════════════════════════════════════════════════════════
# machine    — Pin, PWM, SoftI2C, Timer, ADC, etc.
# time       — sleep_ms(), ticks_ms(), ticks_diff(), ticks_add(), sleep()
# math       — sin, cos, pi, sqrt, abs, etc.
# random     — randint, choice, random, shuffle, getrandbits
# json       — dumps, loads
# struct     — pack, unpack
# sys        — print_exception
# _thread    — start_new_thread (for concurrent actions)
# network    — WLAN (for ESP-NOW)
# espnow     — ESPNow
# neopixel   — NeoPixel
# gc         — collect, mem_free

# ═══════════════════════════════════════════════════════════════════
# 6. CONSTRAINTS AND GOTCHAS
# ═══════════════════════════════════════════════════════════════════
# - f-strings CRASH on this MicroPython build. Use % formatting ONLY.
#     WRONG:  print(f"value = {x}")
#     RIGHT:  print("value = %d" % x)
# - I2C bus is 100kHz. PN532 fails at 400kHz. Do not change.
# - NeoPixel byte order is GRB (SK6812). Leds.solid(r,g,b) accepts RGB.
#   Raw np[i] = (g, r, b) if bypassing Leds class.
# - PN532 NFC reads are slow (~200-500ms). Don't poll every frame.
#   Pattern: poll NFC every 10-15 loop iterations (~500ms-750ms).
# - ESP32-C6 has limited RAM (~512KB). Avoid large allocations. Use gc.collect().
# - time.sleep_ms() is the preferred delay — time.sleep() takes seconds (float).
# - Button on GPIO0 is active LOW with internal pull-up.
#     btn = machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP)
#     pressed = (btn.value() == 0)
# - Motor on GPIO21: machine.Pin(21, machine.Pin.OUT) then .value(1/0)
# - All NFC tags are MIFARE Classic 1K. NDEF text records in sectors 1-2.
#   Use COMMON_KEYS for auth. Read blocks 4-6 (sector 1) and 8-10 (sector 2).
#   Block 7 and 11 are sector trailers — never read/write those.
# - Accelerometer at ±4g, 100Hz. accel.read() → (x,y,z) in g.
#   Resting on table ≈ (0, 0, ±1.0). Gravity is always present.
# - ESP-NOW requires external antenna config on this board:
#   Pin(3).value(0); Pin(14).value(1) before WLAN activation.
#   ESPNowManager.init() handles this automatically.
# - Max ~250 bytes per ESP-NOW message (practical limit ~240).
#   Use short strings or packed binary for multiplayer.
# - GPIO0 is also the boot pin — holding button during reset enters bootloader.

# ═══════════════════════════════════════════════════════════════════
# 7. TEMPLATE: MINIMAL jumpin.py
# ═══════════════════════════════════════════════════════════════════

"""
Jump In — Custom Game Module for Wand Module
==============================================
Tap the "jumpin" NFC tag to enter this mode.
Tap "stop" tag to exit back to programming mode.

Entry point — called from main.py:
    from jumpin import play
    play(nfc, leds, buz, accel, i2c)
"""

import machine
import time

from pn532 import MIFARE_AUTH_A, MIFARE_AUTH_B
from nfc_reader import _decode_ndef_text, COMMON_KEYS
from buzzer import Buzzer

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────
NUM_LEDS = 25
SWITCH_PIN = 0  # Button pin (GPIO0)


# ─────────────────────────────────────────────
# NFC READING (lightweight, same as other games)
# ─────────────────────────────────────────────
def _read_tag_text(nfc):
    """Quick NDEF text read. Returns (text, uid_hex) or (None, None)."""
    tag = nfc.read_passive_target(timeout=200)
    if tag is None:
        return None, None
    if tag['sak'] not in (0x08, 0x18):
        return None, tag['uid_hex']
    ndef_data = bytearray()
    for sector in (1, 2):
        first_block = sector * 4
        authed = False
        for key in COMMON_KEYS:
            for key_type in [MIFARE_AUTH_A, MIFARE_AUTH_B]:
                resel = nfc.read_passive_target(timeout=150)
                if resel is None:
                    continue
                if nfc.mifare_auth_block(resel['uid'], first_block, key, key_type):
                    for blk in range(first_block, first_block + 3):
                        try:
                            ndef_data.extend(nfc.mifare_read_block(blk))
                        except Exception:
                            ndef_data.extend(b'\x00' * 16)
                    authed = True
                    break
            if authed:
                break
        if not authed:
            ndef_data.extend(b'\x00' * 48)
    text = _decode_ndef_text(ndef_data)
    return text, tag['uid_hex']


# ─────────────────────────────────────────────
# YOUR GAME LOGIC GOES HERE
# ─────────────────────────────────────────────
def run_game(nfc, np, buz, accel):
    """
    Main game loop. Runs until stop tag is tapped.

    Args:
        nfc:   PN532 driver instance
        np:    NeoPixel object (25 LEDs, raw pixel access)
        buz:   Buzzer instance
        accel: LIS2DW12 accelerometer instance

    Available hardware:
        np[i] = (r, g, b); np.write()   — set LEDs (25 pixels, 5x5 grid)
        buz.beep(freq, ms)              — play a tone
        accel.read()                    — returns (x, y, z) in g
        machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP).value()  — button (0=pressed)
        machine.Pin(21, machine.Pin.OUT).value(1/0)  — vibration motor

    This function should periodically check for the stop tag
    and return when it's detected.
    """
    frame = 0
    print("  Game running — tap STOP to exit\n")

    while True:
        # ─── CHECK FOR STOP TAG (every ~10 frames = ~500ms) ───
        if frame % 10 == 0:
            text, uid = _read_tag_text(nfc)
            if text == "stop":
                print("  STOP tag detected")
                return

        # ─── YOUR CODE HERE ───
        # Example: rainbow breathing
        # import math
        # for i in range(NUM_LEDS):
        #     hue = (i * 10 + frame * 3) % 255
        #     np[i] = (hue // 3, (255 - hue) // 5, hue // 4)
        # np.write()

        time.sleep_ms(50)
        frame += 1


# ─────────────────────────────────────────────
# ENTRY POINT (called from main.py)
# ─────────────────────────────────────────────
def play(nfc, leds, buz, accel, i2c):
    """
    Called from main.py when the "jumpin" tag is tapped.
    Runs until STOP is scanned.

    Args:
        nfc:   PN532 driver instance
        leds:  Leds instance (we use leds.np for raw NeoPixel access)
        buz:   Buzzer instance
        accel: LIS2DW12 instance
        i2c:   SoftI2C instance (available for additional sensors)
    """
    np = leds.np

    # Entry sound
    buz.beep(523, 80)
    time.sleep_ms(40)
    buz.beep(784, 80)
    time.sleep_ms(40)
    buz.beep(1047, 120)

    print("\n  === ENTERING JUMP IN MODE ===")
    print("  Tap STOP tag to return to programming\n")

    try:
        run_game(nfc, np, buz, accel)
    finally:
        # Clean up LEDs on exit
        for i in range(NUM_LEDS):
            np[i] = (0, 0, 0)
        np.write()

    print("\n  === RETURNING TO PROGRAMMING MODE ===\n")