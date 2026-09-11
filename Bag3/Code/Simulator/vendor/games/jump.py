"""
Jump Counter -- every jump lights one more LED.

A jump reads as free fall: total acceleration dropping near zero. The count
only rises; press the button to reset.

Entry point:
    play(dev)
"""

import math
import random
import time

from leds import RED, GREEN, BLUE, YELLOW, PURPLE, PINK

LOOP_MS = 40
NUM_LEDS = 25
FREEFALL_THRESHOLD = 0.3
MIN_EVENT_SPACING_MS = 1000

PICK_COLORS = (RED, GREEN, BLUE, YELLOW, PURPLE, PINK)


class JumpGame:
    def __init__(self, dev):
        self.dev = dev
        self.level = 0
        self.in_jump = False
        self.last_jump_ms = 0
        self.color = random.choice(PICK_COLORS)
        self._btn_was_down = (dev.button.value() == 0)
        dev.leds.off()
        print("  Your color: %s" % (self.color,))

    def _button_reset(self):
        down = (self.dev.button.value() == 0)
        if down and not self._btn_was_down:
            time.sleep_ms(30)
            if self.dev.button.value() == 0:
                self._btn_was_down = True
                self.level = 0
                self.in_jump = False
                self.dev.leds.off()
                return True
        elif not down and self._btn_was_down:
            self._btn_was_down = False
        return False

    def _count_jump(self):
        """Free fall, spaced out, counts as one jump."""
        x, y, z = self.dev.accel.read()
        if math.sqrt(x * x + y * y + z * z) >= FREEFALL_THRESHOLD:
            self.in_jump = False
            return
        if self.in_jump:
            return
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_jump_ms) > MIN_EVENT_SPACING_MS:
            self.level += 1
            self.last_jump_ms = now
            self.in_jump = True

    def _render(self):
        self.dev.leds.off()
        for i in range(min(self.level, NUM_LEDS)):
            row = 4 - (i // 5)
            self.dev.leds.np[row * 5 + (i % 5)] = self.color
        self.dev.leds.np.write()

    def run(self):
        print("  Jump to light more LEDs!")
        print("  Press the button to reset.\n")
        while self.dev.running():
            if not self._button_reset():
                self._count_jump()
            self._render()
            self.dev.tick(LOOP_MS)


def play(dev):
    dev.buz.start()
    print("\n  === JUMP COUNTER ===")
    JumpGame(dev).run()


def main():
    import bench
    play(bench.device())


if __name__ == "__main__":
    main()
