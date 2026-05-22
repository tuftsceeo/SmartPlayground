"""
Jump In — Button Press LED Blink
================================
Tap the "jumpin" NFC tag to enter this mode.
Press the button to blink all LEDs green.
Tap "stop" tag to exit back to programming mode.

Colors from leds.py — auto-scale with ambient brightness.
"""

import machine
import time

from pn532 import MIFARE_AUTH_A, MIFARE_AUTH_B
from nfc_reader import _decode_ndef_text, COMMON_KEYS
from leds import GREEN, OFF

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────
NUM_LEDS = 25
BUTTON_PIN = 0  # GPIO0 - active LOW with pull-up

# ─────────────────────────────────────────────
# NFC READING
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
# GAME LOGIC
# ─────────────────────────────────────────────
def run_game(nfc, np, buz, accel):
    """
    Main game loop. Blinks LEDs green when button is pressed.
    """
    frame = 0
    button = machine.Pin(BUTTON_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
    
    print("  Press button to blink green LEDs!")
    print("  Tap STOP tag to exit\n")
    
    while True:
        # ─── CHECK FOR STOP TAG (every ~10 frames = ~500ms) ───
        if frame % 10 == 0:
            text, uid = _read_tag_text(nfc)
            if text == "stop":
                print("  STOP tag detected")
                return
        
        # ─── CHECK BUTTON AND BLINK GREEN ───
        if button.value() == 0:  # Button pressed (active LOW)
            print("  Button pressed - blinking green!")
            
            # Turn all LEDs green (library color, auto-scaled)
            for i in range(NUM_LEDS):
                np[i] = GREEN
            np.write()
            
            time.sleep_ms(200)  # Keep green for 200ms
            
            # Turn off all LEDs
            for i in range(NUM_LEDS):
                np[i] = OFF
            np.write()
            
            time.sleep_ms(200)  # Wait before next press can be detected
        
        time.sleep_ms(50)
        frame += 1

# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
def play(nfc, leds, buz, accel, i2c):
    """
    Called from main.py when the "jumpin" tag is tapped.
    """
    np = leds.np
    
    # Entry sound
    buz.beep(523, 100)
    
    print("\n  === BUTTON BLINK MODE ===")
    print("  Press button to blink green!")
    
    try:
        run_game(nfc, np, buz, accel)
    finally:
        # Clean up LEDs on exit
        for i in range(NUM_LEDS):
            np[i] = OFF
        np.write()
    
    print("\n  === RETURNING TO PROGRAMMING MODE ===\n")