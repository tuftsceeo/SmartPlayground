import random
import math
import asyncio
import time

from games.game import Game
from utilities.colors import *

INTENSITY = 0.1

class Rainbow(Game):
    def __init__(self, main):
        super().__init__(main, 'Rainbow Game')
        
    def start(self):
        self.bat = int(self.main.battery.read()/100*12)
        self.bat = max(1, min(self.bat,12))
        print('Battery: ',self.bat)
        self.main.lights.all_on(GREEN, 0.1, self.bat)
        time.sleep(2)
        for i in range(12):
            self.main.lights.on(i, COLORS[i%7], INTENSITY)
            
    async def loop(self):
        if self.main.topic == '/notify':
            self.start()
            self.main.topic = ''

    def close(self):
        self.main.lights.all_off()
        #if not self.main.button.pressed:
        #    self.main.utilities.hibernate()
