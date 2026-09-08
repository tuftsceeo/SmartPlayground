# Earliest sign of life: one dim pixel before main.py imports anything.
# Pin and length are the wand's own -- every device tree has its own boot.py.
from neopixel import NeoPixel
from machine import Pin

_np = NeoPixel(Pin(20), 25)
_np[0] = (5, 5, 5)
_np.write()
