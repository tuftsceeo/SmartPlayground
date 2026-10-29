"""
splatwhack.py -- Splat Companion built-in game
================================================
Card tag: splatwhack (lib/splat_tags.py GAME_TAGS)

Prompts a random color; the first press while it's showing scores a hit
(broadcasts "score"), and a slow response scores nothing. Exits on
ESP-NOW "stop" or "start_game" naming another game -- see
lib/splat_api.py's poll() docstring for why `splat.poll()` must be called
every loop.

Requires no NFC, buzzer, motor or accelerometer -- this device has none of
those; see ChatBroadcast/knowledge/devices/splat_companion.md's argument notes.
"""

import time

COLORS = ("turnred", "turngreen", "turnblue", "turnyellow", "turnpurple")
ROUND_MS = 2500       # time allowed to react to a prompt
GAP_MS = 500          # dark pause between rounds


def play(splat, leds, enow, batt=None):
    print("  splatwhack: start")
    score = 0
    rounds = 0

    while True:
        # ── dark gap, watching for exit ──
        leds.fill((0, 0, 0))
        splat.off()
        gap_end = time.ticks_add(time.ticks_ms(), GAP_MS)
        while time.ticks_diff(gap_end, time.ticks_ms()) > 0:
            mt, data, mac = enow.poll()
            if mt == "stop":
                print("  splatwhack: stop, score=%d/%d" % (score, rounds))
                return
            if mt == "start_game":
                # _StartGameCapture already recorded the name; just return.
                return
            splat.poll()
            time.sleep_ms(1)

        # ── prompt ──
        rounds += 1
        name = COLORS[rounds % len(COLORS)]
        splat.color(name)
        leds.fill((10, 10, 10))
        print("  splatwhack: round %d, prompt=%s" % (rounds, name))

        hit = False
        round_end = time.ticks_add(time.ticks_ms(), ROUND_MS)
        while time.ticks_diff(round_end, time.ticks_ms()) > 0:
            mt, data, mac = enow.poll()
            if mt == "stop":
                print("  splatwhack: stop, score=%d/%d" % (score, rounds))
                return
            if mt == "start_game":
                return
            ev = splat.poll()
            if ev == "press" and not hit:
                hit = True
                score += 1
                print("  splatwhack: hit! score=%d/%d" % (score, rounds))
                enow.broadcast({"type": "score", "game": "splatwhack",
                                "score": score, "rounds": rounds})
                leds.fill((0, 30, 0))
            time.sleep_ms(1)

        if not hit:
            print("  splatwhack: miss, score=%d/%d" % (score, rounds))
