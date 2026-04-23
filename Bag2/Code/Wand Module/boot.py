from neopixel import NeoPixel
from machine import Pin
np = NeoPixel(Pin(20), 25)
np[0] = [5,5,5]
np.write()