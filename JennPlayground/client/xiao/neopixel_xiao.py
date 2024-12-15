import time
import board
import neopixel
import math


pixels = neopixel.NeoPixel(board.D0, 10)

def color_wheel(pos):
    # Generate rainbow colors across 0-255 positions for neopixel
    if pos < 85:
        return (pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return (255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return (0, pos * 3, 255 - pos * 3)


run_for = 20
start = time.monotonic()
i=1
while time.monotonic() - start < 1000*run_for:
# Draw a red gradient.
    pixels.fill(color_wheel(i))
    i=(i+1)%255
    pixels.write()
    time.sleep(.05)
    print(i)
