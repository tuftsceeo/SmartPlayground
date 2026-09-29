"""
jumpin.py -- Splat Companion built-in test game
================================================
Card / start_game name: jumpin (lib/splat_tags.py GAME_TAGS), the neutral
test game name every Bag3 device answers to.

At start, each Splat is randomly given its own color, animal sound and
wand buzzer tone, all distinct (_assign()). Press-and-hold:

- A Splat stays lit in its color while held and goes dark on release;
  its sound plays on the press.
- The ring and the wand show the most recently pressed Splat still held;
  when that one is released they fall back to the next most recent held
  one (no sound replay), and go dark when none is held.
- Every change broadcasts {"type": "jumpin", "from": "splat", "unit": i,
  "event": "press"|"release", "rgb": [r, g, b]} (the color to show now,
  [0, 0, 0] for dark), plus "tone": hz on a press. MockWand/jumpin.py
  shows rgb and beeps tone.
- A {"type": "jumpin", "from": "wand"} flashes every Splat and the ring
  green for BLINK_MS, then restores the held state.

Exits on ESP-NOW "stop" or "start_game" (a stop card or another game's
card arrives the same way; see main.py's _GameEnow).
"""

import random
import time

BLINK_MS = 300          # green flash on a wand press

# (Splat color name, ring/wand RGB). Green is kept for wand presses.
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


def _shuffled(seq):
    items = list(seq)
    for i in range(len(items) - 1, 0, -1):
        j = random.getrandbits(16) % (i + 1)
        items[i], items[j] = items[j], items[i]
    return items


def _assign(n):
    """n distinct (color_name, rgb, sound, tone) tuples, randomly paired.
    Needs n <= len(_COLORS); the hub allows at most 4 Splats."""
    colors, sounds, tones = _shuffled(_COLORS), _shuffled(_SOUNDS), _shuffled(_TONES)
    return [(colors[i][0], colors[i][1], sounds[i], tones[i]) for i in range(n)]


DARK = (0, 0, 0)


def _show(splat, leds, roles, held):
    """Apply the held state: each held Splat in its color, the rest dark;
    the ring in the latest held Splat's color. Returns the ring color."""
    for i in range(splat.count):
        splat.unit(i).color(roles[i][0] if i in held else "turnoff")
    rgb = roles[held[-1]][1] if held else DARK
    leds.fill(rgb)
    return rgb


def play(splat, leds, enow, batt=None):
    roles = _assign(splat.count)
    for i, (cname, rgb, sound, tone) in enumerate(roles):
        print("  jumpin: Splat %d -> %s, %s, %d Hz" % (i, cname, sound, tone))
    held = []           # units held down, oldest first
    splat.off()
    leds.fill(DARK)
    green_until = None
    while True:
        mt, data, mac = enow.poll()
        if mt in ("stop", "start_game"):
            print("  jumpin: exit on %s" % mt)
            return
        if (isinstance(data, dict) and data.get("type") == "jumpin"
                and data.get("from") == "wand"):
            print("  jumpin: wand pressed (%s)" % mac)
            splat.color("turngreen")
            leds.fill((0, 30, 0))
            green_until = time.ticks_add(time.ticks_ms(), BLINK_MS)
        ev = splat.poll()
        if ev is not None:
            i = splat.last_index
            if ev == "press" and i not in held:
                held.append(i)
                print("  jumpin: Splat %d pressed (%s, %s)"
                      % (i, roles[i][0], roles[i][2]))
                splat.unit(i).sound(roles[i][2])
            elif ev == "release" and i in held:
                held.remove(i)
                print("  jumpin: Splat %d released" % i)
            else:
                ev = None
        if ev is not None:
            rgb = roles[held[-1]][1] if held else DARK
            msg = {"type": "jumpin", "from": "splat", "unit": i,
                   "event": ev, "rgb": list(rgb)}
            if ev == "press":
                msg["tone"] = roles[i][3]
            enow.broadcast(msg)
            if green_until is None:
                _show(splat, leds, roles, held)
        if green_until is not None and time.ticks_diff(time.ticks_ms(), green_until) >= 0:
            green_until = None
            _show(splat, leds, roles, held)
        time.sleep_ms(1)
