"""
bars.py -- this station's hardware: a bar-graph board.

Verbs, over ESP-NOW "cap" messages addressed to hubtype score_station:

    push  {v, c}   add value v, drawn in colour name c
    clear          empty the board
    scale {mode}   "low" = smaller value is a taller bar (a race time),
                   "high" = larger value is taller (a count)

The board holds the last `bars` values and renders them relative to the best
one. It has no opinion about what a value means; the caller supplies the
colour. Arrival animation is stepped from the station loop, not slept through,
so the radio keeps being serviced while it runs.
"""

import random
import time

import neopixel
from machine import Pin

from hubtype import HUB_CONFIG

BRIGHTNESS = 0.8
MIN_ROWS = 2

COLORS = {
    "red":    (255, 0, 0),
    "green":  (0, 255, 0),
    "blue":   (0, 0, 255),
    "purple": (160, 0, 200),
    "yellow": (220, 220, 0),
    "cyan":   (0, 220, 220),
    "pink":   (220, 0, 220),
    "orange": (255, 80, 0),
    "white":  (200, 200, 200),
}

RAINBOW = ((255, 0, 0), (255, 100, 0), (200, 200, 0),
           (0, 255, 0), (0, 0, 255), (130, 0, 255))

# Arrival animation: (phase name, frames, ms per frame). Same shape and timing
# as the Bag2 station, driven by step() instead of sleep_ms.
SPARKLE, WIPE, HOLD, FILL, REST = range(5)
PHASES = ((SPARKLE, 9, 50), (WIPE, 10, 27), (HOLD, 1, 150),
          (FILL, 10, 30), (REST, 1, 280))


def _dim(rgb):
    return (int(rgb[0] * BRIGHTNESS), int(rgb[1] * BRIGHTNESS), int(rgb[2] * BRIGHTNESS))


class ScoreBars:

    def __init__(self):
        self.bars = HUB_CONFIG["bars"]
        self.height = HUB_CONFIG["bar_height"]
        self.serpentine = HUB_CONFIG["serpentine"]
        self.strip = neopixel.NeoPixel(Pin(HUB_CONFIG["led_pin"]),
                                       HUB_CONFIG["num_leds"])
        self.scores = []          # [(value, rgb)], newest last, at most `bars`
        self.low_wins = True
        self._phase = None        # index into PHASES while animating
        self._frame = 0
        self._due = 0
        self._col = 0
        self.off()

    # -- capability interface ----------------------------------------

    def handle(self, op, args):
        if op == "push":
            self.push(args["v"], args.get("c", "white"))
        elif op == "clear":
            self.clear()
        elif op == "scale":
            self.set_scale(args["mode"])
        else:
            raise ValueError("score_station: unknown op %r" % op)

    def step(self):
        """Advance the arrival animation. Returns at once when idle."""
        if self._phase is None:
            return
        if time.ticks_diff(time.ticks_ms(), self._due) < 0:
            return
        kind, frames, ms = PHASES[self._phase]
        self._draw_phase(kind, self._frame)
        self._frame += 1
        self._due = time.ticks_add(time.ticks_ms(), ms)
        if self._frame >= frames:
            self._phase += 1
            self._frame = 0
            if self._phase >= len(PHASES):
                self._phase = None
                self._render()

    def off(self):
        self._phase = None
        for i in range(len(self.strip)):
            self.strip[i] = (0, 0, 0)
        self.strip.write()

    # -- verbs -------------------------------------------------------

    def push(self, value, colour):
        if colour not in COLORS:
            raise ValueError("score_station: unknown colour %r" % colour)
        self.scores.append((value, COLORS[colour]))
        if len(self.scores) > self.bars:
            self.scores.pop(0)
        self._col = len(self.scores) - 1
        self._phase = 0
        self._frame = 0
        self._due = time.ticks_ms()

    def clear(self):
        self.scores = []
        self.off()

    def set_scale(self, mode):
        if mode not in ("low", "high"):
            raise ValueError("score_station: unknown scale %r" % mode)
        self.low_wins = (mode == "low")
        self._render()

    # -- drawing -----------------------------------------------------

    def _index(self, col, row):
        base = col * self.height
        if self.serpentine and col % 2:
            return base + (self.height - 1 - row)
        return base + row

    def _set_col(self, col, rgb):
        for row in range(self.height):
            self.strip[self._index(col, row)] = rgb
        self.strip.write()

    def _lit_rows(self, value, best):
        """Rows to light for `value`, given the best value on the board."""
        if value <= 0 or best <= 0:
            return MIN_ROWS
        share = (best / value) if self.low_wins else (value / best)
        return max(MIN_ROWS, min(self.height, round(share * self.height)))

    def _render(self):
        for i in range(len(self.strip)):
            self.strip[i] = (0, 0, 0)
        if self.scores:
            values = [v for v, _ in self.scores]
            best = min(values) if self.low_wins else max(values)
            for col, (value, rgb) in enumerate(self.scores):
                lit = self._lit_rows(value, best)
                for row in range(lit):
                    self.strip[self._index(col, row)] = _dim(rgb)
        self.strip.write()

    def _draw_phase(self, kind, frame):
        if kind == SPARKLE:
            for _ in range(random.randint(3, 6)):
                px = random.randint(0, len(self.strip) - 1)
                br = random.randint(120, 255)
                self.strip[px] = _dim((br, int(br * 0.65), int(br * 0.1)))
            self.strip.write()
            for i in range(len(self.strip)):
                self.strip[i] = (0, 0, 0)
        elif kind == WIPE:
            self._set_col(self._col, (0, 0, 0))
            self.strip[self._index(self._col, frame)] = _dim((255, 255, 255))
            if frame >= 1:
                self.strip[self._index(self._col, frame - 1)] = _dim((80, 30, 220))
            if frame >= 2:
                self.strip[self._index(self._col, frame - 2)] = _dim((25, 10, 70))
            self.strip.write()
        elif kind == HOLD:
            self._set_col(self._col, _dim((255, 255, 255)))
        elif kind == FILL:
            self.strip[self._index(self._col, frame)] = _dim(RAINBOW[frame % len(RAINBOW)])
            self.strip.write()
        elif kind == REST:
            self._set_col(self._col, (0, 0, 0))
