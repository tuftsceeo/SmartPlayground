# Splat games: solo and party

A **Splat** is a pad children press; it lights up and plays sounds. Each wand pairs with up to
**2** Splats (the children tap a Splat's card on the wand beforehand). A wand game drives Splats
through one extra `play()` parameter, `net`. There is no separate Splat file and no
`[DEVICE: splat]` block; everything below goes in the `[DEVICE: wand]` file.

## Choosing: ordinary, solo or party

| The game… | Declare at the top of the wand file | `net` is |
|---|---|---|
| uses no Splats | nothing | `None` (leave `net=None` off or unused) |
| uses this wand's own Splats only: one child or one group, one wand | `SPLATS_LOCAL = n` (1 or 2) | a solo `net` |
| shares Splats between several wands, or wands take turns | `SPLATS_MIN = n` (and optional `SPLATS_MAX = m`) | a party `net` |

- Choose **solo** when one wand is enough (Simon on one Splat, a reaction game for one child). It
  starts instantly and needs no other wands. Choose **party** only when the idea needs several
  wands to share one game.
- Declare **exactly one** of `SPLATS_LOCAL` and `SPLATS_MIN`, as a plain whole number, at the top
  level of the file. Declaring both makes the wand refuse the game.
- `SPLATS_LOCAL` is 1 or 2. `SPLATS_MIN` counts Splats across **all** joined wands (at least 1);
  `SPLATS_MAX`, if set, is at least `SPLATS_MIN`, and the game starts by itself when that many
  have joined.
- A Splat game's `play()` takes **eight** parameters, with `net=None` last:

```python
def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
```

  The wand passes `net` only to an eight-parameter `play()`. Never use `net` without the parameter.

## How a party game starts

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
| `net.is_leader` | `True` on the leader (always `True` in a solo game) |
| `net.me` | this wand's index in `net.wands` (leader is 0) |
| `net.wands` | list of `(mac, identity_color, splat_count)`, leader first |
| `net.local` | this wand's own Splats, or `None` if it has none: `net.local.count`, `net.local.splat(s)` |
| `net.splat_count` | number of Splats in the shared pool |
| `net.splat(i)` | pool Splat `i`. **Leader only** (a follower gets an error): use `net.local.splat(s)` on a follower |
| `net.owner(i)` | index of the wand holding pool Splat `i` |
| `net.send(to, data)` | send a small dict to wand index `to`, or to every other wand with `to=None`. **Party only** |
| `net.poll()` | **call every loop**. Returns one event tuple, or `None` |

A Splat (from `net.splat(i)` or `net.local.splat(s)`) has `color(name)`, `note(name)`,
`sound(name)`, `play([name, name, ...])` (any mix of the three) and `off()`. Use only the names in
the "SPLAT ACTION NAMES" list; any other name is refused when the game is sent. Keep a Splat in a
variable if it is used often: `pad = net.splat(0)`.

Events from `net.poll()`:

| Event | Who gets it | Meaning |
|---|---|---|
| `("press", i)` / `("release", i)` | leader: pool index; a follower: its own local index | a Splat was pressed / let go |
| `("msg", from_wand, data)` | the wand it was sent to | a `net.send()` dict |
| `("splat_lost", i)` / `("splat_back", i)` | leader | a Splat dropped out / came back |
| `("wand_lost", w)` / `("wand_back", w)` | leader | a follower wand went quiet for 3 s / came back |
| `("leader_lost",)` | followers | the leader went quiet for 3 s |
| `("end",)` | followers | the leader ended the game |

## Rules every Splat game follows

- **A follower must return on `("leader_lost",)` and `("end",)`.** Without it the follower's
  wand keeps running a game that no longer exists. The leader decides what a lost wand or Splat
  means (pause, skip that player, or carry on); never ignore it silently.
- Keep the usual wand loop: poll `enow` for `stop`/`start_game`, read cards every `NFC_EVERY`
  loops, `time.sleep_ms(...)` every loop, `leds.off()` in `finally`. In a party game the `enow`
  argument already hands party traffic to `net`; read it exactly as in any other game.
- Do not turn Splats off or say goodbye to other wands at the end: the wand turns its Splats
  off and tells the other wands when `play()` returns, stops or crashes.
- Messages may be lost or arrive late. Prefer **turn-based** designs (one wand or Splat active at
  a time, the leader keeps the score and decides who goes next) over designs that need every wand
  in step at the same instant. The leader should repeat important state rather than send it once.
- Keep `data` dicts small: a few short keys.
- A solo game has no other wands: never call `net.send()` in it (the send is refused).

## Example: solo (one wand, one Splat)

```python
"""
Splat Flash -- press the Splat when it turns green
"""
import time
import random
from machine import Pin

from nfc_reader import NfcReader
from game_tags import exit_tags_excluding
from leds import OFF, GREEN, RED

SPLATS_LOCAL = 1
_EXIT_TAGS = exit_tags_excluding("splat_flash")
COMMANDS = _EXIT_TAGS
NFC_EVERY = 10
LOOP_MS = 20


def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
    reader = NfcReader(nfc, COMMANDS)
    pad = net.splat(0)
    frame = 0
    green = False
    next_ms = time.ticks_add(time.ticks_ms(), 1500)
    buz.beep(660, 80)
    try:
        while True:
            msg_type, _d, _m = enow.poll()
            if msg_type in ("stop", "start_game"):
                return
            if frame % NFC_EVERY == 0:
                cmd, _uid = reader.read_command(timeout=100)
                if cmd in _EXIT_TAGS:
                    return
            if not green and time.ticks_diff(time.ticks_ms(), next_ms) >= 0:
                green = True
                pad.color("turngreen")
            ev = net.poll()
            if ev == ("press", 0):
                if green:
                    pad.play(["turnblue", "note_c"])
                    leds.fill(GREEN)
                else:
                    pad.color("turnred")
                    leds.fill(RED)
                green = False
                next_ms = time.ticks_add(time.ticks_ms(), random.randint(1000, 3000))
            elif ev == ("splat_lost", 0):
                leds.fill((25, 0, 0))
            elif ev == ("splat_back", 0):
                leds.fill(OFF)
            time.sleep_ms(LOOP_MS)
            frame += 1
    finally:
        leds.off()
```

## Example: party, pooled (the leader drives every Splat)

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
            msg_type, _d, _m = enow.poll()
            if msg_type in ("stop", "start_game"):
                return
            if frame % NFC_EVERY == 0:
                cmd, _uid = reader.read_command(timeout=100)
                if cmd in _EXIT_TAGS:
                    return
            ev = net.poll()
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
                if ev in (("leader_lost",), ("end",)):
                    return
                if ev and ev[0] == "msg":
                    leds.fill(GREEN)
                    buz.beep(1047, 60)
            time.sleep_ms(LOOP_MS)
            frame += 1
    finally:
        leds.off()
```

## Example: party, messages (each wand drives its own Splat)

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
    pad = net.local.splat(0) if net.local and net.local.count else None
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
            msg_type, _d, _m = enow.poll()
            if msg_type in ("stop", "start_game"):
                return
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
