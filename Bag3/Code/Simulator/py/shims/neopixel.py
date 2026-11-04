"""
Fake `neopixel.NeoPixel` — stores pixels and pushes frames to sim_state.
"""

import sim_state


class NeoPixel:
    def __init__(self, pin, n, bpp=3, timing=1):
        self.pin = pin
        self.n = n
        self.bpp = bpp
        self._buf = [(0, 0, 0)] * n

    def __setitem__(self, i, color):
        self._buf[i] = tuple(color)

    def __getitem__(self, i):
        return self._buf[i]

    def __len__(self):
        return self.n

    def fill(self, color):
        c = tuple(color)
        for i in range(self.n):
            self._buf[i] = c

    def write(self):
        sim_state.emit_led_frame(self._buf)
