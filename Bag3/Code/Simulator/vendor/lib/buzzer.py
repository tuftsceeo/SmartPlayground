# Hand-mirrored from Bag3/BroadcastBox/MockWand/lib/buzzer.py, not synced
# from Bag2/Code/lib/buzzer.py.
"""
Buzzer Helpers — PWM piezo sound control
==========================================
Handles beeps, melodies, notes, and named audio icons for feedback.

Usage:
    from buzzer import Buzzer

    buz = Buzzer(pin=19)
    buz.beep(880, 100)
    buz.confirm()
    buz.play_note(440, 400)
    buz.melody()
    buz.play('success')
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
    "notechigh": 523,
}

# Named audio icons: freq, ms, gap_ms steps. freq=0 is a silent step.
SOUNDS = {
    # ── Positive ──
    "confirm": [(880, 60, 40), (1200, 80, 0)],
    "success": [(784, 90, 30), (1047, 90, 30), (1319, 140, 0)],
    "celebrate": [
        (523, 70, 15), (659, 70, 15), (784, 70, 15), (1047, 90, 20),
        (1047, 50, 15), (1319, 50, 15), (1047, 50, 0),
    ],
    "start": [(660, 80, 30), (880, 80, 30), (1100, 120, 0)],

    # ── Neutral ──
    "info": [(1000, 50, 60), (1000, 50, 0)],
    "tick": [(1200, 25, 0)],
    "question": [(700, 70, 30), (600, 70, 40), (1000, 160, 0)],
    "waiting": [(600, 90, 120), (900, 90, 0)],

    # ── Negative ──
    "warn": [(1500, 90, 40), (1200, 90, 40), (1500, 90, 0)],
    "error": [(400, 120, 60), (300, 120, 60), (200, 160, 0)],
    "reject": [(220, 150, 100), (220, 150, 0)],
    "stop": [(800, 80, 30), (400, 200, 0)],
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

    def play(self, name):
        """Play a named audio icon from SOUNDS."""
        steps = SOUNDS[name]
        buz = machine.PWM(machine.Pin(self.pin))
        for freq, ms, gap_ms in steps:
            if freq:
                buz.freq(freq); buz.duty_u16(32768)
            else:
                buz.duty_u16(0)
            time.sleep_ms(ms)
            buz.duty_u16(0)
            if gap_ms:
                time.sleep_ms(gap_ms)
        buz.deinit()

    # ── Feedback sounds ──

    def confirm(self):
        """Two rising tones — tag accepted."""
        self.play("confirm")

    def success(self):
        """Three rising tones, action completed."""
        self.play("success")

    def celebrate(self):
        """Ascending run plus a trill, milestone."""
        self.play("celebrate")

    def start(self):
        """Three rising tones — entering run mode."""
        self.play("start")

    def info(self):
        """Two flat blips, neutral notice."""
        self.play("info")

    def tick(self):
        """One short blip, progress/counting."""
        self.play("tick")

    def question(self):
        """Falling then rising tone, waiting for input."""
        self.play("question")

    def stop(self):
        """Descending tone — stopping."""
        self.play("stop")

    def reject(self):
        """Double low tone — invalid action."""
        self.play("reject")

    def warn(self):
        """Alternating high tones, warning."""
        self.play("warn")

    def error(self):
        """Falling tone, failure."""
        self.play("error")
