"""
Find Device -- hidden identify animation, ESP-NOW only.

Triggered when the teacher clicks this wand in a device list. The hub broadcasts
a targeted identify; espnow_manager delivers it only to the matching wand, which
runs this. A rainbow star and a beep so the wand can be picked out of a pile.

Stops after 5 seconds, on a button press, or on any stop/start. Never on a card:
this is not an NFC game.

Entry point:
    play(dev)
"""

import time

from leds import (
    RED, ORANGE, YELLOW, GREEN, CYAN, BLUE, PURPLE, MAGENTA, SHAPE_STAR,
)

DURATION_MS = 5000
FRAME_MS = 60
BEEP_EVERY_FRAMES = 12   # ~0.72 s
BEEP_FREQ = 1500
BEEP_MS = 60

_RAINBOW = (RED, ORANGE, YELLOW, GREEN, CYAN, BLUE, PURPLE, MAGENTA)


def play(dev):
    print("\n  === FIND DEVICE (identify) ===")
    dev.buz.confirm()

    btn_was_down = (dev.button.value() == 0)
    start = time.ticks_ms()
    frame = 0

    while dev.running():
        if time.ticks_diff(time.ticks_ms(), start) >= DURATION_MS:
            print("  Find: done (5s)")
            return

        down = (dev.button.value() == 0)
        if down and not btn_was_down:
            print("  Find: stopped by button")
            return
        btn_was_down = down

        dev.leds.show_shape(SHAPE_STAR, _RAINBOW[frame % len(_RAINBOW)])
        if frame % BEEP_EVERY_FRAMES == 0:
            dev.buz.beep(BEEP_FREQ, BEEP_MS)

        frame += 1
        dev.tick(FRAME_MS)


def main():
    import bench
    play(bench.device())


if __name__ == "__main__":
    main()
