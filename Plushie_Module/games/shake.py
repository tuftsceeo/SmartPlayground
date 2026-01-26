# shake to fill - harder you shake the more LEDs light up - can't go back - so always shows the greatest

import random
import math
import asyncio

from games.game import Game
from utilities.colors import *

#  ALL ESPNow happens in main.py

class Shake(Game):
    def __init__(self, main):
        super().__init__(main, 'Shakes Game')
        
    def start(self):
        self.color = random.choice(COLORS)
        print(f'your color is {self.color}')
        self.level = 0
        
    def accel_mag(self):
        x,y,z = self.main.accel.read_accel()
        return math.sqrt(x**2+y**2+z**2) - 1
        

    async def loop(self):
        """
        Async task to play increase the number of leds shown with how
        vigorous you shake.  Hitting the button resets
        """
        if self.main.button.pressed:  # Button pressed
            self.level = 0
            self.main.lights.all_off()
        else:  # Button released
            acc = min(self.main.tool.num_of_leds, int(self.accel_mag()**3*1.5))
            if self.level < acc: self.level = acc
            self.main.lights.all_on(self.color, 0.1, self.level)

    def close(self):
        self.main.lights.all_off()
