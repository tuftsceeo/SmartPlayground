"""
Melody Builder — NFC Note Recording Game
========================================
Scan note tags to build a melody, tap "save" to commit,
press button to play back. Tap "stop" tag to exit.

Colors from leds.py — auto-scale with ambient brightness.

Entry points:
    play(nfc, leds, buz, accel, i2c, enow)  — called from main.py
    main()                             — standalone testing
"""

import machine
import time
import math
from machine import Pin

from pn532 import PN532
from nfc_reader import NfcReader
from buzzer import NOTE_FREQ
from leds import (
    RED, GREEN, BLUE, YELLOW, BLUE_DIM, SHAPE_PLAY, SHAPE_CHECK,
    SHAPE_C, SHAPE_D, SHAPE_E, SHAPE_G,
)


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

NOTE_SHAPE = {
    "note_c": SHAPE_C,
    "note_d": SHAPE_D,
    "note_e": SHAPE_E,
    "note_g": SHAPE_G,
}

SCAN_NOTE_MS = 250
PLAY_NOTE_MS = 300
GAP_MS = 80
LOOP_SLEEP_MS = 40
REPEAT_SCAN_GUARD_MS = 1200


# ─────────────────────────────────────────────
# Sound Sequences
# ─────────────────────────────────────────────
SOUNDS = {
    'enter': [(659, 80, 40), (784, 80, 40), (880, 80, 40), (1047, 120, 0)],  # E5-G5-A5-C6
    'exit':  [(784, 80, 40), (659, 80, 40), (523, 120, 0)],                  # G5-E5-C5
}


def _play(buz, name):
    """Play a named sound sequence."""
    seq = SOUNDS.get(name)
    if not seq:
        return
    for freq, dur, gap in seq:
        buz.beep(freq, dur)
        if gap:
            time.sleep_ms(gap)


# ─────────────────────────────────────────────
# Display Class
# ─────────────────────────────────────────────
class MelodyDisplay:
    """Handles all LED display for the melody game."""
    
    def __init__(self, leds):
        self.leds = leds
    
    def clear(self):
        """Turn off all LEDs."""
        self.leds.off()
    
    def show_idle(self, frame=0):
        """Display idle state with breathing blue effect."""
        breath = (math.sin(frame * 0.08) + 1) / 2
        level = 0.2 + 0.8 * breath
        r = int(BLUE_DIM[0] * level)
        g = int(BLUE_DIM[1] * level)
        b = int(BLUE_DIM[2] * level)
        self.leds.solid(r, g, b)
    
    def show_note_color(self, cmd):
        """Display solid color for a note."""
        if cmd in NOTE_COLOR:
            r, g, b = NOTE_COLOR[cmd]
            self.leds.solid(r, g, b)
    
    def show_save_confirm(self):
        """Display checkmark shape in green for save confirmation."""
        self.leds.show_shape(SHAPE_CHECK, GREEN)
    
    def show_play_indicator(self, frame=0):
        """Display play shape in blue with pulse effect."""
        pulse = (math.sin(frame * 0.15) + 1) / 2
        scale = 0.5 + 0.5 * pulse
        color = (
            int(BLUE[0] * scale),
            int(BLUE[1] * scale),
            int(BLUE[2] * scale),
        )
        self.leds.show_shape(SHAPE_PLAY, color)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def _to_buzzer_key(cmd):
    """Convert "note_c" -> "notec" to match NOTE_FREQ keys."""
    return cmd.replace("_", "")


def _play_note_with_color(cmd, ms, leds, buz):
    """Play a note while showing its letter shape in color on LEDs."""
    buz_key = _to_buzzer_key(cmd)
    
    if buz_key not in NOTE_FREQ or cmd not in NOTE_COLOR:
        buz.reject()
        leds.flash(127, 0, 0, times=2)
        return
    
    color = NOTE_COLOR[cmd]
    shape = NOTE_SHAPE.get(cmd)
    freq = NOTE_FREQ[buz_key]
    
    if shape:
        leds.show_shape(shape, color)
    else:
        leds.fill(color)
    buz.play_note(freq, ms)
    leds.off()


