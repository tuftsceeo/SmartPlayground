import time, json

from games.game import Game
from utilities.colors import *

INTENSITY = 0.1
UPRIGHT_THRESHOLD = 0.7   # x > 0.7 means upright
UPSIDEDOWN_THRESHOLD = -0.7  # x < -0.7 means upside down

class Color_Press(Game):
    def __init__(self, main):
        super().__init__(main, 'color_press')
        self.button_count = 0
        self.state = 'Upright'
        
    def start(self):
        self.main.lights.all_on(WHITE, INTENSITY)
        
        
    async def loop(self):
        """
        Async task to read the ping strength of hidden_gem.
        """
        try:
            
            x,y,z = self.main.accel.read_accel()
            
            if self.main.button.pressed and self.state =='Upright':  # Button pressed and upright
                self.main.lights.all_on(WHITE, INTENSITY)
                self.button_count +=1
            
            if self.state == 'Upright':
                if x < UPSIDEDOWN_THRESHOLD:
                    self.state = 'Upside_down'
            elif self.state == 'Upside_down':
                if x > UPRIGHT_THRESHOLD:
                    self.state = 'Upright'
                    print("button count:", self.button_count)
                    if self.button_count < 7 :
                        self.main.lights.all_on(COLORS[8-self.button_count], INTENSITY)
                    self.button_count = 0
                    
                    
        except Exception as e:
            print(e)

        
    def close(self):
        self.main.lights.all_off() 
        

