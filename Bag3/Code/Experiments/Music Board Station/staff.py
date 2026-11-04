"""
8x8 NeoPixel staff and button LEDs.

Pixels 0-63 are the staff, wired column-major from index 0:
index = col * 8 + (7 - row), row 0 = low C (bottom), row 7 = high C.
Pixels 64-66 light the voice, play and person+ buttons.

The staff is a window onto a timeline where one column is one
eighth-beat. A note's first column is its head (full colour); the rest
of its length is a dim tail. Rests are empty columns.

The pilot board showed occasional shifted/blurred colours after running a
while (a corrupted WS2812 frame). The LED_* settings below exist to bench
that; see README "LED glitches".
"""

import time
import neopixel
from machine import Pin

# "rmt": MicroPython's default RMT bitstream. "bitbang": CPU bit-bang with
# interrupts off for the ~2 ms frame, so WiFi interrupts cannot delay an RMT
# refill mid-frame.
LED_MODE = "rmt"
WRITE_TWICE = True    # repeat each frame immediately; overwrites a corrupted first pass
REFRESH_MS = 250      # rewrite the current frame this often; 0 = off
PRE_WRITE_MS = 0      # pilot's sleep before each write; 10 there, did not fix the glitch

NEOPIXEL_PIN = 21
NUM_PIXELS = 67
COLS = 8
ROWS = 8
VOICE_LED = 64
PLAY_LED = 65
ADD_LED = 66

PLAYHEAD_COL = 2     # column the playing note holds at while scrolling
TAIL_SCALE = 4       # tail brightness = colour // TAIL_SCALE
MORE_COLOR = (20, 20, 20)
OFF = (0, 0, 0)

# Note number (1-8) -> RGB, as on the Feb 2025 board
NOTE_RGB = {
    1: (100, 0, 0),     # C  red
    2: (255, 127, 0),   # D  orange
    3: (255, 255, 0),   # E  yellow
    4: (0, 255, 0),     # F  green
    5: (0, 255, 255),   # G  cyan
    6: (0, 0, 255),     # A  blue
    7: (50, 0, 255),    # B  purple
    8: (150, 70, 200),  # C5 pink
}


def _dim(c):
    return (c[0] // TAIL_SCALE, c[1] // TAIL_SCALE, c[2] // TAIL_SCALE)


def _index(col, row):
    return col * 8 + (7 - row)


def timeline(tokens):
    """[(note, eighths), ...] -> per-column list of (note, is_head); note 0 = rest."""
    cols = []
    for note, eighths in tokens:
        for i in range(eighths):
            cols.append((note, i == 0))
    return cols


class Staff:
    def __init__(self):
        if LED_MODE == "bitbang":
            import esp32
            esp32.RMT.bitstream_channel(None)
        elif LED_MODE != "rmt":
            raise ValueError(f"LED_MODE must be 'rmt' or 'bitbang', got {LED_MODE!r}")
        print(f"  LEDs: mode={LED_MODE} write_twice={WRITE_TWICE} refresh={REFRESH_MS} ms")
        self.np = neopixel.NeoPixel(Pin(NEOPIXEL_PIN), NUM_PIXELS)
        self._last_write = 0
        self.clear()

    def _write(self):
        if PRE_WRITE_MS:
            time.sleep_ms(PRE_WRITE_MS)
        self.np.write()
        if WRITE_TWICE:
            self.np.write()
        self._last_write = time.ticks_ms()

    def refresh(self):
        """Rewrite the unchanged frame every REFRESH_MS so a glitched frame clears."""
        if REFRESH_MS and time.ticks_diff(time.ticks_ms(), self._last_write) >= REFRESH_MS:
            self._write()

    def clear(self):
        for i in range(COLS * ROWS):
            self.np[i] = OFF
        self._write()

    def window_start(self, cols_len, t):
        """First timeline column shown when column t is playing."""
        start = t - PLAYHEAD_COL
        last = cols_len - COLS
        if start > last:
            start = last
        if start < 0:
            start = 0
        return start

    def draw(self, cols, start=0, playing=None):
        """Draw timeline columns [start, start+8). playing = timeline column now sounding."""
        for i in range(COLS * ROWS):
            self.np[i] = OFF
        for c in range(COLS):
            t = start + c
            if t >= len(cols):
                break
            note, head = cols[t]
            if note == 0:
                continue
            row = note - 1
            color = NOTE_RGB[note]
            if t == playing:
                for r in range(row):
                    self.np[_index(c, r)] = color
                self.np[_index(c, row)] = color
            else:
                self.np[_index(c, row)] = color if head else _dim(color)
        if playing is None and len(cols) > start + COLS:
            idx = _index(COLS - 1, ROWS - 1)
            if self.np[idx] == OFF:
                self.np[idx] = MORE_COLOR
        self._write()

    def buttons(self, voice_rgb, play_rgb, add_rgb):
        self.np[VOICE_LED] = voice_rgb
        self.np[PLAY_LED] = play_rgb
        self.np[ADD_LED] = add_rgb
        self._write()