# ─────────────────────────────────────────────
# Game Class
# ─────────────────────────────────────────────
class MelodyGame:
    """Note recording and playback game."""
    
    def __init__(self, nfc, leds, buz, enow):
        self.nfc = nfc
        self.leds = leds
        self.buz = buz
        self.enow = enow
        self.display = MelodyDisplay(leds)
        self.btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
        self.reader = NfcReader(nfc, COMMANDS)
        
        # Game state
        self.current_melody = []
        self.saved_melody = []
        self.awaiting_new_song = False
        self.last_uid = None
        self.last_scan_ms = 0
        self._frame = 0
        
        # Button state: read at init to avoid false trigger from held button
        self._btn_was_down = (self.btn.value() == 0)
    
    def _save_song(self):
        """Save current melody and prepare for new recording."""
        self.saved_melody = list(self.current_melody)
        self.awaiting_new_song = True
        self.display.show_save_confirm()
        time.sleep_ms(300)
        self.display.clear()
        self.buz.confirm()
    
    def _play_saved(self):
        """Play back the saved melody."""
        if len(self.saved_melody) == 0:
            self.buz.reject()
            return
        
        self.display.show_play_indicator(self._frame)
        time.sleep_ms(200)
        
        for cmd in self.saved_melody:
            _play_note_with_color(cmd, PLAY_NOTE_MS, self.leds, self.buz)
            time.sleep_ms(GAP_MS)
        
        self.buz.confirm()
    
    def _check_button(self):
        """Check for debounced button press edge. Returns True on press."""
        down = (self.btn.value() == 0)
        if down and not self._btn_was_down:
            time.sleep_ms(30)  # Debounce
            if self.btn.value() == 0:
                self._btn_was_down = True
                return True
        elif not down and self._btn_was_down:
            self._btn_was_down = False
        return False
    
    def run(self):
        """Main game loop. Returns when stop tag is tapped."""
        print("  Scan note tags (C, D, E, G), tap SAVE to commit")
        print("  Press button to play back, tap STOP or station stop to exit\n")
        
        while True:
            # ── ESP-NOW ──
            if self.enow:
                msg_type, _, _ = self.enow.poll()
                if msg_type == "stop":
                    print("  ESP-NOW stop")
                    return

            # ── DISPLAY UPDATE ──
            self.display.show_idle(self._frame)
            
            # ── STOP CHECK via NfcReader (at top of loop) ──
            # NfcReader.read_command() returns "stop" if stop tag detected
            cmd, uid = self.reader.read_command(timeout=200)
            
            if cmd == "stop":
                print("  STOP tag detected")
                return
            
            # ── GAME LOGIC ──
            if uid is None:
                self.last_uid = None
            elif cmd:
                now = time.ticks_ms()
                # Skip if same tag and within repeat guard window
                if uid == self.last_uid and time.ticks_diff(now, self.last_scan_ms) < REPEAT_SCAN_GUARD_MS:
                    pass
                else:
                    self.last_uid = uid
                    self.last_scan_ms = now
                    
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
            
            self._frame += 1
            time.sleep_ms(LOOP_SLEEP_MS)


# ─────────────────────────────────────────────
# Entry Point: Wand Integration
# ─────────────────────────────────────────────
def play(nfc, leds, buz, accel, i2c, enow):
    """
    Called from main.py when the "melody" tag is tapped.
    Hardware is already initialized by the caller.
    """
    _play(buz, 'enter')
    leds.solid(0, 20, 20)
    time.sleep_ms(200)
    leds.off()
    
    print("\n  === MELODY BUILDER ===")
    
    try:
        MelodyGame(nfc, leds, buz, enow).run()
    finally:
        _play(buz, 'exit')
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
    
    from espnow_manager import ESPNowManager
    enow = ESPNowManager()
    enow.init()

    print()
    
    # Run the game
    play(nfc, leds, buz, None, i2c, enow)


if __name__ == "__main__":
    main()
