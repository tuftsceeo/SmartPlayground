# shake to fill - harder you shake the closer you get to purple (ROYGBIV) - all the LEDs light up

import math
import asyncio

from games.game import Game
from utilities.colors import *

SHAKE_COLOR_RANGE = [WHITE, RED, ORANGE, YELLOW, GREEN, BLUE, INDIGO, VIOLET]


class Shake_Rainbow(Game):
    def __init__(self, main):
        super().__init__(main, 'Shake Rainbow')

    def start(self):
        print("Shake the plushy to change colors!")

        self.current_level = 0
        self.current_color = SHAKE_COLOR_RANGE[self.current_level]

        self.shake_threshold = 0.15 
        self.acc_max = 10.0

    def accel_mag(self):
        x, y, z = self.main.accel.read_accel()
        return math.sqrt(x**2 + y**2 + z**2) - 1

    async def loop(self):
        if self.main.button.pressed:
            self.current_level = 0
            self.current_color = SHAKE_COLOR_RANGE[self.current_level]
            self.main.lights.all_off()
            return

        acc_raw = self.accel_mag()

        if acc_raw > self.shake_threshold:
            # Shape + clamp
            acc = (acc_raw ** 2) * 1.5
            acc = max(0.0, min(self.acc_max, acc))

            n = len(SHAKE_COLOR_RANGE)
            level = int((acc / self.acc_max) * (n - 1))
            level = max(0, min(n - 1, level))

            # Only change color when the level changes
            if level > self.current_level:
                self.current_level = level
                self.current_color = SHAKE_COLOR_RANGE[level]

        # Always show the stored (sticky) color
        self.main.lights.all_on(self.current_color, 0.1)

    def close(self):
        self.main.lights.all_off()
