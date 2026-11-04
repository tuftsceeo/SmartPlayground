"""
Jump In 1 — Button Press LED Blink
================================
Tap the "jumpin1" NFC tag to enter this mode.
Press the button to blink all LEDs green.
Tap "stop" tag to exit back to programming mode.

Colors from leds.py — auto-scale with ambient brightness.

Entry points:
    play(nfc, leds, buz, accel, i2c, enow)  — called from main.py
    main()                             — standalone testing
"""


"""
NOTE: This is a simple template game for creating new games as described in GAME_AUTHORING_GUIDE.md
This is a simple Button Blink Test and not a real game.
The template pattern:
    1. Game class with __init__() and run()
    2. play() for wand integration (hardware passed in)
    3. main() for standalone testing (initializes hardware)
    4. CRITICAL: check for stop tags and ESP-NOW stop messages at start of run loop
"""

import machine
import time
from machine import Pin

from pn532 import PN532, MIFARE_AUTH_A, MIFARE_AUTH_B
from nfc_reader import _decode_ndef_text, COMMON_KEYS
from game_tags import exit_tags_excluding

_EXIT_TAGS = exit_tags_excluding("jumpin1")
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
class JumpIn1Game:
    """Button-press LED blink game."""
    
    def __init__(self, nfc, leds, buz, enow):
        self.nfc = nfc
        self.leds = leds
        self.buz = buz
        self.enow = enow
        self.np = leds.np
        self.btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
        self._frame = 0
    
    def _check_stop(self):
        """Check ESP-NOW and NFC for stop. Returns True if stop detected."""
        if self.enow:
            msg_type, _, _ = self.enow.poll()
            if msg_type in ("stop", "start_game"):
                return True
        if self._frame % NFC_POLL_INTERVAL != 0:
            return False
        try:
            text, uid = _read_tag_text(self.nfc)
            return text in _EXIT_TAGS
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
        print("  Tap STOP tag or station stop to exit\n")
        
        while True:
            # ── STOP CHECK FIRST (always at top of loop) ──
            if self._check_stop():
                print("  Stop detected")
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
def play(nfc, leds, buz, accel, i2c, enow):
    """
    Called from main.py when the "jumpin1" tag is tapped.
    Hardware is already initialized by the caller.
    """
    buz.beep(523, 100)
    
    print("\n  === BUTTON BLINK MODE 1 ===")
    
    try:
        JumpIn1Game(nfc, leds, buz, enow).run()
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
    print("  Jump In 1 — Button Blink Test")
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

    # Initialize Accelerometer
    accel = None
    accel_ok = False
    try:
        accel = LIS2DW12(i2c)
        accel.init(fs_range=RANGE_4G)
        accel_ok = True
        print("  Accelerometer OK")
    except Exception as e:
        print("  [WARN] Accel:"); sys.print_exception(e)
    
    # Initialize ESP-NOW
    from espnow_manager import ESPNowManager
    enow = ESPNowManager()
    enow.init()

    print()
    
    # Run the game
    play(nfc, leds, buz, accel, i2c, enow)


if __name__ == "__main__":
    main()
