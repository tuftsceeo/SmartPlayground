# Device: Wand  (`[DEVICE: wand]`)

## What it is and who sees it

A handheld wand each child holds: a 5×5 grid of colored lights on the front, a buzzer, a button, a
vibration motor, an accelerometer (senses tilting, shaking and jumping), and an NFC reader that
reads cards tapped against it. Board: Seeed XIAO ESP32-C6, MicroPython v1.27. Several wands can
play at once; each runs its own copy of the game.

It has **no screen and no speaker for music** — only the light grid, simple beeps, and vibration.

## The `play()` contract

The wand calls a game with exactly seven arguments, in this order:

```python
def play(nfc, leds, buz, accel, i2c, enow, batt=None):
```

Write all seven, even if the game uses only some. A shorter signature crashes at launch with
`TypeError`. (The icon display and Splat Companion have different signatures; never use theirs.)

| Argument | What it is | Notes |
|---|---|---|
| `nfc` | PN532 card reader, already started | Wrap it: `reader = NfcReader(nfc, COMMANDS)` |
| `leds` | the 5×5 light grid (`Leds`) | Already built |
| `buz` | the buzzer (`Buzzer`) | Already built |
| `accel` | accelerometer (`LIS2DW12`, ±4 g, 100 Hz) | **May be `None`** — guard with `if accel:` |
| `i2c` | the shared I2C bus | Rarely needed; never change its speed |
| `enow` | ESP-NOW manager, already started | Never `None`; poll every loop |
| `batt` | battery gauge (`MAX17048`) | **May be `None`** — guard with `if batt:` |

Never create another `ESPNowManager`, `Leds`, `Buzzer`, `PN532` or I2C bus inside a game.

## Canonical template

Start every new wand game from this shape. Replace `"your_game"` with the game's slug: the
`[GAME_NAME:]` in snake_case (see platform rules). Replace the entry sound with one that differs
from the built-in games.

```python
"""
<Game title> — <one line on what the children do>
"""
import time
import math
from machine import Pin

from nfc_reader import NfcReader
from game_tags import exit_tags_excluding
from leds import OFF, RED, GREEN, BLUE, YELLOW, SHAPE_HEART

_EXIT_TAGS = exit_tags_excluding("your_game")
COMMANDS = _EXIT_TAGS            # add this game's own cards: _EXIT_TAGS | {"red", "blue"}
NFC_EVERY = 10                   # read cards every N loops (~0.5 s)
LOOP_MS = 50


def play(nfc, leds, buz, accel, i2c, enow, batt=None):
    """Called by the wand when this game is chosen."""
    reader = NfcReader(nfc, COMMANDS)
    btn = Pin(0, Pin.IN, Pin.PULL_UP)
    btn_was_down = (btn.value() == 0)
    frame = 0

    for freq, ms in ((523, 80), (659, 80), (784, 120)):   # entry sound
        buz.beep(freq, ms)
    try:
        while True:
            # 1. Stop when the teacher switches games
            msg_type, data, _mac = enow.poll()
            if msg_type in ("stop", "start_game"):
                return

            # 2. Cards, every NFC_EVERY loops
            if frame % NFC_EVERY == 0:
                cmd, uid = reader.read_command(timeout=100)
                if cmd in _EXIT_TAGS:
                    return
                # elif cmd == "red": ...

            # 3. Button press (edge only)
            down = (btn.value() == 0)
            if down and not btn_was_down:
                pass                      # button was just pressed
            btn_was_down = down

            # 4. Motion
            if accel:
                x, y, z = accel.read()
                strength = math.sqrt(x * x + y * y + z * z)
                # strength > 1.4 -> shaken; strength < 0.3 -> jumping

            # 5. Game logic and lights here

            time.sleep_ms(LOOP_MS)
            frame += 1
    finally:
        leds.off()
```

## API

### Lights — `leds`

Import color and shape names from `leds`; they are tuned for the hardware and dim automatically in
bright rooms. Do not use raw `(r, g, b)` tuples for these colors.

- **Colors:** `OFF RED ROSE ORANGE AMBER YELLOW LIME GREEN TEAL CYAN BLUE INDIGO PURPLE MAGENTA
  WHITE PINK PEACH MINT SKY`, and dim versions `RED_DIM GREEN_DIM BLUE_DIM YELLOW_DIM WHITE_DIM
  ORANGE_DIM AMBER_DIM PINK_DIM PURPLE_DIM`.
