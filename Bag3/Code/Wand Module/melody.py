"""
Melody Builder — NFC Note Recording Game
========================================
Scan note tags to build a melody, tap "erase" to clear,
press button to play back. Tap "stop" tag to exit.

Colors from leds.py — auto-scale with ambient brightness.

Entry points:
    play(nfc, leds, buz, accel, i2c, enow)  — called from main.py
    main()                             — standalone testing
"""

import machine
import time
from machine import Pin

from pn532 import PN532
from nfc_reader import NfcReader
from game_tags import exit_tags_excluding

_EXIT_TAGS = exit_tags_excluding("melody")
from buzzer import NOTE_FREQ
from leds import (
    OFF, RED, ORANGE, YELLOW, GREEN, BLUE, PURPLE, PINK, WHITE, TEAL,
    SHAPE_A, SHAPE_B, SHAPE_C, SHAPE_D, SHAPE_E, SHAPE_F, SHAPE_G,
    SHAPE_X, SHAPE_MUSIC, SHAPE_SAD_FACE, SHAPE_QUESTION,
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
MAX_NOTES = 25

COMMANDS = {
    "note_c", "note_d", "note_e", "note_f",
    "note_g", "note_a", "note_b", "note_c_high",
    "erase", "melody",
} | _EXIT_TAGS

NOTE_COLOR = {
    "note_c": RED,
    "note_d": ORANGE,
    "note_e": YELLOW,
    "note_f": GREEN,
    "note_g": BLUE,
    "note_a": PURPLE,
    "note_b": PINK,
    "note_c_high": WHITE,
}

NOTE_SHAPE = {
    "note_c": SHAPE_C,
    "note_d": SHAPE_D,
    "note_e": SHAPE_E,
    "note_f": SHAPE_F,
    "note_g": SHAPE_G,
    "note_a": SHAPE_A,
    "note_b": SHAPE_B,
    "note_c_high": SHAPE_C,
}

SCAN_NOTE_MS = 250
NOTE_LETTER_HOLD_MS = 500
PLAY_NOTE_MS = 300
GAP_MS = 80
ERASE_FADE_MS = 500
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
        """Display idle state with breathing music icon."""
        self.leds.breathe_shape(SHAPE_MUSIC, TEAL, frame, bg=OFF)

    def show_melody_pixels(self, melody, highlight_idx=None):
        """Render melody as one pixel per note in row-major order."""
        for i in range(self.leds.num):
            if i < len(melody):
                color = NOTE_COLOR.get(melody[i], OFF)
                if highlight_idx is not None and i == highlight_idx:
                    color = (
                        min(255, int(color[0] * 1.6)),
                        min(255, int(color[1] * 1.6)),
                        min(255, int(color[2] * 1.6)),
                    )
                self.leds.np[i] = color
            else:
                self.leds.np[i] = OFF
        self.leds.np.write()

    def show_error_max_notes(self):
        """Melody is full. Caller plays a blocking sound to provide visible duration."""
        self.leds.show_shape(SHAPE_SAD_FACE, RED, bg=OFF)

    def show_error_unknown(self):
        """Unknown note mapping. Caller plays a blocking sound to provide visible duration."""
        self.leds.show_shape(SHAPE_QUESTION, RED, bg=OFF)

    def show_error_empty_erase(self):
        """Erase tapped with nothing to clear."""
        self.show_error_max_notes()

    def show_erase_animation(self):
        """Fade X mark after erase."""
        self.leds.fade_shape(SHAPE_X, RED, ERASE_FADE_MS, bg=OFF)


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
        leds.show_shape(SHAPE_QUESTION, RED, bg=OFF)
        buz.reject()
        return
    
    color = NOTE_COLOR[cmd]
    shape = NOTE_SHAPE.get(cmd)
    freq = NOTE_FREQ[buz_key]
    
    if shape:
        leds.show_shape(shape, color)
    else:
        leds.fill(color)
    buz.play_note(freq, ms)
    if NOTE_LETTER_HOLD_MS > ms:
        time.sleep_ms(NOTE_LETTER_HOLD_MS - ms)


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
        self.last_uid = None
        self.last_scan_ms = 0
        self._frame = 0
        
        # Button state: read at init to avoid false trigger from held button
        self._btn_was_down = (self.btn.value() == 0)
    
    def _play_current(self):
        """
        Play back the current melody. Returns False if an ESP-NOW stop is
        received mid-playback, True otherwise.

        Note: NFC stop is not polled during playback — the PN532 requires
        ~50-100 ms per scan, which would add audible gaps between notes.
        Worst-case wait is ~9.5 s (25 notes at 380 ms each). ESP-NOW stop
        from the station still exits immediately.
        """
        for i, cmd in enumerate(self.current_melody):
            if self.enow:
                msg_type, _, _ = self.enow.poll()
                if msg_type in ("stop", "start_game"):
                    print("  ESP-NOW stop")
                    return False

            self.display.show_melody_pixels(self.current_melody, highlight_idx=i)
            buz_key = _to_buzzer_key(cmd)
            if buz_key not in NOTE_FREQ:
                self.display.show_error_unknown()
                self.buz.reject()
                continue
            self.buz.play_note(NOTE_FREQ[buz_key], PLAY_NOTE_MS)
            time.sleep_ms(GAP_MS)
        
        self.buz.confirm()
        return True
    
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
        print("  Scan note tags (C, D, E, F, G, A, B, C high)")
        print("  Tap ERASE to clear, press button to play back")
        print("  Tap STOP or station stop to exit\n")
        
        while True:
            # ── ESP-NOW ──
            if self.enow:
                msg_type, _, _ = self.enow.poll()
                if msg_type in ("stop", "start_game"):
                    print("  ESP-NOW stop")
                    return

            # ── DISPLAY UPDATE ──
            if len(self.current_melody) == 0:
                self.display.show_idle(self._frame)
            else:
                self.display.show_melody_pixels(self.current_melody)
            
            # ── STOP CHECK via NfcReader (at top of loop) ──
            # NfcReader.read_command() returns "stop" if stop tag detected
            cmd, uid = self.reader.read_command(timeout=200)
            
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
                    
                    if cmd in _EXIT_TAGS:
                        print("  Exit tag detected: %s" % cmd)
                        return
                    elif cmd.startswith("note_"):
                        if len(self.current_melody) >= MAX_NOTES:
                            self.display.show_error_max_notes()
                            self.buz.warn()
                            print("  Melody full (%d notes max)" % MAX_NOTES)
                        elif cmd not in NOTE_COLOR or _to_buzzer_key(cmd) not in NOTE_FREQ:
                            self.display.show_error_unknown()
                            self.buz.reject()
                        else:
                            self.current_melody.append(cmd)
                            _play_note_with_color(cmd, SCAN_NOTE_MS, self.leds, self.buz)
                            print("  Note: %s (%d in sequence)" % (cmd, len(self.current_melody)))
                    elif cmd == "erase" or cmd == "melody":
                        if len(self.current_melody) == 0:
                            self.display.show_error_empty_erase()
                            self.buz.warn()
                        else:
                            erased = len(self.current_melody)
                            self.current_melody = []
                            self.display.show_erase_animation()
                            self.buz.confirm()
                            print("  Melody erased (%d notes)" % erased)
            
            # ── BUTTON: Play current melody ──
            if self._check_button():
                if len(self.current_melody) == 0:
                    self.buz.reject()
                else:
                    print("  Playing melody...")
                    keep_running = self._play_current()
                    if not keep_running:
                        return
            
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
    leds.show_shape(SHAPE_MUSIC, TEAL)
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
    print("  Tags: note_c, note_d, note_e, note_f, note_g, note_a, note_b, note_c_high")
    print("  Utility tags: erase, stop\n")
    
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
