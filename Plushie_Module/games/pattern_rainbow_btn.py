import random
import asyncio

from games.game import Game

class pattern(Game):
    def __init__(self, main):
        super().__init__(main, 'Pattern Game Btn')
        
    def start(self):
        self.main.lights.all_on(PURPLE, 0.1)
        print("starting up ")

    async def loop(self):
        """
        Async task to wait for a message from a button and then show the color
        """
        if self.main.button.pressed:  # Button pressed
            self.main.buzzer.play(440)
        else:  # Button released
            self.main.buzzer.stop()  # Silence

    def close(self):
        self.main.lights.all_off() 
        self.main.buzzer.stop()


