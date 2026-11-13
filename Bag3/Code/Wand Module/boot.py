# Power-on feedback before main.py brings the radio up: one dim pixel on
# the wand's 25-pixel matrix (GPIO20). AGENTS.md radio-first exception;
# add nothing else here. main.py's leds.py re-inits the same pin.
from neopixel import NeoPixel
from machine import Pin
np = NeoPixel(Pin(20), 25)
np[0] = (5, 5, 5)
np.write()
del np, NeoPixel, Pin
