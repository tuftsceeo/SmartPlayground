from neopixel import NeoPixel
from machine import Pin
np = NeoPixel(Pin(20), 60)
np[0] = [5,5,5]
np.write()

# BENCH: earliest possible heap reading, before main.py exists at all.
# lib/memprobe.py is bench-only -- see its docstring. Not in the fielded
# wand baseline (Bag3/Code/Wand Module/ has no boot.py probe call). /lib
# is already on sys.path on this port, same as main.py's `from hubtype
# import ...` relies on.
try:
    import memprobe
    memprobe.probe("boot")
except Exception as e:
    print("  [BENCH] memprobe unavailable at boot:", e)