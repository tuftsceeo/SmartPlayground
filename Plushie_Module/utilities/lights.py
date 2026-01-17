import neopixel
from machine import Pin
import asyncio

NUM_LED = 12
LED_PIN = 20

from utilities.colors import *

class Lights():
    def __init__(self):
        self.np = neopixel.NeoPixel(Pin(LED_PIN), NUM_LED)
        self.default_color = RED
        self.default_intensity = 1
        self.last_pattern = [0]*12
        
    def defaults(self, color = None, intensity = None):
        color = color if color else self.default_color
        intensity = intensity  if intensity else self.default_intensity
        return color, intensity

    def on(self, num, color = None, intensity = None):
        color, intensity = self.defaults(color, intensity)
        if num < NUM_LED:
            self.np[num] = [int(c*intensity) for c in color]
            self.last_pattern[num] = self.np[num]
            self.np.write()
            
    def all_on(self, color = None, intensity = None, number = NUM_LED):
        color, intensity = self.defaults(color, intensity)
        for i in range(number):
            self.np[i] = [int(c*intensity) for c in color]
            self.last_pattern[i] = self.np[i]
        self.np.write()
        
    def array_on(self, colors = [], intensity = None):
        _, intensity = self.defaults(None, intensity)
        for i,color in enumerate(colors):
            self.np[i] = [int(c*intensity) for c in color]
            self.last_pattern[i] = self.np[i]
        self.np.write()
        
    def off(self, num):
        self.on(num, [0,0,0])
        
    def all_off(self, num = NUM_LED):
        for i in range(NUM_LED):
            self.np[i] = OFF
            self.last_pattern[i] = self.np[i]
        self.np.write()
        
    async def animate(self, color = None, intensity = None, number = NUM_LED, repeat= 1, timeout = 1.0, speed = 0.1):
        color, intensity = self.defaults(color, intensity)
        for j in range(repeat):
            for i in range(number):
                self.on(i, color, intensity)
                self.off(i+1)
                await asyncio.sleep(speed)
            
        if timeout > 0.0:
            #turn off all LEDs
            await asyncio.sleep(timeout)
            self.all_off()

    def show_number(self, number, color = None, intensity = None):
        color, intensity = self.defaults(color, intensity)
        for i in range(NUM_LED):
            self.np[i] = [int(c*intensity) for c in color] if (i == number) else OFF
            self.last_pattern[i] = self.np[i]
        self.np.write()

