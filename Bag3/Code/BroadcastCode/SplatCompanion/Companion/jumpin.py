"""
jumpin.py -- Splat Companion built-in test game
================================================
Card / start_game name: jumpin (lib/splat_tags.py GAME_TAGS), the neutral
test game name every Bag3 device answers to.

At start, each Splat is randomly given its own color, animal sound and
wand buzzer tone, all distinct (_assign()). A press on Splat i shows its
color on that Splat and the ring, plays its sound, and broadcasts
{"type": "jumpin", "from": "splat", "unit": i, "rgb": [r, g, b],
 "tone": hz}; a wand's jumpin (MockWand/jumpin.py) blinks that color and
beeps that tone. A {"type": "jumpin", "from": "wand"} blinks every Splat
green. Exits on ESP-NOW "stop" or "start_game" (a stop card or another
game's card arrives the same way; see main.py's _GameEnow).
"""

import random
import time

BLINK_MS = 300

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


def play(splat, leds, enow, batt=None):
    roles = _assign(splat.count)
    for i, (cname, rgb, sound, tone) in enumerate(roles):
        print("  jumpin: Splat %d -> %s, %s, %d Hz" % (i, cname, sound, tone))
    leds.fill((0, 0, 0))
    splat.off()
    off_at = None
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
            off_at = time.ticks_add(time.ticks_ms(), BLINK_MS)
        if splat.poll() == "press":
            i = splat.last_index
            cname, rgb, sound, tone = roles[i]
            print("  jumpin: Splat %d pressed (%s, %s)" % (i, cname, sound))
            enow.broadcast({"type": "jumpin", "from": "splat", "unit": i,
                            "rgb": list(rgb), "tone": tone})
            u = splat.unit(i)
            u.color(cname)
            u.sound(sound)
            leds.fill(rgb)
            off_at = time.ticks_add(time.ticks_ms(), BLINK_MS)
        if off_at is not None and time.ticks_diff(time.ticks_ms(), off_at) >= 0:
            # LEDs only: splat.off() would also cut a sound still playing.
            # main.py runs splat.off() when the game returns.
            splat.color("turnoff")
            leds.fill((0, 0, 0))
            off_at = None
        time.sleep_ms(1)
