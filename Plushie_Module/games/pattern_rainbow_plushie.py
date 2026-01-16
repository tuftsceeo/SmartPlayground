import random
import asyncio

from games.game import Game
from utilities.colors import *

INTENSITY = 0.1
FIFO = 12

class Pattern_plush(Game):
    def __init__(self, main):
        super().__init__(main, 'Pattern Game Plush')
        
    def start(self):
        self.main.lights.all_on(WHITE, INTENSITY)
        print("starting up ")
        pattern = []

    async def loop(self):
        """
        Async task to wait for a message from a button and then show the color from the message
        """
        if self.main.topic == '/color':
            new_color = self.main.value
            if new_color != old_color:
                pattern.append(new_color)
                pattern = pattern[-FIFO:]
                self.main.lights.all_on(pattern, INTENSITY)
                old_color = new_color
        if self.main.button.pressed:  # Button pressed
            self.main.buzzer.play(440)
        else:  # Button released
            self.main.buzzer.stop()  # Silence

    def close(self):
        self.main.lights.all_off() 
        self.main.buzzer.stop()



