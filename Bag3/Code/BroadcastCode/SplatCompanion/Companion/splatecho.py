"""
Splat Echo -- two-player pattern game, Splat Companion half
=============================================================
Tag / start_game name: splatecho (lib/splat_tags.py GAME_TAGS). Runs with
the wand's splatecho.py (MockWand/), a separate program for the same game.

The wand (Caller) sends a pattern of Splat units one step at a time; each
step lights that Splat in its color and plays its sound. When the wand
sends echo_go, the Echo player presses the Splats in the same order within
STEP_MS per step. A correct press lights and sounds that Splat; the whole
pattern scores for Echo, a wrong Splat or a timeout scores for Caller.

Unit colors and sounds are fixed by unit index (UNITS) so they match the
wand's colors. With fewer than 4 Splats, a unit index wraps onto the
Splats present (index % splat.count).

Messages (dicts, "type" names not used elsewhere):
  received  {"type": "echo_add", "unit": i}
            {"type": "echo_go", "n": steps}
  sent      {"type": "echo_step", "idx": k}
            {"type": "echo_result", "ok": bool, "n": steps}

Exits on ESP-NOW "stop" or "start_game" (cards arrive the same way; see
main.py's _GameEnow).
"""

import time

# unit index -> (Splat color, ring RGB, sound); same order as the wand's.
UNITS = (
    ("turnred", (60, 0, 0), "cat"),
    ("turnblue", (0, 0, 60), "dog"),
    ("turnyellow", (60, 40, 0), "cow"),
    ("turnpurple", (36, 0, 45), "duck"),
)
SHOW_MS = 400          # how long a step or a correct press stays lit
STEP_MS = 3000         # Echo's time allowed per step
RESULT_MS = 800        # all-Splat result flash


def _unit(splat, i):
    return splat.unit(i % splat.count)


def _light(splat, leds, i):
    cname, rgb, sound = UNITS[i % len(UNITS)]
    u = _unit(splat, i)
    u.color(cname)
    u.sound(sound)
    leds.fill(rgb)
    return time.ticks_add(time.ticks_ms(), SHOW_MS)


def _dark(splat, leds):
    splat.color("turnoff")
    leds.fill((0, 0, 0))


def play(splat, leds, enow, batt=None):
    print("  splatecho: %d Splat(s); waiting for the wand's pattern" % splat.count)
    splat.off()
    leds.fill((0, 0, 0))
    pattern = []
    echo = False          # False: Caller is adding steps; True: Echo's turn
    idx = 0
    deadline = None
    off_at = None
    while True:
        now = time.ticks_ms()
        mt, data, mac = enow.poll()
        if mt in ("stop", "start_game"):
            print("  splatecho: exit on %s" % mt)
            return
        kind = data.get("type") if isinstance(data, dict) else None

        if kind == "echo_add" and not echo:
            unit = data.get("unit")
            if isinstance(unit, int):
                pattern.append(unit)
                print("  splatecho: step %d -> unit %d" % (len(pattern), unit))
                off_at = _light(splat, leds, unit)
        elif kind == "echo_go" and not echo and pattern:
            echo, idx = True, 0
            deadline = time.ticks_add(now, STEP_MS)
            print("  splatecho: Echo's turn, %d step(s)" % len(pattern))

        ev = splat.poll()
        result = None
        if echo and ev == "press":
            pressed = splat.last_index
            want = pattern[idx] % splat.count
            if pressed == want:
                off_at = _light(splat, leds, pattern[idx])
                enow.broadcast({"type": "echo_step", "idx": idx})
                idx += 1
                deadline = time.ticks_add(now, STEP_MS)
                if idx == len(pattern):
                    result = True
            else:
                print("  splatecho: wrong Splat %d, wanted %d" % (pressed, want))
                result = False
        elif echo and time.ticks_diff(now, deadline) >= 0:
            print("  splatecho: timeout on step %d" % (idx + 1))
            result = False

        if result is not None:
            enow.broadcast({"type": "echo_result", "ok": result, "n": len(pattern)})
            print("  splatecho: %s" % ("Echo scores" if result else "Caller scores"))
            splat.color("turngreen" if result else "turnred")
            leds.fill((0, 30, 0) if result else (30, 0, 0))
            off_at = time.ticks_add(time.ticks_ms(), RESULT_MS)
            pattern, echo, deadline = [], False, None

        if off_at is not None and time.ticks_diff(time.ticks_ms(), off_at) >= 0:
            _dark(splat, leds)
            off_at = None
        time.sleep_ms(1)
