"""
Jump In -- press the button, the matrix blinks green.

The simplest complete game, and the template for a new one:

    def play(dev):
        while dev.running():
            ...
            dev.tick(50)

dev.running() pumps the radio and the card reader, so the game does not check
for stop itself: it goes False on an ESP-NOW stop, a start for another game,
or an exit tag. dev restores the LEDs when play() returns.

Entry points:
    play(dev)  -- called by main.py
    main()     -- run one game at the REPL, see bench.py
"""

import time

from leds import GREEN

BLINK_ON_MS = 200
BLINK_OFF_MS = 200
LOOP_MS = 50


def play(dev):
    dev.buz.beep(523, 100)
    print("\n  === BUTTON BLINK MODE ===")
    print("  Press the button to blink green.")

    while dev.running():
        if dev.button.value() == 0:
            print("  Button pressed!")
            dev.leds.fill(GREEN)
            time.sleep_ms(BLINK_ON_MS)
            dev.leds.off()
            time.sleep_ms(BLINK_OFF_MS)
        dev.tick(LOOP_MS)


def main():
    import bench
    play(bench.device())


if __name__ == "__main__":
    main()
