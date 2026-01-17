import random
import asyncio

from games.game import Game
from utilities.colors import *

INTENSITY = 1

class Pattern_btn(Game):
    def __init__(self, main):
        super().__init__(main, 'Pattern Game Btn')
        
    def start(self):
        self.pressed = False
        self.main.lights.all_on(WHITE, INTENSITY)
        print("starting up ")

    async def loop(self):
        """
        Async task to wait for a message from a button and then show the color
        """
        if self.main.button.pressed:  # Button pressed
            if not self.pressed:
                self.pressed = True
                self.main.buzzer.play(440)
                self.main.publish({'topic':'/color', 'value':random.choice(COLORS)})
        else:  # Button released
            self.pressed = False
            self.main.buzzer.stop()  # Silence

    def close(self):
        self.main.lights.all_off() 
        self.main.buzzer.stop()