- **Shapes** (tuples of light positions for `show_shape`):
  - Numbers and letters: `SHAPE_0`–`SHAPE_9`, `SHAPE_A`–`SHAPE_Z`
  - Symbols: `SHAPE_HEART SHAPE_STAR SHAPE_DIAMOND SHAPE_CHECK SHAPE_X SHAPE_LIGHTNING SHAPE_MUSIC
    SHAPE_QUESTION SHAPE_EXCLAIM SHAPE_PLUS SHAPE_HOUSE SHAPE_TREE SHAPE_FLAME SHAPE_MOON
    SHAPE_RAINDROP SHAPE_FISH SHAPE_BIRD SHAPE_PACMAN SHAPE_INVADER SHAPE_GHOST SHAPE_CHECKERS
    SHAPE_SPIRAL SHAPE_HOURGLASS SHAPE_BULLSEYE SHAPE_PLAY SHAPE_PAUSE SHAPE_POINTER SHAPE_POWER
    SHAPE_RECTANGLE SHAPE_FASTFORWARD SHAPE_REWIND`
  - Faces: `SHAPE_HAPPY_FACE SHAPE_SAD_FACE SHAPE_ANGRY_FACE SHAPE_NEUTRAL_FACE SHAPE_SL_FACE
    SHAPE_SLEEPY_FACE`
  - Arrows: `SHAPE_ARROW_UP SHAPE_ARROW_DN SHAPE_ARROW_L SHAPE_ARROW_R SHAPE_DIAG_L SHAPE_DIAG_R`
  - Grid parts: `SHAPE_TOP_ROW SHAPE_ROW2 SHAPE_ROW3 SHAPE_ROW4 SHAPE_BOT_ROW SHAPE_LEFT_COL
    SHAPE_COL2 SHAPE_COL3 SHAPE_COL4 SHAPE_RIGHT_COL SHAPE_BORDER SHAPE_INNER_3x3 SHAPE_CORNERS
    SHAPE_CENTER SHAPE_SLASH_L SHAPE_SLASH_R`
- **Grid layout:** light index = `row * 5 + col`, 0 at top-left, 24 at bottom-right.

| Call | What it does |
|---|---|
| `leds.off()` | All lights off |
| `leds.fill(RED)` | All lights one color |
| `leds.show_shape(SHAPE_HEART, RED, bg=OFF)` | A shape in a color |
| `leds.show_pattern({RED: (0, 4), GREEN: (12,)})` | Several groups of lights in different colors |
| `leds.flash_color(RED, times=2, on_ms=120, off_ms=80)` | Flash all lights (pauses the game while flashing) |
| `leds.breathe(130, 0, 0, frame)` | Slow glow; call every loop with the frame count |
| `leds.breathe_shape(SHAPE_HEART, RED, frame)` | Glowing shape; call every loop |
| `leds.pulse_color(130, 0, 0, duration_ms=600)` | One pulse then off (pauses the game) |
| `leds.fade_shape(SHAPE_STAR, YELLOW, 800)` | Fade a shape out (pauses the game) |
| `leds.np[i] = GREEN` then `leds.np.write()` | Set single lights |

Animations — call every loop with the frame count; bigger `frames_per_step` is slower:
`leds.animate_spin(frame, BLUE)`, `animate_dancer`, `animate_rows`, `animate_columns`,
`animate_grow`, `animate_shrink`, `animate_arrow_spin`, `animate_firework`.

### Sound — `buz`

| Call | Sound |
|---|---|
| `buz.beep(freq, ms)` | One tone (pauses the game while it plays). C4=262, E4=330, G4=392, A4=440, C5=523, E5=659, G5=784, C6=1047 |
| `buz.melody()` | Short rising tune |
| `buz.confirm()` / `buz.success()` / `buz.celebrate()` | Right answer / success / big win |
| `buz.start()` / `buz.stop()` | Entering / leaving a mode |
| `buz.reject()` / `buz.warn()` / `buz.error()` | Wrong / warning / error |
| `buz.tick()` / `buz.info()` / `buz.question()` | Small feedback sounds |

### Cards — `NfcReader`

- `reader = NfcReader(nfc, COMMANDS)`; `COMMANDS` is every card value the game reacts to, always
  including `_EXIT_TAGS`.
