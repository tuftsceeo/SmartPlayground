"""
jumpin.py -- Splat Companion built-in test game
================================================
Card / start_game name: jumpin (lib/splat_tags.py GAME_TAGS), the neutral
test game name every Bag3 device answers to.

Each Splat press blinks that Splat (only) and the ring green and broadcasts
{"type": "jumpin", "from": "splat", "unit": i}; a {"type": "jumpin",
"from": "wand"} from a wand's jumpin (MockWand/jumpin.py) blinks every
Splat. With several Splats (hubtype.py max_splats), i says which one. Exits on ESP-NOW
"stop" or "start_game" (a stop card or another game's card arrives the
same way; see main.py's _GameEnow).
"""

import time

BLINK_MS = 300


def play(splat, leds, enow, batt=None):
    print("  jumpin: press the Splat to blink green")
    leds.fill((0, 0, 0))
    splat.off()
    off_at = None
    while True:
        mt, data, mac = enow.poll()
        if mt in ("stop", "start_game"):
            print("  jumpin: exit on %s" % mt)
            return
        target = None       # the object to blink: one unit, or the group
        if (isinstance(data, dict) and data.get("type") == "jumpin"
                and data.get("from") == "wand"):
            print("  jumpin: wand pressed (%s)" % mac)
            target = splat
        if splat.poll() == "press":
            i = splat.last_index
            print("  jumpin: Splat %d pressed" % i)
            enow.broadcast({"type": "jumpin", "from": "splat", "unit": i})
            target = splat.unit(i)
        if target is not None:
            target.color("turngreen")
            leds.fill((0, 30, 0))
            off_at = time.ticks_add(time.ticks_ms(), BLINK_MS)
        if off_at is not None and time.ticks_diff(time.ticks_ms(), off_at) >= 0:
            splat.off()
            leds.fill((0, 0, 0))
            off_at = None
        time.sleep_ms(1)
