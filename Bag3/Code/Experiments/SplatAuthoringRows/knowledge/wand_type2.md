# Type 2: one wand, 1-2 Splats (add to devices/wand.md)

DRAFT. A child plays alone with Splats paired to their own wand. No lobby, no `net`.

Declare `SPLATS_LOCAL = n` (1 or 2) at the top level. `play()` takes an eighth parameter,
`splats=None`. Do not declare `SPLATS_MIN`, `SPLAT_HOST`, and do not use `net`.

```python
def play(nfc, leds, buz, accel, i2c, enow, batt=None, splats=None):
```

The loop is the ordinary wand loop (see the canonical template): `enow.poll()` every loop and
return on `"stop"` / `"start_game"`, cards every `NFC_EVERY`, `time.sleep_ms(...)` every loop,
`leds.off()` in `finally`. Add one line: `ev = splats.poll()`.

## The `splats` object

| Member | Meaning |
|---|---|
| `splats.count` | Splats connected now (at least `SPLATS_LOCAL`) |
| `splats.unit(i)` | Splat `i`: `color(name)`, `note(name)`, `sound(name)`, `play([name, ...])`, `off()` |
| `splats.poll()` | call every loop: `("press", i)`, `("release", i)` or `None` |

The wand starts the game only if at least `SPLATS_LOCAL` Splats are connected, so inside `play()`
`splats` is never `None` and `splats.count >= SPLATS_LOCAL`. No guard is needed. Use only names from
the SPLAT ACTION NAMES list.

A Splat's lights split as **inner/outer** or **left/right**: `color(name, part)` sets only that
part. Use one split at a time. `play()` and `off()` act on the whole Splat.

| Color | Wand (`leds`) | Splat `color()` |
|---|---|---|
| red | `RED` | `"turnred"` |
| green | `GREEN` | `"turngreen"` |
| blue | `BLUE` | `"turnblue"` |
| yellow | `YELLOW` | `"turnyellow"` |
| purple | `PURPLE` | `"turnpurple"` |
| white | `WHITE` | `"turnwhite"` |

A Splat that stands for something stays lit in its color; after a press, flash or play a note,
then return to the color. The wand turns the Splats off itself after the game; do not.

## Example: Color Pads (press the Splat that matches the wand)

```python
"""
Color Pads -- press the Splat that glows the same color as the wand
"""
import time
import random

from nfc_reader import NfcReader
from game_tags import exit_tags_excluding
from leds import RED, BLUE, SHAPE_STAR, MINT

GAME_ICON = (SHAPE_STAR, MINT)
SPLATS_LOCAL = 2
_EXIT_TAGS = exit_tags_excluding("color_pads")
COMMANDS = _EXIT_TAGS
NFC_EVERY = 10
LOOP_MS = 20
CHOICES = (("turnred", RED), ("turnblue", BLUE))


def play(nfc, leds, buz, accel, i2c, enow, batt=None, splats=None):
    reader = NfcReader(nfc, COMMANDS)
    n = SPLATS_LOCAL
    frame = 0
    score = 0
    try:
        for i in range(n):
            splats.unit(i).color(CHOICES[i][0])
        want = random.randrange(n)
        leds.fill(CHOICES[want][1])
        while True:
            msg_type, data, _mac = enow.poll()
            if msg_type in ("stop", "start_game"):
                return
            if frame % NFC_EVERY == 0:
                cmd, _uid = reader.read_command(timeout=100)
                if cmd in _EXIT_TAGS:
                    return
            ev = splats.poll()
            if ev and ev[0] == "press":
                if ev[1] == want:
                    score += 1
                    splats.unit(ev[1]).play(["turnwhite", "note_c"])
                    time.sleep_ms(200)
                    splats.unit(ev[1]).color(CHOICES[ev[1]][0])
                    want = random.randrange(n)
                    leds.fill(CHOICES[want][1])
                else:
                    buz.beep(200, 150)
            time.sleep_ms(LOOP_MS)
            frame += 1
    finally:
        leds.off()
```

`[GAME_SETTINGS: {"splats": 2, "wands": 1}]` (see `station_mode.md` for the settings change).
