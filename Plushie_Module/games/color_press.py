import time, json
import asyncio

from games.game import Game
from utilities.colors import *

INTENSITY = 0.1
UPRIGHT_THRESHOLD = 0.7   # x > 0.7 means upright
UPSIDEDOWN_THRESHOLD = -0.7  # x < -0.7 means upside down
TARGET_COLOR = YELLOW # Change color for each animal


class Color_Press(Game):
    def __init__(self, main):
        super().__init__(main, 'color_press')
        self.button_count = 0
        self.button_released = True
        self.state = 'Upright'

    def _log(self, message):
        try:
            self.main.log_message(f"[COLOR_PRESS] {message}")
        except:
            print(message)

    def start(self):
        self._log("Game started")
        self.main.lights.all_on(WHITE, INTENSITY)

    async def loop(self):
        try:
            x,y,z = self.main.accel.read_accel()

            if self.main.button.pressed and self.state =='Upright': # Button pressed and upright
                self.main.lights.all_off()
                while self.main.button.pressed:
                    pass
                self.button_count +=1
                self._log(f"Button pressed | count={self.button_count}")
                self.main.lights.all_on(WHITE, INTENSITY, self.button_count)

            if self.state == 'Upright':
                if x < UPSIDEDOWN_THRESHOLD:
                    self.state = 'Upside_down'
                    self._log(f"Flip → Upside_down | x={x:+.3f}")
            elif self.state == 'Upside_down':
                if x > UPRIGHT_THRESHOLD:
                    self.state = 'Upright'
                    self._log(f"Flip → Upright | x={x:+.3f} | button_count={self.button_count}")
                    if self.button_count < 8 :
                        color = COLORS[8-self.button_count]
                        self._log(f"Color selected | count={self.button_count} → color_index={8-self.button_count}")
                        self.main.lights.all_on(color, INTENSITY)
                        if color == TARGET_COLOR:
                            self._log("TARGET_COLOR matched → blink + rainbow")
                            await asyncio.sleep(0.5)
                            for _ in range(5):
                                self.main.lights.all_off()
                                await asyncio.sleep(0.2)
                                self.main.lights.all_on(TARGET_COLOR, INTENSITY)
                                await asyncio.sleep(0.2)
                            for i in range(12):
                                self.main.lights.on(i, COLORS[i % 7], INTENSITY)
                            self._log("Rainbow displayed")
                    else:
                        self._log(f"Color selected | count={self.button_count} → WHITE (overflow)")
                        self.main.lights.all_on(WHITE, INTENSITY)
                    self.button_count = 0

        except Exception as e:
            print(e)

        
    def close(self):
        self._log(f"Game closed | final button_count={self.button_count}")
        self.main.lights.all_off()
        

