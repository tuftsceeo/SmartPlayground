import random
import asyncio

from games.game import Game
from utilities.colors import *

class Pattern_btn(Game):
    def __init__(self, main):
        super().__init__(main, 'Pattern Game Btn')
        
    def start(self):
        self.pressed = False
        self.last_color = 0
        print("starting up ")

    async def loop(self):
        """
        Async task to wait for a message from a button and then show the color
        """
        if self.main.button.pressed:  # Button pressed
            if not self.pressed:
                self.pressed = True
                self.main.lights.all_on(WHITE, self.main.intensity)
                self.main.buzzer.play(440)
                new_color = self.last_color
                #while new_color == self.last_color:
                #new_color = random.choice(COLORS)
                new_color = self.main.color
                self.main.publish({'topic':'/color', 'value':new_color})
                self.last_color = new_color
                print('sent ', new_color)
        else:  # Button released
            self.pressed = False
            self.main.buzzer.stop()  # Silence
            self.main.lights.all_on(self.main.color, self.main.intensity)

    def close(self):
        self.main.lights.all_off() 
        self.main.buzzer.stop()




