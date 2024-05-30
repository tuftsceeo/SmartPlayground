import neopixel
import machine

# 32 LED strip connected to X8.
p = machine.Pin.board.P0
n = neopixel.NeoPixel(p, 12)

# Draw a red gradient.
for i in range(12):
    n[i] = (i * 8, 0, 0)

# Update the strip.
n.write()
