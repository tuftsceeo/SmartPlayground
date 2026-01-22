import time

from games.game import Game
from utilities.colors import *

INTENSITY = 0.1

class Hibernate(Game):
    def __init__(self, main):
        super().__init__(main, 'Hibernate Game')
        
    def start(self):
        for i in range(5):
            self.main.lights.all_on(RED, 0.1, 12)
            time.sleep(0.5)
            self.main.lights.all_off()
            time.sleep(0.5)
        if not self.main.button.pressed:
            self.main.hibernate.hibernate()
            
    async def loop(self):
        if self.main.topic == '/notify':
            self.start()
            self.main.topic = ''

    def close(self):
        self.main.lights.all_off()

