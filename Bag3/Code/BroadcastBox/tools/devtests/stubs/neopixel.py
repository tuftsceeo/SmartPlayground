"""Stub: MicroPython neopixel. Records writes so a test can inspect frames."""
class NeoPixel:
    ORDER = (1, 0, 2, 3)
    def __init__(self, pin, n):
        self.n = n
        self.buf = bytearray(n * 3)
        self.writes = 0
    def __setitem__(self, i, v):
        o = i * 3
        self.buf[o], self.buf[o + 1], self.buf[o + 2] = v
    def __getitem__(self, i):
        o = i * 3
        return tuple(self.buf[o:o + 3])
    def write(self):
        self.writes += 1
