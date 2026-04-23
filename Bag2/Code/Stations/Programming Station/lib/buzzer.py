"""
Buzzer Helpers — PWM piezo sound control
==========================================
Handles beeps, melodies, notes, and feedback sounds.

Usage:
    from buzzer import Buzzer

    buz = Buzzer(pin=19)
    buz.beep(880, 100)
    buz.confirm()
    buz.play_note(440, 400)
    buz.melody()
"""

import machine
import time

# 4th octave note frequencies
NOTE_FREQ = {
    "notec": 262,
    "noted": 294,
    "notee": 330,
    "notef": 349,
    "noteg": 392,
    "notea": 440,
    "noteb": 494,
}


class Buzzer:
    def __init__(self, pin):
        self.pin = pin

    # ── Core ──

    def beep(self, freq=1000, ms=100):
        buz = machine.PWM(machine.Pin(self.pin))
        buz.freq(freq); buz.duty_u16(32768)
        time.sleep_ms(ms)
        buz.duty_u16(0); buz.deinit()

    def play_note(self, freq, ms=400):
        buz = machine.PWM(machine.Pin(self.pin))
        buz.freq(freq); buz.duty_u16(32768)
        time.sleep_ms(ms)
        buz.duty_u16(0); buz.deinit()

    def melody(self):
        """Short ascending melody: C5-E5-G5-C6."""
        notes = [(523, 150), (659, 150), (784, 200), (1047, 300)]
        buz = machine.PWM(machine.Pin(self.pin))
        for freq, dur in notes:
            buz.freq(freq); buz.duty_u16(32768)
            time.sleep_ms(dur)
            buz.duty_u16(0); time.sleep_ms(30)
        buz.deinit()

    # ── Feedback sounds ──

    def confirm(self):
        """Two rising tones — tag accepted."""
        self.beep(880, 60); time.sleep_ms(40); self.beep(1200, 80)

    def start(self):
        """Three rising tones — entering run mode."""
        self.beep(660, 80); time.sleep_ms(30)
        self.beep(880, 80); time.sleep_ms(30)
        self.beep(1100, 120)

    def stop(self):
        """Descending tone — stopping."""
        self.beep(800, 80); time.sleep_ms(30); self.beep(400, 200)

    def reject(self):
        """Double low tone — invalid action."""
        self.beep(200, 150); time.sleep_ms(100); self.beep(200, 150)

    def warn(self):
        """Single low tone — warning."""
        self.beep(200, 300)