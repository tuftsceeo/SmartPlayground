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
        self.button_released = True
        self.state = 'Upright'

    def start(self):
        self.main.lights.all_on(WHITE, INTENSITY)
              
    async def loop(self):
        """
        Async task to read the ping strength of hidden_gem.
        """
        try:
            x,y,z = self.main.accel.read_accel()
            
            if self.main.button.pressed and self.state =='Upright': # Button pressed and upright
                self.main.lights.all_off()
                while self.main.button.pressed:
                    pass
                #self.main.lights.all_on(WHITE, INTENSITY)
                self.button_count +=1
                self.main.lights.all_on(WHITE, INTENSITY, self.button_count)
                
            if self.state == 'Upright':
                if x < UPSIDEDOWN_THRESHOLD:
                    self.state = 'Upside_down'
            elif self.state == 'Upside_down':
                if x > UPRIGHT_THRESHOLD:
                    self.state = 'Upright'
                    if self.button_count < 8 :
                        print("setting lights on?")
                        self.main.lights.all_on(COLORS[8-self.button_count], INTENSITY)
                    else:
                        self.main.lights.all_on(WHITE, INTENSITY)
                    self.button_count = 0
    
        except Exception as e:
            print(e)

        
    def close(self):
        self.main.lights.all_off() 
        

