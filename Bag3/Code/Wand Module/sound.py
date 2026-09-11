"""
Bell Choir -- each wand gets a random note; hold the button to ring it.

Hold to sound your note and show its colour and shape, release to stop. With a
wand each, a group makes a chord.

Entry point:
    play(dev)
"""

import random

from leds import (
    RED, ORANGE, YELLOW, GREEN, BLUE, PURPLE, PINK, WHITE,
    SHAPE_TOP_ROW, SHAPE_BOT_ROW, SHAPE_LEFT_COL, SHAPE_RIGHT_COL,
    SHAPE_BORDER, SHAPE_INNER_3x3, SHAPE_DIAMOND, SHAPE_STAR,
)

LOOP_MS = 40
BEEP_MS = 80

# note -> (hz, colour, shape)
BELLS = {
    "C4": (262, RED, SHAPE_TOP_ROW),
    "D4": (294, ORANGE, SHAPE_BOT_ROW),
    "E4": (330, YELLOW, SHAPE_LEFT_COL),
    "F4": (349, GREEN, SHAPE_RIGHT_COL),
    "G4": (392, BLUE, SHAPE_BORDER),
    "A4": (440, PURPLE, SHAPE_INNER_3x3),
    "B4": (494, PINK, SHAPE_DIAMOND),
    "C5": (523, WHITE, SHAPE_STAR),
}


def play(dev):
    dev.buz.start()
    print("\n  === BELL CHOIR ===")

    note = random.choice(list(BELLS))
    freq, color, shape = BELLS[note]
    print("  You were assigned %s (%d Hz)" % (note, freq))
    print("  Hold the button to play your note.\n")

    while dev.running():
        if dev.button.value() == 0:
            dev.buz.beep(freq, BEEP_MS)
            dev.leds.show_shape(shape, color)
        else:
            dev.leds.off()
        dev.tick(LOOP_MS)


def main():
    import bench
    play(bench.device())


if __name__ == "__main__":
    main()