- `cmd, uid = reader.read_command(timeout=100)` returns the card value (or `None`) and the card's
  unique id. Read only every `NFC_EVERY` loops.
- To react once per tap, remember the last `uid` and ignore repeats until `uid` is `None` again.

### Button

`Pin(0, Pin.IN, Pin.PULL_UP)`; pressed reads `0`. Read the starting state before the loop (as in
the template) so a button held at start does not count as a press.

### Motion — `accel`

`x, y, z = accel.read()` in g. At rest the total is about 1.0 (gravity). Measured on the wand:

| Wand position | Reading |
|---|---|
| Upright (tip up, handle down) — normal holding | `x ≈ -1` |
| Upside down (handle up) | `x ≈ +1` |
| Left side raised | `y ≈ +1` |
| Right side raised | `y ≈ -1` |
| Lights facing up (lying flat, face up) | `z ≈ -1` |
| Lights facing down | `z ≈ +1` |

- Shake: `strength > 1.4`. Jump / free fall: `strength < 0.3`. A lean: that axis passes ±0.5.
- "Tilt left" is ambiguous. Pick one meaning (for example "left side down", `y < -0.5`) and say it
  in How to play.

### Vibration

```python
motor = Pin(21, Pin.OUT, value=0)
motor.value(1); time.sleep_ms(200); motor.value(0)
```
Keep buzzes short; the motor draws a lot of power.

### Battery

`if batt: volts, percent = batt.read_all()`

## Everyday words → code

| The teacher says | Use |
|---|---|
| "light up red", "turn red" | `leds.fill(RED)` |
| "turn off", "go dark" | `leds.off()` |
| "flash", "blink" | `leds.flash_color(RED, 3)` |
| "show a heart / star / smiley" | `leds.show_shape(SHAPE_HEART, RED)` / `SHAPE_STAR` / `SHAPE_HAPPY_FACE` |
| "show the number 3", "the letter A" | `leds.show_shape(SHAPE_3, GREEN)` / `SHAPE_A` |
| "rainbow", "all the colors" | cycle `[RED, ORANGE, YELLOW, GREEN, BLUE, PURPLE]` with `(frame // 6) % 6` |
| "glow", "breathe" | `leds.breathe(...)` or `leds.breathe_shape(...)` each loop |
| "spin", "dance", "firework" | `leds.animate_spin` / `animate_dancer` / `animate_firework` |
| "beep", "happy sound", "sad sound" | `buz.beep(1000, 200)` / `buz.confirm()` / `buz.reject()` |
| "press the button" | button edge, as in the template |
| "shake it" | `strength > 1.4` |
| "jump" | `strength < 0.3` |
| "hold it upright" / "turn it upside down" | `x < -0.5` / `x > 0.5` |
| "lay it flat, lights up" | `z < -0.8` |
| "tap a card" | `reader.read_command(...)` every `NFC_EVERY` loops |
| "vibrate", "rumble" | motor on pin 21 |
| "start / freeze the music" | `enow.broadcast("FD_GO")` / `enow.broadcast("FD_FREEZE")` — plays on the speaker devices |

## Limits and why

- **Read cards only every 10–15 loops.** A read takes 200–500 ms; reading every loop freezes the
  lights and motion.
- **Poll `enow` every loop.** Otherwise the teacher cannot switch games.
- **`flash_color`, `pulse_color`, `fade_shape` and `beep` pause the loop.** Keep them short, or
  the game feels stuck and misses cards.
- **Only use the imports shown here.** Library files on the wand (`main.py`, `leds.py`, …) are not
  editable from the app.
- **Keep the file small** (platform size budget). The wand refuses files over 32 KB.

## Checklist

- [ ] `[DEVICE: wand]` before the block
- [ ] `def play(nfc, leds, buz, accel, i2c, enow, batt=None):` — all seven
- [ ] `_EXIT_TAGS = exit_tags_excluding("<slug>")`; game cards unioned into `COMMANDS`
- [ ] `enow.poll()` every loop; return on `"stop"` / `"start_game"`
- [ ] Cards read every `NFC_EVERY` loops; return on any `_EXIT_TAGS` card
- [ ] `accel` and `batt` guarded; `leds.off()` in `finally`
- [ ] Colors and shapes imported from `leds`; no f-strings
- [ ] Every card value listed in `[NFC_CARDS: ...]`
