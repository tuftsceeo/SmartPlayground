"""
jumpin.py -- Mini Splat Companion test game (one Splat)
========================================================
Wand-contract game: play(nfc, leds, buz, accel, i2c, enow, batt, splats).
SPLATS_LOCAL = 1, so main.py hands it the mini's GameSplats and refuses to
start it unless the Splat is connected.

At start the Splat gets a random color and animal sound. Held: the Splat and
the 3 pixels show the color, the sound plays on the press; released: dark.
Every change broadcasts {"type": "jumpin", "from": "splat", "unit": 0,
"event": "press"|"release", "rgb": [r, g, b]} (plus "tone" on a press).
A {"type": "jumpin", "from": "wand"} flashes the Splat and pixels green.
Exits on ESP-NOW "stop" or "start_game".
"""

import random
import time

SPLATS_LOCAL = 1
BLINK_MS = 300

_COLORS = (
    ("turnred", (60, 0, 0)),
    ("turnblue", (0, 0, 60)),
    ("turnpurple", (36, 0, 45)),
    ("turnyellow", (60, 40, 0)),
    ("turnwhite", (40, 40, 40)),
)
_SOUNDS = ("cat", "chicken", "cow", "dog", "pig", "duck", "elephant",
           "horse", "goat")
_TONES = (392, 523, 659, 784, 988, 1175)
DARK = (0, 0, 0)


def _pick(seq):
    return seq[random.getrandbits(16) % len(seq)]


def play(nfc, leds, buz, accel, i2c, enow, batt=None, splats=None):
    cname, rgb = _pick(_COLORS)
    sound = _pick(_SOUNDS)
    tone = _pick(_TONES)
    print("  jumpin: Splat -> %s, %s" % (cname, sound))
    unit = splats.unit(0)
    unit.off()
    leds.fill(DARK)
    held = False
    green_until = None
    while True:
        mt, data, mac = enow.poll()
        if mt in ("stop", "start_game"):
            print("  jumpin: exit on %s" % mt)
            return
        if (isinstance(data, dict) and data.get("type") == "jumpin"
                and data.get("from") == "wand"):
            unit.color("turngreen")
            leds.fill((0, 30, 0))
            green_until = time.ticks_add(time.ticks_ms(), BLINK_MS)
        ev = splats.poll()
        if ev is not None:
            kind, i = ev
            if kind == "press" and not held:
                held = True
                unit.sound(sound)
            elif kind == "release" and held:
                held = False
            else:
                kind = None
            if kind is not None:
                msg = {"type": "jumpin", "from": "splat", "unit": i,
                       "event": kind, "rgb": list(rgb if held else DARK)}
                if kind == "press":
                    msg["tone"] = tone
                enow.broadcast(msg)
                if green_until is None:
                    unit.color(cname if held else "turnoff")
                    leds.fill(rgb if held else DARK)
        if green_until is not None and time.ticks_diff(time.ticks_ms(), green_until) >= 0:
            green_until = None
            unit.color(cname if held else "turnoff")
            leds.fill(rgb if held else DARK)
        time.sleep_ms(1)
