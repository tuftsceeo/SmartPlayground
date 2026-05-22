"""
Melody Builder — NFC Note Recording Game
========================================
Scan note tags to build a melody, tap "save" to commit,
press button to play back. Tap "stop" tag to exit.

Colors from leds.py — auto-scale with ambient brightness.

Entry points:
    play(nfc, leds, buz, accel, i2c)  — called from main.py
    main()                             — standalone testing

Template Pattern:
    1. MelodyGame class with __init__() and run()
    2. play() for wand integration (hardware passed in)
    3. main() for standalone testing (initializes hardware)
    4. CRITICAL: Stop tag checked via NfcReader at START of every loop
"""

import machine
import time
from machine import Pin

from pn532 import PN532
from nfc_reader import NfcReader
from buzzer import NOTE_FREQ
from leds import RED, GREEN, BLUE, YELLOW


# ─────────────────────────────────────────────
# Hardware Config
# ─────────────────────────────────────────────
I2C_SDA, I2C_SCL = 22, 23
BUZZER_PIN = 19
BUTTON_PIN = 0
PN532_ADDR = 0x24


# ─────────────────────────────────────────────
# Game Config
# ─────────────────────────────────────────────
MAX_NOTES = 64

COMMANDS = {"note_c", "note_d", "note_e", "note_g", "save", "stop"}

NOTE_COLOR = {
    "note_c": RED,
    "note_d": GREEN,
    "note_e": BLUE,
    "note_g": YELLOW,
}

SCAN_NOTE_MS = 250
PLAY_NOTE_MS = 300
GAP_MS = 80
LOOP_SLEEP_MS = 40


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def _to_buzzer_key(cmd):
    """Convert "note_c" -> "notec" to match NOTE_FREQ keys."""
    return cmd.replace("_", "")


def _play_note_with_color(cmd, ms, leds, buz):
    """Play a note while showing its color on LEDs."""
    buz_key = _to_buzzer_key(cmd)
    
    if buz_key not in NOTE_FREQ or cmd not in NOTE_COLOR:
        buz.reject()
        leds.flash(127, 0, 0, times=2)
        return
    
    r, g, b = NOTE_COLOR[cmd]
    freq = NOTE_FREQ[buz_key]
    
    leds.solid(r, g, b)
    buz.play_note(freq, ms)
    leds.off()


# ─────────────────────────────────────────────
# Game Class
# ─────────────────────────────────────────────
class MelodyGame:
    """Note recording and playback game."""
    
    def __init__(self, nfc, leds, buz):
        self.nfc = nfc
        self.leds = leds
        self.buz = buz
        self.btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
        self.reader = NfcReader(nfc, COMMANDS)
        
        # Game state
        self.current_melody = []
        self.saved_melody = []
        self.awaiting_new_song = False
        self._last_button = 1
    
    def _save_song(self):
        """Save current melody and prepare for new recording."""
        self.saved_melody = list(self.current_melody)
        self.awaiting_new_song = True
        self.leds.flash(80, 80, 80, times=2)
        self.buz.confirm()
    
    def _play_saved(self):
        """Play back the saved melody."""
        if len(self.saved_melody) == 0:
            self.buz.reject()
            return
        
        self.leds.flash(0, 0, 30, times=1, on_ms=80, off_ms=40)
        
        for cmd in self.saved_melody:
            _play_note_with_color(cmd, PLAY_NOTE_MS, self.leds, self.buz)
            time.sleep_ms(GAP_MS)
        
        self.buz.confirm()
    
    def _check_button(self):
        """Check for button press edge (active LOW). Returns True if pressed."""
        btn = self.btn.value()
        pressed = (self._last_button == 1 and btn == 0)
        self._last_button = btn
        return pressed
    
    def run(self):
        """Main game loop. Returns when stop tag is tapped."""
        print("  Scan note tags (C, D, E, G), tap SAVE to commit")
        print("  Press button to play back, tap STOP to exit\n")
        
        while True:
            # ── STOP CHECK via NfcReader (at top of loop) ──
            # NfcReader.read_command() returns "stop" if stop tag detected
            cmd, uid = self.reader.read_command(timeout=200)
            
            if cmd == "stop":
                print("  STOP tag detected")
                return
            
            # ── GAME LOGIC ──
            if cmd:
                if cmd.startswith("note_"):
                    if self.awaiting_new_song:
                        self.current_melody = []
                        self.awaiting_new_song = False
                    
                    if len(self.current_melody) >= MAX_NOTES:
                        self.buz.warn()
                        print("  Melody full (%d notes max)" % MAX_NOTES)
                    else:
                        self.current_melody.append(cmd)
                        _play_note_with_color(cmd, SCAN_NOTE_MS, self.leds, self.buz)
                        print("  Note: %s (%d in sequence)" % (cmd, len(self.current_melody)))
                
                elif cmd == "save":
                    self._save_song()
                    print("  Melody saved (%d notes)" % len(self.saved_melody))
            
            # ── BUTTON: Play saved melody ──
            if self._check_button():
                print("  Playing saved melody...")
                self._play_saved()
            
            time.sleep_ms(LOOP_SLEEP_MS)


# ─────────────────────────────────────────────
# Entry Point: Wand Integration
# ─────────────────────────────────────────────
def play(nfc, leds, buz, accel, i2c):
    """
    Called from main.py when the "melody" tag is tapped.
    Hardware is already initialized by the caller.
    """
    buz.beep(523, 100)
    leds.solid(0, 20, 20)
    time.sleep_ms(200)
    leds.off()
    
    print("\n  === MELODY BUILDER ===")
    
    try:
        MelodyGame(nfc, leds, buz).run()
    finally:
        leds.off()
        print("\n  === RETURNING TO PROGRAMMING MODE ===\n")


# ─────────────────────────────────────────────
# Entry Point: Standalone Testing
# ─────────────────────────────────────────────
def main():
    """
    Standalone entry point for testing without main.py.
    Run directly: import melody; melody.main()
    """
    print("\n" + "=" * 45)
    print("  Melody Builder — Note Recording Game")
    print("=" * 45)
    
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
