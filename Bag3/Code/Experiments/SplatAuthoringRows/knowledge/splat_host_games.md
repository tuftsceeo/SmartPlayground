# Splat host group games (type 9); replaces lobby_games.md

DRAFT. A **Splat host** is one extra wand, set up beforehand, that holds all the game's Splats (up to
**4**) and runs the group. The children's wands hold none.

Declare `SPLAT_HOST = True`, `SPLATS_MIN` (1..4), `SPLATS_MAX` (at most 4), `PLAYERS_MIN` (at least
1) and `GAME_ICON`; never `SPLATS_LOCAL`. `play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None)`.
Say how it starts in the description: the teacher taps the game card on the host, each child taps
it on their wand, the teacher presses the host's button.
`[GAME_SETTINGS: {"splat_host": n, "wands": m}]`: Splats on the host (1..4), children's wands.

## Template rules

- `ev = net.poll()` first each loop; **never `enow.poll()`**. Return on `("end",)` and
  `("leader_lost",)`. Cards every `NFC_EVERY`, `time.sleep_ms(...)` every loop, `leds.off()` in
  `finally`. The wand turns Splats off itself.
- `if net.is_host:` the host decides everything and drives `net.splat(i)`. A player wand shows
  state and sends input with `net.send(0, {...})`.
- **Handle `splat_lost` and `wand_lost`** (pause, skip or carry on); a host game that ignores
  them is refused at send time. Prefer turn-based play and small dicts.

## `net`

| Member | Meaning |
|---|---|
| `net.is_host`, `net.me` | `True` on the host; this wand's index (host is 0) |
| `net.wands`, `net.players` | `(mac, identity_name, splat_count)` per wand, host first (the name is a Splat color name); indexes of the children's wands |
| `net.splat_count`, `net.splat(i)` | Splats on the host; Splat `i` (`color`, `note`, `sound`, `play([...])`, `off()`), host only |
| `net.send(to, data)` | small dict to wand index `to`, or `to=None` for all others |

| Event from `net.poll()` | Who | Meaning |
|---|---|---|
| `("press", i)` / `("release", i)` | host | Splat `i` pressed / let go |
| `("msg", from_wand, data)` | receiver | a `net.send()` dict |
| `("splat_lost", i)`, `("wand_lost", w)` / `("splat_back", i)`, `("wand_back", w)` | host | a Splat dropped or a player wand quiet for 3 s / it returned |
| `("leader_lost",)` / `("end",)` | players / all | the host went quiet for 3 s / game over |

Splat actions and colors: see `wand_type2.md`. Map `net.wands[i][1]` to `leds` colors with a dict.

## Example: Splat Tag (the host lights a Splat in a player's color; first to 5)
```python
"""Splat Tag -- press the Splat that glows in your wand's color"""
import random
import time
from nfc_reader import NfcReader
from game_tags import exit_tags_excluding
from leds import RED, GREEN, BLUE, YELLOW, PURPLE, WHITE, ORANGE, SHAPE_BULLSEYE

GAME_ICON = (SHAPE_BULLSEYE, ORANGE)
SPLAT_HOST = True
SPLATS_MIN = 2
SPLATS_MAX = 4
PLAYERS_MIN = 1
_EXIT_TAGS = exit_tags_excluding("splat_tag")
COMMANDS = _EXIT_TAGS
NFC_EVERY, LOOP_MS = 10, 20
WAND_COLOR = {"turnred": RED, "turngreen": GREEN, "turnblue": BLUE,
              "turnyellow": YELLOW, "turnpurple": PURPLE, "turnwhite": WHITE}
WIN_SCORE = 5
ROUND_MS, PAUSE_MS = 8000, 1200


def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
    if net is None:
        return
    reader = NfcReader(nfc, COMMANDS)
    frame, lost = 0, set()        # lost: ("s", splat) and ("w", wand) that dropped out
    scores, target = [0] * len(net.wands), None   # target: host's (splat, player) in a live round
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
                # host on event
                if ev and ev[0] in ("splat_lost", "wand_lost"):
                    lost.add((ev[0][0], ev[1]))
                elif ev and ev[0] in ("splat_back", "wand_back"):
                    lost.discard((ev[0][0], ev[1]))
                elif ev and ev[0] == "press" and target and ev[1] == target[0]:
                    scores[target[1]] += 1
                    net.splat(ev[1]).play(["turnyellow", "cow"])
                    if scores[target[1]] >= WIN_SCORE:
                        net.send(None, {"win": target[1]})
                        return
                    target, at = None, time.ticks_ms()
                # host on timer
                waited = time.ticks_diff(time.ticks_ms(), at)
                if target and (waited >= ROUND_MS or ("s", target[0]) in lost
                               or ("w", target[1]) in lost):
                    net.splat(target[0]).off()
                    target, at = None, time.ticks_ms()
                elif target is None and waited >= PAUSE_MS:
                    splats = [i for i in range(net.splat_count) if ("s", i) not in lost]
                    players = [p for p in net.players if ("w", p) not in lost]
                    if splats and players:
                        target = (random.choice(splats), random.choice(players))
                        net.splat(target[0]).color(net.wands[target[1]][1])
                        at = time.ticks_ms()
            elif ev and ev[0] == "msg" and "win" in ev[2]:
                # player on message
                leds.fill(WAND_COLOR[net.wands[ev[2]["win"]][1]])
                time.sleep_ms(3000)
                return
            time.sleep_ms(LOOP_MS)
            frame += 1
    finally:
        leds.off()
```

## Appendix: type 7, plain wand lobby (last resort)

Only when the teacher asks for a group game with no station. Declare `SPLATS_MIN` without `SPLAT_HOST`
(no Splats); same shape and rules, `net.is_leader` for `net.is_host`. The first wand to tap the card
leads, the others tap it to join, the leader presses to start.
