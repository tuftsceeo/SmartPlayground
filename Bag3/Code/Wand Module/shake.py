"""
Shake Fill -- shake harder to light more of the matrix.

The level only rises, so it holds your best shake. Press the button to reset.

Entry point:
    play(dev)
"""

import math
import random
import time

from leds import RED, GREEN, BLUE, YELLOW, PURPLE, PINK

LOOP_MS = 40
NUM_LEDS = 25
PICK_COLORS = (RED, GREEN, BLUE, YELLOW, PURPLE, PINK)


class ShakeGame:
    def __init__(self, dev):
        self.dev = dev
        self.level = 0
        self.color = random.choice(PICK_COLORS)
        self._btn_was_down = (dev.button.value() == 0)
        print("  Your color: %s" % (self.color,))

    def _accel_mag(self):
        x, y, z = self.dev.accel.read()
        return math.sqrt(x * x + y * y + z * z) - 1

    def _button_reset(self):
        """True on a fresh press, having cleared the level."""
        down = (self.dev.button.value() == 0)
        if down and not self._btn_was_down:
            time.sleep_ms(30)
            if self.dev.button.value() == 0:
                self._btn_was_down = True
                self.level = 0
                self.dev.leds.off()
                return True
        elif not down and self._btn_was_down:
            self._btn_was_down = False
        return False

    def _render(self):
        """Fill from the bottom row up."""
        self.dev.leds.off()
        for i in range(min(self.level, NUM_LEDS)):
            row = 4 - (i // 5)
            self.dev.leds.np[row * 5 + (i % 5)] = self.color
        self.dev.leds.np.write()

    def run(self):
        print("  Shake harder to fill the matrix!")
        print("  Press the button to reset.\n")
        while self.dev.running():
            if not self._button_reset():
                peak = min(NUM_LEDS, int(self._accel_mag() ** 3 * 1.5))
                if self.level < peak:
                    self.level = peak
            self._render()
            self.dev.tick(LOOP_MS)


def play(dev):
    dev.buz.start()
    print("\n  === SHAKE FILL ===")
    ShakeGame(dev).run()


def main():
    import bench
    play(bench.device())


if __name__ == "__main__":
    main()
