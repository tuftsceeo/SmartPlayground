# Splat games (lobby games)

A **Splat** is a pad children press; it lights up and plays sounds. A Splat cannot tell who
pressed it: a press counts the same whoever made it. Teachers see the Splats as one shared set on
the playground, not as belonging to a child. Each wand pairs with up to
**2** Splats (the children tap a Splat's card on the wand beforehand). A wand game drives Splats
through one extra `play()` parameter, `net`. There is no separate Splat file and no
`[DEVICE: splat]` block; everything below goes in the `[DEVICE: wand]` file.

## Choosing: ordinary or lobby game

| The game… | Declare at the top of the wand file | `net` is |
|---|---|---|
| uses no Splats | nothing | `None` (leave `net=None` off or unused) |
| uses Splats | `SPLATS_MIN = n` (and optional `SPLATS_MAX = m`) | a lobby game `net` |

- Every Splat game is a lobby game. For one child on one wand, use `SPLATS_MIN = 1`: the wand
  opens a lobby, nobody else needs to join, and the child presses the wand button to start.
- Declare `SPLATS_MIN` as a plain whole number at the top level of the file. Do not declare
  `SPLATS_LOCAL`: the wand has no solo Splat path and the game is refused when it is sent.
- `SPLATS_MIN` counts Splats across **all** joined wands (at least 1); `SPLATS_MAX`, if set, is at
  least `SPLATS_MIN`, and the game starts by itself when that many have joined.
- After the code, write the `[GAME_SETTINGS:]` marker (platform rules): `wand_splats` is how many
  Splats each wand is meant to have paired for this game, and `wands` how many wands it is for.
  The practice window starts with that many; the game itself still reads `net.local.count`,
  because on the playground it is whatever the children actually paired.
- A Splat game's `play()` takes **eight** parameters, with `net=None` last:

```python
def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
```

  The wand passes `net` only to an eight-parameter `play()`. Never use `net` without the parameter.

## How a lobby game starts

**Every player taps the same game card** on their own wand. The first wand becomes the
**leader** and opens a lobby; the others join it. The leader's lights count Splats joined against
`SPLATS_MIN`; when there are enough, the leader presses the wand button to start (or it starts
by itself at `SPLATS_MAX`). Wands without Splats may join and count as 0. A `stop` card on the
leader cancels the lobby for everyone. Tell the teacher this in the game's description.

Then **every wand, leader and followers, runs the same `play()`**. Write one `play()` and branch
on `net.is_leader`.

## The `net` object

| Member | Meaning |
|---|---|
| `net.is_leader` | `True` on the leader |
| `net.me` | this wand's index in `net.wands` (leader is 0) |
| `net.wands` | list of `(mac, identity_color, splat_count)`, leader first |
| `net.local` | this wand's own Splats, or `None` if it has none: `net.local.count`, `net.local.unit(s)` |
| `net.splat_count` | number of Splats in the shared pool |
| `net.splat(i)` | pool Splat `i`. **Leader only** (a follower gets an error): use `net.local.unit(s)` on a follower |
| `net.owner(i)` | index of the wand holding pool Splat `i` |
| `net.send(to, data)` | send a small dict to wand index `to`, or to every other wand with `to=None` |
| `net.poll()` | **call every loop**. Returns one event tuple, or `None` |

A Splat (from `net.splat(i)` or `net.local.unit(s)`) has `color(name)`, `note(name)`,
`sound(name)`, `play([name, name, ...])` (any mix of the three) and `off()`. Use only the names in
the "SPLAT ACTION NAMES" list; any other name is refused when the game is sent. Keep a Splat in a
variable if it is used often: `pad = net.splat(0)`.

A Splat's 14 lights are two rings: an **inner** ring in the middle and **outer** points out in
the arms. `color(name)` sets all of them; `color(name, "inner")` or `color(name, "outer")` sets
only that ring and leaves the other as it is. So a Splat can show two colors at once, or light
one ring and turn the other off:

```python
pad.color("turnred")                # all red
pad.color("turnoff", "outer")       # outer off; inner stays red
pad.color("turnblue", "outer")      # red inside, blue outside
```

`play([...])` and `off()` always act on the whole Splat. The only parts are `"inner"` and
`"outer"`; any other part is refused when the game is sent.

The Splat shows only six colors; each ring shows one at a time. When the same thing (a team, an animal, a card) appears on a
wand and a Splat, give it one of these so children can match them by eye:

| Color | Wand (`leds`) | Splat `color()` |
|---|---|---|
| red | `RED` | `"turnred"` |
| green | `GREEN` | `"turngreen"` |
| blue | `BLUE` | `"turnblue"` |
| yellow | `YELLOW` | `"turnyellow"` |
| purple | `PURPLE` | `"turnpurple"` |
| white | `WHITE` | `"turnwhite"` |

Events from `net.poll()`:

| Event | Who gets it | Meaning |
|---|---|---|
| `("press", i)` / `("release", i)` | leader: pool index; a follower: its own local index | a Splat was pressed / let go |
| `("msg", from_wand, data)` | the wand it was sent to | a `net.send()` dict |
| `("splat_lost", i)` / `("splat_back", i)` | leader | a Splat dropped out / came back |
| `("wand_lost", w)` / `("wand_back", w)` | leader | a follower wand went quiet for 3 s / came back |
| `("leader_lost",)` | followers | the leader went quiet for 3 s |
| `("end",)` | every wand | the game is over: the leader ended it, or a `stop` / `start_game` broadcast arrived |

## Rules every Splat game follows

- **Every wand returns on `("end",)`, and a follower also on `("leader_lost",)`.** Without it the
  wand keeps running a game that no longer exists. The leader decides what a lost wand or Splat
  means (pause, skip that player, or carry on); never ignore it silently.
- **Never call `enow.poll()` in a Splat game.** `net.poll()` reads the radio itself; an
  `enow.poll()` would take the other wands' messages away from it. A `stop` or `start_game`
  broadcast arrives as `("end",)`. Otherwise keep the usual wand loop: read cards every
  `NFC_EVERY` loops, `time.sleep_ms(...)` every loop, `leds.off()` in `finally`.
- Do not turn Splats off or say goodbye to other wands at the end: the wand turns its Splats
  off and tells the other wands when `play()` returns, stops or crashes.
- Messages may be lost or arrive late. Prefer **turn-based** designs (one wand or Splat active at
  a time, the leader keeps the score and decides who goes next) over designs that need every wand
  in step at the same instant. The leader should repeat important state rather than send it once.
- Keep `data` dicts small: a few short keys.
- **A Splat that stands for something stays lit.** When children tell Splats apart by color
  (a color, a team, an answer), keep each one glowing in its color for the whole game; after a
  press, flash or play a note, then go back to that color, not `off()`.
- **Talk to the teacher about Splats as one shared set**, by how many the game uses in all
  ("4 Splats"). Pairing Splats to wands comes up only in the how-to-play setup steps.

## Example: lobby game, pooled (the leader drives every Splat)

The leader lights one Splat from the whole pool at a time; whoever presses it scores for their
wand. Followers only keep `net.poll()` running (it carries out the leader's Splat commands) and
show their score.

```python
"""
Splat Race -- every player taps this card; press the lit Splat first
"""
import time
import random

from nfc_reader import NfcReader
from game_tags import exit_tags_excluding
from leds import OFF, GREEN

SPLATS_MIN = 2
SPLATS_MAX = 6
_EXIT_TAGS = exit_tags_excluding("splat_race")
COMMANDS = _EXIT_TAGS
NFC_EVERY = 10
LOOP_MS = 20


def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
    reader = NfcReader(nfc, COMMANDS)
    frame = 0
    lit = None
    lost = set()
    scores = [0] * len(net.wands)
    buz.beep(784, 80)
    try:
        while True:
            if frame % NFC_EVERY == 0:
                cmd, _uid = reader.read_command(timeout=100)
                if cmd in _EXIT_TAGS:
                    return
            ev = net.poll()
            if ev == ("end",):
                return
            if net.is_leader:
                if ev and ev[0] == "splat_lost":
                    lost.add(ev[1])
                    if lit == ev[1]:
                        lit = None
                elif ev and ev[0] == "splat_back":
                    lost.discard(ev[1])
                elif ev and ev[0] == "press" and ev[1] == lit:
                    w = net.owner(lit)
                    scores[w] += 1
                    net.splat(lit).off()
                    lit = None
                    net.send(w, {"s": scores[w]})
                    if w == net.me:
                        leds.fill(GREEN)
                if lit is None:
                    choices = [i for i in range(net.splat_count) if i not in lost]
                    if choices:
                        lit = random.choice(choices)
                        net.splat(lit).play(["turnyellow", "note_e"])
            else:
                if ev == ("leader_lost",):
                    return
                if ev and ev[0] == "msg":
                    leds.fill(GREEN)
                    buz.beep(1047, 60)
            time.sleep_ms(LOOP_MS)
            frame += 1
    finally:
        leds.off()
```

## Example: lobby game, messages (each wand drives its own Splat)

Turn-based: the leader says whose turn it is; that wand lights its own Splat; pressing it ends
the turn and tells the leader, who picks the next wand. Only wands with a Splat take turns.

```python
"""
Pass the Glow -- every player taps this card; press your Splat when it glows
"""
import time

from nfc_reader import NfcReader
from game_tags import exit_tags_excluding
from leds import OFF, BLUE

SPLATS_MIN = 2
_EXIT_TAGS = exit_tags_excluding("pass_the_glow")
COMMANDS = _EXIT_TAGS
NFC_EVERY = 10
LOOP_MS = 20


def _next(net, turn, gone):
    """Next wand after `turn` that has a Splat and is still here."""
    n = len(net.wands)
    for k in range(1, n + 1):
        w = (turn + k) % n
        if net.wands[w][2] > 0 and w not in gone:
            return w
    return turn


def _glow(leds, pad):
    """Start this wand's turn: light the wand and its Splat. Returns True."""
    leds.fill(BLUE)
    pad.color("turnblue")
    return True


def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
    reader = NfcReader(nfc, COMMANDS)
    pad = net.local.unit(0) if net.local and net.local.count else None
    frame = 0
    my_turn = False
    turn = None
    gone = set()
    try:
        if net.is_leader:
            turn = _next(net, len(net.wands) - 1, gone)
            if turn == net.me:
                my_turn = _glow(leds, pad)
            else:
                net.send(turn, {"go": 1})
        while True:
            if frame % NFC_EVERY == 0:
                cmd, _uid = reader.read_command(timeout=100)
                if cmd in _EXIT_TAGS:
                    return

            ev = net.poll()
            if ev in (("leader_lost",), ("end",)):
                return
            done = False
            if ev and ev[0] == "msg" and ev[2].get("go"):
                my_turn = _glow(leds, pad)
            elif ev and ev[0] == "press" and my_turn:
                # The leader gets pool indexes: only its own Splats count here.
                if not net.is_leader or net.owner(ev[1]) == net.me:
                    my_turn = False
                    leds.fill(OFF)
                    pad.off()
                    buz.beep(880, 60)
                    if net.is_leader:
                        done = True
                    else:
                        net.send(0, {"done": 1})
            elif net.is_leader and ev and ev[0] == "msg" and ev[2].get("done"):
                done = True
            elif net.is_leader and ev and ev[0] == "wand_lost":
                gone.add(ev[1])
                done = ev[1] == turn
            elif net.is_leader and ev and ev[0] == "wand_back":
                gone.discard(ev[1])

            if done:
                turn = _next(net, turn, gone)
                if turn == net.me:
                    my_turn = _glow(leds, pad)
                else:
                    net.send(turn, {"go": 1})
            time.sleep_ms(LOOP_MS)
            frame += 1
    finally:
        leds.off()
```
