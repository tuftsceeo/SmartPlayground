import neopixel
from machine import Pin
import asyncio


LED_PIN = 20

from utilities.colors import *

class Lights:
    def __init__(self, num_of_leds = 12):
        self.NUM_LED = num_of_leds
        self.np = neopixel.NeoPixel(Pin(LED_PIN), self.NUM_LED)
        self.color = RED
        self.intensity = 1
        self.last_pattern = [0]*self.NUM_LED
        
        
    def defaults(self, color = None, intensity = None):
        color = color if color else self.color
        intensity = intensity  if intensity else self.intensity
        return color, intensity


    def on(self, num, color = None, intensity = None):
        color, intensity = self.defaults(color, intensity)
        if num < self.NUM_LED:
            self.np[num] = [int(c*intensity) for c in color]
            self.last_pattern[num] = self.np[num]
            self.np.write()
            
    def all_on(self, color = None, intensity = None, number = None ):
        if number is None:
            number = self.NUM_LED
        color, intensity = self.defaults(color, intensity)
        for i in range(number):
            self.np[i] = [int(c*intensity) for c in color]
            self.last_pattern[i] = self.np[i]
        self.np.write()
        
    def array_on(self, colors = []):
        for i,color in enumerate(colors):
            self.np[i] = color
            self.last_pattern[i] = self.np[i]
        self.np.write()
        
    def off(self, num):
        self.on(num, [0,0,0])
        
    def all_off(self, number = None):
        if number is None:
            number = self.NUM_LED
        for i in range(number):
            self.np[i] = OFF
            self.last_pattern[i] = self.np[i]
        self.np.write()
        
    async def animate(self, color = None, intensity = None, number = None, repeat= 1, timeout = 1.0, speed = 0.1):
        if number is None:
            number = self.NUM_LED
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
        for i in range(self.NUM_LED):
            self.np[i] = [int(c*intensity) for c in color] if (i == number) else OFF
            self.last_pattern[i] = self.np[i]
        self.np.write()

