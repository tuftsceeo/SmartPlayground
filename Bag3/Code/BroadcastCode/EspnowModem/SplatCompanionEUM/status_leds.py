"""
status_leds.py -- companion status LEDs (NeoPixel strip)
========================================================
show(color, breathe, now) writes the strip only when the output changes.
Breathe is a 2 s triangle wave from 10 % to 100 % of color.
"""

import machine
import neopixel

BREATHE_PERIOD_MS = 2000


class StatusLeds:
    def __init__(self, pin, num):
        self.np = neopixel.NeoPixel(machine.Pin(pin), num)
        self._last = None

    def show(self, color, breathe, now):
        if breathe:
            half = BREATHE_PERIOD_MS // 2
            ph = now % BREATHE_PERIOD_MS
            k = ph if ph < half else BREATHE_PERIOD_MS - ph
            k = 100 + 900 * k // half            # per mille, 100..1000
            color = (color[0] * k // 1000, color[1] * k // 1000,
                     color[2] * k // 1000)
        if color != self._last:
            self._last = color
            self.np.fill(color)
            self.np.write()

    def off(self):
        self._last = None
        self.np.fill((0, 0, 0))
        self.np.write()
