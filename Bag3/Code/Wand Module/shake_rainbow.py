"""
Shake Rainbow -- shake to climb the rainbow, one colour at a time.

The colour only advances, so it holds your best shake. Press the button to go
back to the start.

Entry point:
    play(dev)
"""

import math
import time

from leds import WHITE, RED, ORANGE, YELLOW, GREEN, BLUE, PURPLE, PINK

LOOP_MS = 40
SHAKE_THRESHOLD = 0.15
ACC_MAX = 10.0

COLORS = (WHITE, RED, ORANGE, YELLOW, GREEN, BLUE, PURPLE, PINK)


class ShakeRainbowGame:
    def __init__(self, dev):
        self.dev = dev
        self.level = 0
        self._btn_was_down = (dev.button.value() == 0)
        dev.leds.off()

    def _accel_mag(self):
        x, y, z = self.dev.accel.read()
        return math.sqrt(x * x + y * y + z * z) - 1

    def _button_reset(self):
        """True on a fresh press, having gone back to the first colour."""
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

    def _shake_level(self):
        """Rainbow index for the current shake, 0 when below the threshold."""
        raw = self._accel_mag()
        if raw <= SHAKE_THRESHOLD:
            return 0
        acc = min(ACC_MAX, max(0, (raw ** 2) * 1.5))
        return int((acc / ACC_MAX) * (len(COLORS) - 1))

    def run(self):
        print("  Shake to change colours through the rainbow!")
        print("  Press the button to reset.\n")
        while self.dev.running():
            if not self._button_reset():
                level = self._shake_level()
                if level > self.level:
                    self.level = level
            self.dev.leds.fill(COLORS[self.level])
            self.dev.tick(LOOP_MS)


def play(dev):
    dev.buz.start()
    print("\n  === SHAKE RAINBOW ===")
    ShakeRainbowGame(dev).run()


def main():
    import bench
    play(bench.device())


if __name__ == "__main__":
    main()
