"""
Melody Builder -- record a tune from note cards and play it back.

Tap note cards to append notes (each lights its letter and sounds), "backspace"
to drop the last one, "erase" to clear, and press the button to play the melody
back. The grid shows one pixel per recorded note, coloured by pitch.

Entry point:
    play(dev)
"""

import time

from buzzer import NOTE_FREQ
from leds import (
    OFF, RED, ORANGE, YELLOW, GREEN, BLUE, PURPLE, PINK, WHITE, TEAL,
    SHAPE_A, SHAPE_B, SHAPE_C, SHAPE_D, SHAPE_E, SHAPE_F, SHAPE_G,
    SHAPE_X, SHAPE_MUSIC, SHAPE_SAD_FACE, SHAPE_QUESTION,
)

MAX_NOTES = 25
LOOP_MS = 40

# Cards drive this game, so read more often than the framework default.
NFC_EVERY = 3

SCAN_NOTE_MS = 250
NOTE_HOLD_MS = 500
PLAY_NOTE_MS = 300
GAP_MS = 80
ERASE_FADE_MS = 500

# card tag -> (buzzer note key, colour, letter shape)
NOTES = {
    "note_c": ("notec", RED, SHAPE_C),
    "note_d": ("noted", ORANGE, SHAPE_D),
    "note_e": ("notee", YELLOW, SHAPE_E),
    "note_f": ("notef", GREEN, SHAPE_F),
    "note_g": ("noteg", BLUE, SHAPE_G),
    "note_a": ("notea", PURPLE, SHAPE_A),
    "note_b": ("noteb", PINK, SHAPE_B),
    "note_c_high": ("notechigh", WHITE, SHAPE_C),
}

ERASE_TAGS = ("erase", "melody")


class Melody:
    def __init__(self, dev):
        self.dev = dev
        self.notes = []
        self.frame = 0
        self.btn_down = (dev.button.value() == 0)

    # -- display ------------------------------------------------------

    def show(self, highlight=None):
        """One pixel per note in row-major order; the playing note brightens."""
        if not self.notes:
            self.dev.leds.breathe_shape(SHAPE_MUSIC, TEAL, self.frame, bg=OFF)
            return
        pattern = {}
        for i, tag in enumerate(self.notes):
            color = NOTES[tag][1]
            if i == highlight:
                color = tuple(min(255, int(c * 1.6)) for c in color)
            pattern.setdefault(color, []).append(i)
        self.dev.leds.show_pattern(pattern)

    def reject(self, shape):
        self.dev.leds.show_shape(shape, RED, bg=OFF)
        self.dev.buz.warn()

    # -- editing ------------------------------------------------------

    def add(self, tag):
        if len(self.notes) >= MAX_NOTES:
            self.reject(SHAPE_SAD_FACE)
            print("  Melody full (%d notes max)" % MAX_NOTES)
            return
        key, color, shape = NOTES[tag]
        self.notes.append(tag)
        self.dev.leds.show_shape(shape, color)
        self.dev.buz.play_note(NOTE_FREQ[key], SCAN_NOTE_MS)
        time.sleep_ms(NOTE_HOLD_MS - SCAN_NOTE_MS)
        print("  Note: %s (%d in sequence)" % (tag, len(self.notes)))

    def erase(self):
        if not self.notes:
            self.reject(SHAPE_SAD_FACE)
            return
        print("  Melody erased (%d notes)" % len(self.notes))
        self.notes = []
        self.dev.leds.fade_shape(SHAPE_X, RED, ERASE_FADE_MS, bg=OFF)
        self.dev.buz.confirm()

    def backspace(self):
        if not self.notes:
            self.reject(SHAPE_SAD_FACE)
            return
        self.notes.pop()
        self.dev.buz.confirm()
        print("  Backspaced (%d left)" % len(self.notes))

    def card(self, tag):
        if tag in NOTES:
            self.add(tag)
        elif tag in ERASE_TAGS:
            self.erase()
        elif tag == "backspace":
            self.backspace()
        else:
            self.reject(SHAPE_QUESTION)

    # -- playback -----------------------------------------------------

    def pressed(self):
        """Debounced button edge."""
        down = (self.dev.button.value() == 0)
        edge = down and not self.btn_down
        self.btn_down = down
        return edge

    def playback(self):
        """Play the melody through. running() between notes keeps stop live."""
        if not self.notes:
            self.dev.buz.reject()
            return
        print("  Playing melody...")
        for i, tag in enumerate(self.notes):
            if not self.dev.running():
                return
            self.show(highlight=i)
            self.dev.buz.play_note(NOTE_FREQ[NOTES[tag][0]], PLAY_NOTE_MS)
            time.sleep_ms(GAP_MS)
        self.dev.buz.confirm()


def play(dev):
    dev.nfc_every = NFC_EVERY
    dev.buz.start()
    dev.leds.show_shape(SHAPE_MUSIC, TEAL)
    time.sleep_ms(200)

    print("\n  === MELODY BUILDER ===")
    print("  Tap note cards to record, erase to clear, backspace to undo.")
    print("  Press the button to play the melody back.\n")

    mel = Melody(dev)
    while dev.running():
        ev = dev.event()
        if ev and ev[0] == "tag":
            mel.card(ev[1])
        if mel.pressed():
            mel.playback()
        mel.show()
        mel.frame += 1
        dev.tick(LOOP_MS)

    dev.buz.stop()


def main():
    import bench
    play(bench.device(set(NOTES) | set(ERASE_TAGS) | {"backspace"}))


if __name__ == "__main__":
    main()
