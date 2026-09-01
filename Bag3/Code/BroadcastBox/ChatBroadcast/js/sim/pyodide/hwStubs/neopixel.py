"""Browser stub for MicroPython neopixel — paints via JS callback."""

from js import _js_paint_leds

BLACK = (0, 0, 0)
_pixels = [BLACK] * 25


def reset_pixels():
    global _pixels
    _pixels = [BLACK] * 25


def get_pixels():
    return list(_pixels)


def flush_pixels():
    out = []
    for r, g, b in _pixels:
        out.append("rgb({},{},{})".format(int(r), int(g), int(b)))
    _js_paint_leds(out)


class NeoPixel:
    def __init__(self, pin, n):
        self.pin = pin
        self.n = min(int(n), 25)

    def __setitem__(self, i, color):
        if 0 <= i < self.n:
            if isinstance(color, (list, tuple)) and len(color) >= 3:
                _pixels[i] = (int(color[0]), int(color[1]), int(color[2]))
            else:
                _pixels[i] = color

    def __getitem__(self, i):
        return _pixels[i]

    def __len__(self):
        return self.n

    def fill(self, color):
        c = color
        if isinstance(color, (list, tuple)) and len(color) >= 3:
            c = (int(color[0]), int(color[1]), int(color[2]))
        for i in range(self.n):
            _pixels[i] = c

    def write(self):
        flush_pixels()
