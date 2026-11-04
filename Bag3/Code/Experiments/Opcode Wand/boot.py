from neopixel import NeoPixel
from machine import Pin
np = NeoPixel(Pin(20), 60)
np[0] = [5,5,5]
np.write()