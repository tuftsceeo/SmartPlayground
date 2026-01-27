# Series of different color buttons - when you press the button, one LED of that color shows up on all the stuffies
# goes with pattern_rainbow_plushie

import random
import asyncio

from games.game import Game
from utilities.colors import *

FIFO = 12

class Pattern_plush(Game):
    def __init__(self, main):
        super().__init__(main, 'Pattern Game Plush')
        
    def start(self):
        self.main.lights.all_on(WHITE, 0.01)
        print("starting up ")
        self.pattern = []
        self.old_color = -1

    async def loop(self):
        """
        Async task to wait for a message from a button and then show the color from the message
        """
        if self.main.topic == '/color':  #might be better to just look at self.value...
            new_color = self.main.tool.color
            if new_color != self.old_color:
                self.pattern.append(new_color)
                self.pattern = self.pattern[-FIFO:]
                for i, c in enumerate(self.pattern):
                    self.main.lights.on(i, c, self.main.tool.intensity)
                self.old_color = new_color

    def close(self):
        self.main.lights.all_off() 
        self.main.buzzer.stop()




