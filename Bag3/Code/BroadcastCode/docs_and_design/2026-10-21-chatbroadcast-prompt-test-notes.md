# ChatBroadcast prompt test notes — 2026-10-21

Raw log of prompt tests. Results and comments are recorded as given; no analysis until the notes are marked done.

Status: open

## Prompts under test

Numbering follows the list as given (3-8).

**Wands + Splats**

3. "Make a simple single-wand game with the wand's paired Splats. The wand shows a smile for 5 seconds. Then one random paired Splat lights green. When that Splat is pressed, the wand beeps and a different random Splat lights green. Only one Splat is lit at a time. The game does not have an end or a score."
4. "Make a simple multiplayer lobby game with Splats. The wands show a smile for 5 seconds, then create or join a lobby, at least 2 wands. When the game starts, each wand lights its own paired Splats in that wand's color. When a lit Splat is pressed, its wand beeps and that Splat turns off for 3 seconds, then lights again. The game does not have an end or a score."

**Wands + Icon Display**

5. "Make a simple single-wand game with the Icon Display. The wand shows a smile for 5 seconds. When the wand's button is pressed, the Icon Display shows a random animal icon and the wand beeps. The game does not have an end or a score."
6. "Make a simple multiplayer lobby game with the Icon Display. The wands show a smile for 5 seconds, then create or join a lobby, at least 2 wands. When the game starts, one wand holds a star and the Icon Display shows the star in that wand's color. When the star wand's button is pressed, the star passes to another random wand and the display changes to the new wand's color. Only one wand has the star at a time. The game does not have an end or a score."

**Wands + Splats + Icon Display**

7. "Make a simple single-wand game with the wand's paired Splats and the Icon Display. The wand shows a smile for 5 seconds. Then one random paired Splat lights. When it is pressed, the Icon Display shows a heart icon for 1 second and a different Splat lights. The game does not have an end or a score."
8. "Make a simple multiplayer lobby game with Splats and the Icon Display. The wands show a smile for 5 seconds, then create or join a lobby, at least 2 wands. When the game starts, one wand holds a star, its paired Splats light yellow, and the Icon Display shows a star. When the star wand's button is pressed, the star passes to another random wand: the old wand's Splats turn off and the new wand's Splats light yellow. Only one wand has the star at a time. The game does not have an end or a score."

## Entries

### 3. Single-wand Splat hop (user wrote "response for 1"; matched to the first prompt, which this game fits)

**Generated game:** `green_splat_hop` ("Green Splat Hop -- press the green Splat, then the other one lights up")

```python
"""
Green Splat Hop -- press the green Splat, then the other one lights up
"""
import time
import random

from nfc_reader import NfcReader
from game_tags import exit_tags_excluding
from leds import YELLOW, SHAPE_HAPPY_FACE

SPLATS_MIN = 2
_EXIT_TAGS = exit_tags_excluding("green_splat_hop")
COMMANDS = _EXIT_TAGS
NFC_EVERY = 10
LOOP_MS = 20
SMILE_MS = 5000


def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
    reader = NfcReader(nfc, COMMANDS)
    frame = 0
    lit = None
    lost = set()
    started = False
    t0 = time.ticks_ms()
    buz.beep(659, 100)
    leds.show_shape(SHAPE_HAPPY_FACE, YELLOW)
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
                if not started and time.ticks_diff(time.ticks_ms(), t0) >= SMILE_MS:
                    started = True
                    leds.off()
                if ev and ev[0] == "splat_lost":
                    lost.add(ev[1])
                    if lit == ev[1]:
                        lit = None
                elif ev and ev[0] == "splat_back":
                    lost.discard(ev[1])
                elif ev and ev[0] == "press" and ev[1] == lit:
                    net.splat(lit).off()
                    buz.beep(880, 80)
                    prev = lit
                    lit = None
                    choices = [i for i in range(net.splat_count)
                               if i != prev and i not in lost]
                    if choices:
                        lit = random.choice(choices)
                        net.splat(lit).color("turngreen")
                if started and lit is None:
                    choices = [i for i in range(net.splat_count) if i not in lost]
                    if choices:
                        lit = random.choice(choices)
                        net.splat(lit).color("turngreen")
            else:
                if ev == ("leader_lost",):
                    return
            time.sleep_ms(LOOP_MS)
            frame += 1
    finally:
        leds.off()
```

**Result:** Game started immediately after loading. There was no chance to pair Splats in advance, and pairing after the game started did not work.

**Comments:**
- Prefers being able to pair Splats after the game has started, if at all possible.
- Wish: when a game is waiting for a button press, flash a down arrow pointing at the button to prompt the action (for people who don't read the info before the chat).
- Wish: when sending to the Dial, besides the game name, also allow entering a game symbol (e.g. shape and color drop-downs). The symbol would show for about a second before the game begins, to indicate it is starting.

### 4. Multiplayer Splat lobby game

**Generated game:** not pasted.

**Result / Comments:** "Basically the same notes" as entry 3: game started immediately after loading with no chance to pair Splats in advance, pairing after start did not work, and pairing after start is preferred. The button-prompt arrow and game-symbol wishes from entry 3 also apply.

## General observations (not tied to one prompt)

- After ChatBroadcast sits unused for a while, the entire browser freezes. Suggestion: pause/disable the simulation after 30 seconds without any interaction with it, to save memory.
- The frozen tab was using 13 GB of memory when force-closed.
- Sequence: the tab was working normally. Prompted, code was generated, simulation tested, code sent to the Dial. Then the tab sat unused for a while. On return, the browser was frozen and the tab's memory was in the 13 GB state.
