import random
import asyncio

from games.game import Game
from utilities.colors import *

INTENSITY = 1

class Pattern_btn(Game):
    def __init__(self, main):
        super().__init__(main, 'Pattern Game Btn')
        
    def start(self):
        self.main.lights.all_on(WHITE, INTENSITY)
        print("starting up ")

    async def loop(self):
        """
        Async task to wait for a message from a button and then show the color
        """
        if self.main.button.pressed:  # Button pressed
            self.main.buzzer.play(440)
            #send out over NOW a new random color
            self.main.espnow.publish(json.dumps({'topic':'/color', 'value':2}))
            self.main.lights.all_on(random.choice(COLORS), INTENSITY)
        else:  # Button released
            self.main.buzzer.stop()  # Silence

    def close(self):
        self.main.lights.all_off() 
        self.main.buzzer.stop()


