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

from pn532 import PN532
from nfc_reader import NfcReader, _decode_ndef_text, COMMON_KEYS
from pn532 import MIFARE_AUTH_A, MIFARE_AUTH_B
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
        np:    NeoPixel object (25 LEDs, raw access)
        buz:   Buzzer instance
        accel: LIS2DW12 accelerometer instance

    This function should periodically check for the stop tag
    and return when it's detected.
    """
    last_uid = None
    frame = 0

    print("  Game running — tap STOP to exit\n")

    while True:
        # ─── CHECK FOR STOP TAG (every ~10 frames) ───
        if frame % 10 == 0:
            text, uid = _read_tag_text(nfc)
            if text == "stop":
                print("  STOP tag detected")
                return

        # ─── YOUR CODE HERE ───
        # Do whatever you want! Use:
        #   np[i] = (r, g, b)  /  np.write()   — LEDs
        #   buz.beep(freq, ms)                  — buzzer
        #   accel.read_accel()                  — accelerometer (x, y, z)
        #   machine.Pin(SWITCH_PIN, ...).value() — button

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
        i2c:   SoftI2C instance (available if needed)
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