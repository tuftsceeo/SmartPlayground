# Earliest sign of life: one dim pixel before main.py imports anything.
# Pin and length are this station's own -- every device tree has its own
# boot.py. The Matrix main.py builds takes the same pin over afterwards.
from neopixel import NeoPixel
from machine import Pin

_np = NeoPixel(Pin(0), 256)
_np[0] = (5, 5, 5)
_np.write()
