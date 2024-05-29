import neopixel
import machine
import time


# 32 LED strip connected to X8.
p = machine.Pin.board.P0
n = neopixel.NeoPixel(p, 12)

def color_wheel(pos):
    # Generate rainbow colors across 0-255 positions
    if pos < 85:
        return (pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return (255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return (0, pos * 3, 255 - pos * 3)


run_for = 20
start = time.ticks_ms()
i=1
while time.ticks_diff(time.ticks_ms(), start) < 1000*run_for:
# Draw a red gradient.
    n.fill(color_wheel(i))
    n
    i=(i+1)%255
    n.write()
    time.sleep(.05)
    print(i)
