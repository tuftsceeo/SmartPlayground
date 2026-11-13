# Splat host group games (type 9); replaces lobby_games.md

DRAFT. A **Splat host** is one extra wand the teacher sets up beforehand. It holds all the
game's Splats (up to **4**) and runs the group; the children's wands hold none. Pooled Splats do
not exist.

## Declarations (top level)

`SPLAT_HOST = True`, `SPLATS_MIN` (1..4), `SPLATS_MAX` (at most 4), `PLAYERS_MIN` (at least 1),
`GAME_ICON`. `play()` takes eight parameters, with `net=None` last. Never `SPLATS_LOCAL`.

```python
def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
```

## How it starts (say this in the game's description)

The teacher taps the game card on the host. Each child taps the same card on their wand. The
host's lights show how many children have joined, as a numeral. The teacher presses the host's
button to start.

`[GAME_SETTINGS: {"splat_host": n, "wands": m}]`: Splats on the host (1..4) and children's wands.

## Template rules

- Call `ev = net.poll()` first each loop. **Never `enow.poll()`**: `net.poll()` reads the radio.
- Return on `("end",)` and `("leader_lost",)`. Cards every `NFC_EVERY`, `time.sleep_ms(...)`
  every loop, `leds.off()` in `finally`.
- `if net.is_host:` the host decides everything and drives `net.splat(i)`. A player wand shows
  state and sends input with `net.send(0, {...})`.
- Handle `splat_lost` / `wand_lost` (pause, skip, or carry on); never ignore them.
- Prefer turn-based play; the host repeats important state. Keep dicts small.
- A Splat that stands for something stays lit in its color. The wand turns Splats off itself.
- Tell teachers "4 Splats", not how they pair.

## `net` (trimmed)

| Member | Meaning |
|---|---|
| `net.is_host` | `True` on the Splat host |
| `net.players` | indexes in `net.wands` of the children's wands (host excluded) |
| `net.me` | this wand's index (host is 0) |
| `net.wands` | list of `(mac, identity_name, splat_count)`, host first |
| `net.splat_count` | Splats on the host |
| `net.splat(i)` | Splat `i`: `color`, `note`, `sound`, `play([...])`, `off()`. Host only |
| `net.send(to, data)` | small dict to wand index `to`, or `to=None` for all others |
| `net.poll()` | every loop; one event tuple or `None` |

`net.wands[i][1]` is a wand's identity name and is already a Splat color name
(`"turnred"` ...). Map it to `leds` colors with a six-entry dict (see the example).

| Event | Who | Meaning |
|---|---|---|
| `("press", i)` / `("release", i)` | host | Splat `i` pressed / let go |
| `("msg", from_wand, data)` | receiver | a `net.send()` dict |
| `("splat_lost", i)` / `("splat_back", i)` | host | Splat dropped / returned |
| `("wand_lost", w)` / `("wand_back", w)` | host | a player wand quiet for 3 s / back |
| `("leader_lost",)` | players | the host went quiet for 3 s |
| `("end",)` | every wand | game over (host ended it, or `stop` / `start_game`) |

Splat actions, parts and the color table are as in `wand_type2.md`.

## Example: Splat Tag

The host lights a Splat in a player's color; that player scores when it is pressed. First to 5.

```python
"""
Splat Tag -- press the Splat that glows in your wand's color
"""
import random
import time

from nfc_reader import NfcReader
from game_tags import exit_tags_excluding
from leds import (RED, GREEN, BLUE, YELLOW, PURPLE, WHITE, ORANGE, SHAPE_BULLSEYE,
                  SHAPE_0, SHAPE_1, SHAPE_2, SHAPE_3, SHAPE_4, SHAPE_5)

GAME_ICON = (SHAPE_BULLSEYE, ORANGE)
SPLAT_HOST = True
SPLATS_MIN = 2
SPLATS_MAX = 4
PLAYERS_MIN = 1

_EXIT_TAGS = exit_tags_excluding("splat_tag")
COMMANDS = _EXIT_TAGS
NFC_EVERY = 10
LOOP_MS = 20
WAND_COLOR = {"turnred": RED, "turngreen": GREEN, "turnblue": BLUE,
              "turnyellow": YELLOW, "turnpurple": PURPLE, "turnwhite": WHITE}
DIGITS = (SHAPE_0, SHAPE_1, SHAPE_2, SHAPE_3, SHAPE_4, SHAPE_5)
WIN_SCORE = 5
ROUND_MS = 8000
PAUSE_MS = 1200


def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
    if net is None:
        return
    reader = NfcReader(nfc, COMMANDS)
    frame = 0
    lost_splats = set()
    lost_wands = set()
    scores = [0] * len(net.wands)
    target = None                 # host: (splat, player)
    state = "pick"                # host: pick, wait, pause
    at = time.ticks_ms()
    try:
        while True:
            if frame % NFC_EVERY == 0:
                cmd, _uid = reader.read_command(timeout=100)
                if cmd in _EXIT_TAGS:
                    return
            ev = net.poll()
            if ev == ("end",) or ev == ("leader_lost",):
                return
            if net.is_host:
                # host: decides everything
                if ev and ev[0] == "splat_lost":
                    lost_splats.add(ev[1])
                elif ev and ev[0] == "splat_back":
                    lost_splats.discard(ev[1])
                elif ev and ev[0] == "wand_lost":
                    lost_wands.add(ev[1])
                elif ev and ev[0] == "wand_back":
                    lost_wands.discard(ev[1])
                elif ev and ev[0] == "press" and state == "wait" and ev[1] == target[0]:
                    p = target[1]
                    scores[p] += 1
                    net.splat(ev[1]).play(["turnyellow", "cow"])
                    net.send(None, {"s": scores})
                    if scores[p] >= WIN_SCORE:
                        net.send(None, {"win": p})
                        return
                    target = None
                    state = "pause"
                    at = time.ticks_ms()
                waited = time.ticks_diff(time.ticks_ms(), at)
                lost_target = target and (target[0] in lost_splats or target[1] in lost_wands)
                if state == "pause" and waited >= PAUSE_MS or state == "wait" and (
                        waited >= ROUND_MS or lost_target):
                    if target:
                        net.splat(target[0]).off()
                    target = None
                    state = "pick"
                if state == "pick":
                    splats = [i for i in range(net.splat_count) if i not in lost_splats]
                    players = [p for p in net.players if p not in lost_wands]
                    if splats and players:
                        target = (random.choice(splats), random.choice(players))
                        net.splat(target[0]).color(net.wands[target[1]][1])
                        state = "wait"
                        at = time.ticks_ms()
            else:
                # player: shows what the host sends
                if ev and ev[0] == "msg":
                    d = ev[2]
                    if "s" in d:
                        leds.show_shape(DIGITS[d["s"][net.me]], WAND_COLOR[net.wands[net.me][1]])
                    elif "win" in d:
                        leds.fill(WAND_COLOR[net.wands[d["win"]][1]])
                        if d["win"] == net.me:
                            buz.success()
                        time.sleep_ms(3000)
                        return
            time.sleep_ms(LOOP_MS)
            frame += 1
    finally:
        leds.off()
```

## Appendix: type 7, plain wand lobby (last resort)

Only when the teacher asks for a group game with no station. Children cannot recall multi-step
starts, so prefer type 9, 8 or 6. Declare `SPLATS_MIN` without `SPLAT_HOST` (no Splats are
used); `play()` has the same eight-parameter shape and the same rules, with `net.is_leader` in
place of `net.is_host`. The first wand to tap the card leads; the others tap it to join; the
leader presses the wand button to start. No Splat calls.
