import random
import math
import asyncio
import time

from games.game import Game
from utilities.colors import *

class Clap(Game):
    def __init__(self, main):
        super().__init__(main, 'Clap Game')
        
    def start(self):
        self.main.lights.all_off()
        self.maxled = self.main.tool.num_of_leds-1
        
    async def loop(self):
        if self.main.topic == '/notify':
            try:
                strength = self.main.rssi[self.main.hidden_gem][0]
                s = int(-self.maxled * (strength+20)/50)   # assuming -60dB to -10dB is the best
                strength = max(0, min(s, self.maxled))
                print('strength = ',strength)
                self.main.lights.all_off()
                self.main.lights.all_on(RED, self.main.tool.intensity, self.maxled+1-strength)
                if strength < int((self.maxled+1)/2):
                    self.main.buzzer.play(440)
                    time.sleep(1)
                    self.main.buzzer.stop()
                self.main.topic = '/null'
            except Exception as e:
                print(e)

    def close(self):
        self.main.lights.all_off()
        self.main.buzzer.stop()



