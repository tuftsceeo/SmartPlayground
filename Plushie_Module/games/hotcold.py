import time, json

from games.game import Game
from utilities.colors import *

class Hot_cold(Game):
    def __init__(self, main):
        super().__init__(main, 'Hot/Cold Game')
        
    def start(self):
        self.main.lights.all_off()
        self.maxleds = self.main.tool.num_of_leds -1
        
    async def loop(self):
        """
        Async task to read the ping strength of hidden_gem.
        """
        try:
            if not self.main.rssi:
                return
            strength = self.main.rssi[self.main.hidden_gem][0]
            s = int((-self.maxleds) * (strength+20)/50)   # assuming -60dB to -10dB is the best
            strength = max(0, min(s, self.maxleds))
            print('strength = ',strength)
            self.main.lights.all_off()
            self.main.lights.all_on(RED, self.main.tool.intensity, self.maxleds-strength)
        except Exception as e:
            print(e)

        
    def close(self):
        self.main.lights.all_off() 
        