"""
Jump In — Button Press LED Blink
================================
Tap the "jumpin" NFC tag to enter this mode.
Press the button to blink all LEDs green.
Tap "stop" tag to exit back to programming mode.

Colors from leds.py — auto-scale with ambient brightness.

Entry points:
    play(nfc, leds, buz, accel, i2c)  — called from main.py
    main()                             — standalone testing

Template Pattern:
    1. Game class with __init__() and run()
    2. play() for wand integration (hardware passed in)
    3. main() for standalone testing (initializes hardware)
    4. CRITICAL: _check_stop_tag() polled at START of every loop
"""

import machine
import time
from machine import Pin

from pn532 import PN532, MIFARE_AUTH_A, MIFARE_AUTH_B
from nfc_reader import _decode_ndef_text, COMMON_KEYS
from leds import GREEN, OFF

# ─────────────────────────────────────────────
# Hardware Config
# ─────────────────────────────────────────────
I2C_SDA, I2C_SCL = 22, 23
NEOPIXEL_PIN = 20
NUM_LEDS = 25
BUZZER_PIN = 19
BUTTON_PIN = 0
PN532_ADDR = 0x24

# ─────────────────────────────────────────────
# Game Config
# ─────────────────────────────────────────────
NFC_POLL_INTERVAL = 10
LOOP_DELAY_MS = 50
BLINK_ON_MS = 200
BLINK_OFF_MS = 200


# ─────────────────────────────────────────────
# NFC Helper
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
            for key_type in (MIFARE_AUTH_A, MIFARE_AUTH_B):
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
    
    return _decode_ndef_text(ndef_data), tag['uid_hex']


# ─────────────────────────────────────────────
# Game Class
# ─────────────────────────────────────────────
class JumpInGame:
    """Button-press LED blink game."""
    
    def __init__(self, nfc, leds, buz):
        self.nfc = nfc
        self.leds = leds
        self.buz = buz
        self.np = leds.np
        self.btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
        self._frame = 0
    
    # ── STOP TAG DETECTION (CRITICAL) ──────────────────────
    # Every game MUST check for stop tag to allow exit.
    # Poll periodically (not every frame) to balance responsiveness
    # with NFC read overhead. Check at START of game loop.
    def _check_stop_tag(self):
        """
        Poll NFC for stop tag. Returns True if stop detected.
        MUST be called every loop iteration — internally throttled.
        """
        if self._frame % NFC_POLL_INTERVAL != 0:
            return False
        try:
            text, uid = _read_tag_text(self.nfc)
            return text == "stop"
        except Exception:
            return False
    
    def _blink_green(self):
        """Blink all LEDs green once."""
        for i in range(NUM_LEDS):
            self.np[i] = GREEN
        self.np.write()
        time.sleep_ms(BLINK_ON_MS)
        
        for i in range(NUM_LEDS):
            self.np[i] = OFF
        self.np.write()
        time.sleep_ms(BLINK_OFF_MS)
    
    def run(self):
        """Main game loop. Returns when stop tag is tapped."""
        print("  Press button to blink green LEDs!")
        print("  Tap STOP tag to exit\n")
        
        while True:
            # ── STOP CHECK FIRST (always at top of loop) ──
            if self._check_stop_tag():
                print("  STOP tag detected")
                return
            
            # ── GAME LOGIC ──
            if self.btn.value() == 0:
                print("  Button pressed!")
                self._blink_green()
            
            time.sleep_ms(LOOP_DELAY_MS)
            self._frame += 1


# ─────────────────────────────────────────────
# Entry Point: Wand Integration
# ─────────────────────────────────────────────
def play(nfc, leds, buz, accel, i2c):
    """
    Called from main.py when the "jumpin" tag is tapped.
    Hardware is already initialized by the caller.
    """
    buz.beep(523, 100)
    
    print("\n  === BUTTON BLINK MODE ===")
    
    try:
        JumpInGame(nfc, leds, buz).run()
    finally:
        leds.off()
        print("\n  === RETURNING TO PROGRAMMING MODE ===\n")


# ─────────────────────────────────────────────
# Entry Point: Standalone Testing
# ─────────────────────────────────────────────
def main():
    """
    Standalone entry point for testing without main.py.
    Run directly: import jumpin; jumpin.main()
    """
    print("\n" + "=" * 45)
    print("  Jump In — Button Blink Test")
    print("=" * 45)
    
    # Initialize I2C
    i2c = machine.SoftI2C(sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=100_000)
    
    # Calibrate brightness from ambient light
    import brightness
    try:
        from opt3002 import OPT3002
        light = OPT3002(i2c)
        light.init()
        mult, lux = brightness.calibrate(light)
        if lux is not None:
            print("  Light: %.0f lux -> brightness x%.2f" % (lux, mult))
    except Exception as e:
        print("  [WARN] OPT3002: %s — brightness x1.00" % e)
    
    # Initialize LEDs
    from leds import Leds
    leds = Leds()
    
    # Initialize buzzer
    from buzzer import Buzzer
    buz = Buzzer(BUZZER_PIN)
    
    # Initialize NFC
    nfc = PN532(i2c, PN532_ADDR)
    try:
        ic, ver, rev = nfc.begin()
        print("  PN5%02X fw %d.%d — NFC ready" % (ic, ver, rev))
    except Exception as e:
        print("  NFC init failed: %s" % e)
        return
    
    print()
    
    # Run the game
    play(nfc, leds, buz, None, i2c)


if __name__ == "__main__":
    main()
