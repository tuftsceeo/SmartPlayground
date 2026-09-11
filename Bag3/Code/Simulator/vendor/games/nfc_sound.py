"""
NFC Bell Choir -- tap a note tag to pick your bell, hold the button to ring it.

Starts on a random note. Tapping one of the note cards (note_c ... note_b)
changes it; the same physical cards work in the melody game.

Entry point:
    play(dev)
"""

import random

from buzzer import NOTE_FREQ
from leds import (
    RED, ORANGE, YELLOW, GREEN, BLUE, PURPLE, PINK, WHITE,
    SHAPE_TOP_ROW, SHAPE_BOT_ROW, SHAPE_LEFT_COL, SHAPE_RIGHT_COL,
    SHAPE_BORDER, SHAPE_INNER_3x3, SHAPE_DIAMOND, SHAPE_STAR,
)

LOOP_MS = 40
BEEP_MS = 80

# The reader runs every 5th pass here: this game is played by tapping cards,
# so it needs a faster read than the framework's idle-ish default.
NFC_EVERY = 5

# card tag -> (buzzer note key, colour, shape)
BELLS = {
    "note_c": ("notec", RED, SHAPE_TOP_ROW),
    "note_d": ("noted", ORANGE, SHAPE_BOT_ROW),
    "note_e": ("notee", YELLOW, SHAPE_LEFT_COL),
    "note_f": ("notef", GREEN, SHAPE_RIGHT_COL),
    "note_g": ("noteg", BLUE, SHAPE_BORDER),
    "note_a": ("notea", PURPLE, SHAPE_INNER_3x3),
    "note_b": ("noteb", PINK, SHAPE_DIAMOND),
}

HIGH_C = ("notechigh", WHITE, SHAPE_STAR)


def play(dev):
    dev.buz.start()
    dev.nfc_every = NFC_EVERY
    print("\n  === NFC BELL CHOIR ===")

    bell = random.choice(list(BELLS.values()) + [HIGH_C])
    key, color, shape = bell
    freq = NOTE_FREQ[key]
    print("  You were assigned %s (%d Hz)" % (key, freq))
    print("  Tap a note tag to change your bell; hold the button to play.\n")

    while dev.running():
        ev = dev.event()
        if ev and ev[0] == "tag" and ev[1] in BELLS:
            key, color, shape = BELLS[ev[1]]
            freq = NOTE_FREQ[key]
            print("  Note changed to %s" % key)
            dev.buz.beep(freq, 120)

        if dev.button.value() == 0:
            dev.buz.beep(freq, BEEP_MS)
            dev.leds.show_shape(shape, color)
        else:
            dev.leds.off()
        dev.tick(LOOP_MS)


def main():
    import bench
    play(bench.device(BELLS))


if __name__ == "__main__":
    main()
