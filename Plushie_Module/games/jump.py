import random
import math
import asyncio
import time 

from games.game import Game
from utilities.colors import *

FREEFALL_THRESHOLD = 0.3  # Magnitude below this = free fall (adjust as needed)
MIN_EVENT_SPACING = 1000   # Minimum ms between jumps (prevents double-counting)

class Jump(Game):
    def __init__(self, main):
        super().__init__(main, 'Jump Game')
        
    def start(self):
        self.color = random.choice(COLORS)
        print(f'your color is {self.color}')
        self.level = 0
        
        print("jumping")
        self.in_jump = False
        self.last_jump_time = 0

    async def loop(self):
        """
        Async task to play increase the number of leds shown with every
        jump.  Hitting the button resets
        """
        if self.main.button.pressed:  # Button pressed
            self.level = 0
            self.main.lights.all_off()
        else:  # Button released
            x,y,z = self.main.accel.read_accel()
            current_time = time.ticks_ms()
            magnitude = (x**2 + y**2 + z**2)**0.5
            if magnitude < FREEFALL_THRESHOLD:
                if not self.in_jump:
                    if time.ticks_diff(current_time, self.last_jump_time) > MIN_EVENT_SPACING:
                        self.level += 1
                        self.last_jump_time = current_time
                        self.in_jump = True
                else:
                    if self.in_jump:
                        self.in_jump = False

            self.level = self.level%12
            self.main.lights.all_on(self.color, 0.1, self.level)

    def close(self):
        self.main.lights.all_off()
        

