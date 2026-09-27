"""
status_leds.py -- companion status LEDs (NeoPixel strip)
========================================================
show(color, breathe, now) writes the strip only when the output changes,
for the idle station's status colors (see companion.py). fill()
is the same 3-LED strip made available to games as the `leds` parameter --
it always writes, since a game's own animation may repeat a color on
purpose (a blink), which show()'s dedup would otherwise swallow.
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

    def fill(self, color):
        """Unconditional solid write, for a game's own animation. Clears
        the dedup state show() uses, so the idle loop repaints on resume
        instead of trusting a color a game may have left behind."""
        self._last = None
        self.np.fill(color)
        self.np.write()
