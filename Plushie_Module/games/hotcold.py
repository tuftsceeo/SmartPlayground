import time, json

from games.game import Game
from utilities.colors import *

INTENSITY = 0.1

class Hot_cold(Game):
    def __init__(self, main):
        super().__init__(main, 'Hot/Cold Game')
        
    def start(self):
        self.main.lights.all_off()
        
    async def loop(self):
        """
        Async task to read the ping strength of hidden_gem.
        """
        try:
            if not self.main.rssi:
                return
            strength = self.main.rssi[self.main.hidden_gem][0]
            s = int(-11 * (strength+20)/50)   # assuming -60dB to -10dB is the best
            strength = max(0, min(s, 11))
            print('strength = ',strength)
            self.main.lights.all_off()
            self.main.lights.all_on(RED, INTENSITY, 11-strength)
        except Exception as e:
            print(e)

        
    def close(self):
        self.main.lights.all_off() 
        