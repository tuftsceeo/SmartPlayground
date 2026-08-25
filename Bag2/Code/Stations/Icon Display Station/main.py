import machine
import neopixel
import time
import os
import sys

sys.path.append("icons")

DATA_PIN = 0
GRID_W = 16
GRID_H = 16
NUM_PIXELS = GRID_W * GRID_H
INTENSITY = 0.25

strip = neopixel.NeoPixel(machine.Pin(DATA_PIN), NUM_PIXELS)


def pixel_index(col, row):
    c = col if (row % 2 == 0) else (GRID_W - 1 - col)
    return row * GRID_W + c


def scale(rgb):
    return tuple(int(c * INTENSITY) for c in rgb)


def draw(pixels):
    for row in range(GRID_H):
        for col in range(GRID_W):
            strip[pixel_index(col, row)] = scale(pixels[row * GRID_W + col])
    strip.write()


def clear():
    for i in range(NUM_PIXELS):
        strip[i] = (0, 0, 0)
    strip.write()


def setup():
    clear()


def loop():
    time.sleep_ms(500)


def cycle_icons(hold_ms=2000):
    for fn in os.listdir("icons"):
        if not fn.endswith(".py"):
            continue
        name = fn[:-3]
        mod = __import__(name)
        print("showing", name)
        draw(mod.ICON)
        time.sleep_ms(hold_ms)


def main():
    setup()
    while True:
        cycle_icons(hold_ms=4000)


if __name__ == "__main__":
    main()
