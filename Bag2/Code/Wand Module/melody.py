"""
Melody Builder — NFC Note Recording Game
========================================
Scan note tags to build a melody, tap "save" to commit,
press button to play back. Tap "stop" tag to exit.

Colors from leds.py — auto-scale with ambient brightness.
"""

import machine
import time

from nfc_reader import NfcReader
from buzzer import NOTE_FREQ
from leds import RED, GREEN, BLUE, YELLOW


# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
MAX_NOTES = 64

COMMANDS = {"note_c", "note_d", "note_e", "note_g", "save", "stop"}

NOTE_COLOR = {
    "note_c": RED,
    "note_d": GREEN,
    "note_e": BLUE,
    "note_g": YELLOW,
}

# Timings
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
# Entry point
# ─────────────────────────────────────────────
def play(nfc, leds, buz, accel, i2c):
    """
    Melody Builder game entry point.
    Scan note tags to build a melody, tap "save" to commit,
    press button to play back. Tap "stop" tag to exit.
    """
    button = machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP)
    
    reader = NfcReader(nfc, COMMANDS)
    
    # Game state
    current_melody = []
    saved_melody = []
    awaiting_new_song = False
    last_button = 1
    
    def save_song():
        nonlocal saved_melody, awaiting_new_song
        saved_melody = list(current_melody)
        awaiting_new_song = True
        leds.flash(80, 80, 80, times=2)
        buz.confirm()
    
    def play_saved():
        if len(saved_melody) == 0:
            buz.reject()
            return
        
        leds.flash(0, 0, 30, times=1, on_ms=80, off_ms=40)
        
        for cmd in saved_melody:
            _play_note_with_color(cmd, PLAY_NOTE_MS, leds, buz)
            time.sleep_ms(GAP_MS)
        
        buz.confirm()
    
    # Entry feedback
    buz.beep(523, 100)
    leds.solid(0, 20, 20)
    time.sleep_ms(200)
    leds.off()
    
    print("\n  === MELODY BUILDER ===")
    print("  Scan note tags (C, D, E, G), tap SAVE to commit")
    print("  Press button to play back, tap STOP to exit\n")
    
    try:
        while True:
            # NFC read
            cmd, uid = reader.read_command(timeout=200)
            
            if cmd:
                if cmd == "stop":
                    print("  STOP tag detected")
                    return
                
                if cmd.startswith("note_"):
                    if awaiting_new_song:
                        current_melody = []
                        awaiting_new_song = False
                    
                    if len(current_melody) >= MAX_NOTES:
                        buz.warn()
                        print("  Melody full (%d notes max)" % MAX_NOTES)
                    else:
                        current_melody.append(cmd)
                        _play_note_with_color(cmd, SCAN_NOTE_MS, leds, buz)
                        print("  Note: %s (%d in sequence)" % (cmd, len(current_melody)))
                
                elif cmd == "save":
                    save_song()
                    print("  Melody saved (%d notes)" % len(saved_melody))
            
            # Button edge detect (active LOW)
            btn = button.value()
            if last_button == 1 and btn == 0:
                print("  Playing saved melody...")
                play_saved()
            last_button = btn
            
            time.sleep_ms(LOOP_SLEEP_MS)
    
    finally:
        leds.off()
        print("\n  === RETURNING TO PROGRAMMING MODE ===\n")
