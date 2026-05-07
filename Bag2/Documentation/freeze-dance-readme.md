# Freeze Dance — Design & Reference

A multiplayer freeze-dance game that runs on the wand modules. All wands run the same `freeze_dance.py`. On entry each wand picks a role (caller or player) by tapping a tag. The caller drives state via button + shake; players are caught by motion (or lack of it) depending on the current command. ESP-NOW carries every state change.

---

## Quick map

| | What it does |
|---|---|
| Caller | Holds button = GO, releases = FREEZE, shakes wand = DANCE |
| Player | Dances on GO, holds still on FREEZE, must keep moving on DANCE |
| Out | Tap REJOIN tag, then press button to come back |

---

## State machine

There are seven states. Players and callers share state IDs but not all states apply to both.

| State | Used by | Color | Entry sound | What it means |
|---|---|---|---|---|
| `STATE_ROLE_SELECT` | both | yellow `(200, 200, 0)` | none | Tap caller or player tag to start |
| `STATE_READY` (caller) | caller | amber `(200, 100, 0)` | join | Idle — waiting to drive the game |
| `STATE_READY` (player) | player | yellow `(200, 200, 0)` | join | In the game, waiting for next command |
| `STATE_GO` | both | green `(0, 200, 0)` | go | Dance freely |
| `STATE_FREEZE` | both | red `(200, 0, 0)` | freeze | Hold still — players checked for movement |
| `STATE_DANCE` | both | purple `(180, 0, 180)` | dance | Keep moving — players checked for stillness |
| `STATE_OUT` | player only | blue sad face on black | out | Caught. Tap REJOIN tag to recover |
| `STATE_REJOIN_ARMED` | player only | white `(140, 140, 140)` | rejoin | Tag tapped — press button to re-enter |

### Player journey when caught

```
FREEZE (red)            ←  caller's command
   ↓ moved too much
OUT (blue sad face)     ←  caught
   ↓ tap REJOIN tag
REJOIN_ARMED (white)    ←  press button to confirm
   ↓ press button
READY (yellow)          ←  back in, waiting
   ↓ caller sends GO
GO (green)              ←  dance!
```

### Caller flow

```
READY (amber)
   ↓ press button
GO (green) — broadcasts FD_GO
   ↓ release button
FREEZE (red) — broadcasts FD_FREEZE
   ↓ shake wand (button must be up)
DANCE (purple) — broadcasts FD_DANCE
   ↓ press button
GO (green) again
```

The caller can shake into DANCE only from READY or FREEZE — never while button is held (would conflict with GO motion) and not from inside DANCE itself.

---

## Color choices and rationale

All colors are tuned for **outdoor sun visibility** without pulling unnecessary current.

| Channel | Brightness | Rationale |
|---|---|---|
| Single channel (red, green, blue) | 200 / 255 ≈ 78% | Maximum perceived brightness per amp. Most efficient. |
| Two channels (yellow, amber, purple) | 200 each ≈ 78% | Each channel still 78%, total current ~2× a single channel state. |
| Three channels (white) | 140 each ≈ 55% | Per-channel dropped so total current stays comparable to two-channel states. White at 200 across 3 channels would draw ~2× more than yellow. |

**Nothing hits 255.** Headroom is intentional — saves battery, reduces heat, prevents premature LED wear.

### Color → meaning mapping

- **Yellow** = waiting (both ROLE_SELECT and player READY use it)
- **Green** = go / active
- **Red** = stop / hold still
- **Purple** = dance / keep moving
- **Blue** = out / sad
- **Amber** = caller idle (warm, distinct from player yellow)
- **White** = press the button (REJOIN_ARMED)

### Known overlap

- ROLE_SELECT and player READY are both yellow. The role-tap flash + beep is the visual/audio cue that the tap registered. If you want them distinct, change `STATE_COLORS[STATE_ROLE_SELECT]` to something else (e.g., `(200, 150, 0)` orange-yellow).
- Caller READY (amber) and player READY (yellow) use the same hue family but are clearly distinguishable. This is intentional — both feel "warm/waiting" while signaling different roles.

---

## Sad face geometry

5×5 NeoPixel grid, indices 0–24. Sad face uses these indices:

```
.  .  .  .  .       0  1  2  3  4
.  X  .  X  .       5  6  7  8  9       ← eyes at 6, 8
.  .  .  .  .      10 11 12 13 14
.  X  X  X  .      15 16 17 18 19       ← frown top at 16, 17, 18
X  .  .  .  X      20 21 22 23 24       ← frown corners at 20, 24
```

Total: 7 lit pixels in deep blue `(0, 0, 200)`. Background is fully off for max contrast in sunlight.

---

## NFC tags

Tags this module recognizes (NDEF text payload, lowercase):

| Tag | Purpose |
|---|---|
| `freezedance` | Enters this game from main.py (not handled inside this module) |
| `caller` | Pick caller role |
| `player` | Pick player role |
| `go` | Caller backup — sends GO |
| `freeze` | Caller backup — sends FREEZE |
| `rejoin` | Player only, when OUT — arms rejoin |
| `stop` | Exit game (caller broadcasts STOP to all wands) |

Tags are read by Mifare Classic reads on sectors 1 and 2, decoded as NDEF text. Repeat-scan guard: same UID within 1.2 seconds is ignored.

---

## ESP-NOW protocol

Plain byte-string messages, no JSON, broadcast to `FF:FF:FF:FF:FF:FF`:

| Message | Sent by | Triggers receiver state |
|---|---|---|
| `FD_GO` | caller (button down) | STATE_GO |
| `FD_FREEZE` | caller (button up) | STATE_FREEZE |
| `FD_DANCE` | caller (shake) | STATE_DANCE |
| `FD_RESET` | (not currently sent) | STATE_READY |
| `stop` | caller (stop tag) | exit game |

### Burst + dedupe

Caller sends each message **5 times in rapid succession** (`BTN_SEND_REPEATS = 5`, `BTN_SEND_DELAY_MS = 1`) to defeat radio packet loss. Receivers dedupe by checking `if self.state != target_state` before transitioning — first message of the burst wins, the other 4 are silently dropped. This means:

- Players beep exactly once per legitimate state change
- The `state_ms` timestamp anchors to the first message, so grace periods (FREEZE_GRACE_MS, DANCE_GRACE_MS) measure accurately

### Caller never reacts to its own broadcasts

The `not self.is_caller` guard on each message branch ensures callers don't process their own outgoing messages (ESP-NOW shouldn't loop back, but the guard makes it impossible regardless).

### Players in OUT or REJOIN_ARMED ignore game-state messages

Once you're out, tags are the only way back. A new GO broadcast won't auto-rejoin you. Same in REJOIN_ARMED — you must press your own button.

---

## Motion detection

Three independent detectors share one accelerometer read per loop iteration. Each has its own hit counter; `motion.reset()` clears all of them on every state change.

| Detector | Used by | Threshold | Hits needed | Triggered by |
|---|---|---|---|---|
| `triggered()` | player in FREEZE | `MOVE_THRESHOLD = 0.70 g` | 2 frames | sum-of-axis-deltas ≥ threshold |
| `too_still()` | player in DANCE | `STILL_THRESHOLD = 0.18 g` | 30 frames (~1.2 s) | sum-of-axis-deltas < threshold for sustained period |
| `shake_detected()` | caller, button up | `SHAKE_THRESHOLD = 1.5 g` | 2 frames | sum-of-axis-deltas ≥ threshold; self-consuming |

The "sum of axis deltas" measures `|Δx| + |Δy| + |Δz|` between two consecutive accel reads. Loop runs every 40 ms, so reads are 40 ms apart.

### Why `too_still` resets to 0 instead of decrementing

`triggered` and `shake_detected` decrement their hit count by 1 when the threshold isn't met (slow recovery). `too_still` resets to 0 the moment any real motion is detected. This is intentional — for stillness detection, even a single frame of motion should "save" the dancer. The forgiving direction matters.

### Grace periods

| Constant | Value | Purpose |
|---|---|---|
| `FREEZE_GRACE_MS` | 1000 ms | After FREEZE starts, players have 1 s to actually freeze before motion checks begin |
| `DANCE_GRACE_MS` | 1500 ms | After DANCE starts, players have 1.5 s to start dancing before stillness checks begin |

Grace periods are anchored to `state_ms`, which only updates on real state changes (the dedupe guard prevents bursts from re-anchoring it).

---

## Tuning guide

Common adjustments and where to make them:

### "Players are getting caught too easily during FREEZE"
- Raise `MOVE_THRESHOLD` (e.g., 0.85 or 1.0) to require more motion
- Or raise `MOVE_HITS_NEEDED` (e.g., 3 or 4) to require sustained motion

### "Players never get caught during FREEZE"
- Lower `MOVE_THRESHOLD` (e.g., 0.5 or 0.4)
- Or lower `MOVE_HITS_NEEDED` to 1 (single-frame trigger)

### "Active dancers are getting flagged as not dancing"
- Raise `STILL_THRESHOLD` (e.g., 0.25 or 0.30)
- Or raise `STILL_HITS_NEEDED` (e.g., 50 frames = 2.0 s) so a brief pause doesn't count

### "Standing still doesn't trigger OUT during DANCE"
- Lower `STILL_THRESHOLD` (e.g., 0.10) — but careful, gravity noise floor is around 0.05 g
- Or lower `STILL_HITS_NEEDED` (e.g., 20 frames = 0.8 s)

### "Caller shake doesn't reliably trigger DANCE"
- Lower `SHAKE_THRESHOLD` (e.g., 1.2 or 1.0)
- Lower `SHAKE_HITS_NEEDED` to 1 (single-frame shake)

### "Caller shake fires accidentally during normal arm movement"
- Raise `SHAKE_THRESHOLD` (e.g., 1.8 or 2.0)
- Raise `SHAKE_HITS_NEEDED` (e.g., 3) to require sustained shaking

### "Colors are too dim for outdoor use"
- In `STATE_COLORS`, bump single-channel values from 200 → 230
- In `READY_PLAYER`, `READY_CALLER`, `SAD_BLUE`: same
- Don't go past 240 on any channel — battery drain compounds

### "Colors are too bright indoors / drains battery"
- Drop single-channel values from 200 → 130
- Drop white from 140 → 90

### "Yellow waiting and green GO look too similar"
- Change `READY_PLAYER` from `(200, 200, 0)` to `(200, 130, 0)` (orange)
- Or `(0, 200, 200)` (cyan) for a fully different hue
- Or `(200, 200, 200)` (white) for "neutral waiting"

### "Beep volume is annoying / not loud enough"
- Sound is in `buzzer.py` — `Buzzer.beep()` uses `duty_u16(32768)` (50% duty cycle, max volume for piezo)
- To reduce volume: lower duty cycle in `Buzzer.beep()` (not in this file)
- To shorten sounds: edit `SOUNDS` dict — drop the durations or skip notes

### "Players need a longer grace before being checked"
- `FREEZE_GRACE_MS = 2000` → 2 s grace before FREEZE motion check
- `DANCE_GRACE_MS = 2500` → 2.5 s grace before DANCE stillness check

### "Want auto-rejoin back, no manual tag tap"
- Re-add the auto-rejoin timer in the run loop:
  ```python
  if self.state == STATE_OUT:
      if time.ticks_diff(time.ticks_ms(), self.state_ms) >= 30_000:
          self._set_state(STATE_READY)
  ```
- Define `OUT_DURATION_MS = 30_000` near the other constants

---

## Hardware

| Component | Pin | Notes |
|---|---|---|
| Button | GPIO 0 (`SWITCH_PIN`) | Active low, internal pull-up |
| LED strip | GPIO 20 | NeoPixel, 25 LEDs in 5×5 |
| I2C SDA | GPIO 22 | PN532 + LIS2DW12 + others |
| I2C SCL | GPIO 23 | 100 kHz (PN532 unreliable at 400) |
| Buzzer | GPIO 19 | PWM-driven piezo |
| WiFi enable | GPIO 3 | Toggle low → external antenna |
| Antenna config | GPIO 14 | High → external antenna |

The wand main module configures all of this before calling `play()`. Standalone mode in this file's `main()` reconfigures it for solo testing.

### Required libraries (in `/lib/`)

- `pn532.py` — NFC reader driver
- `nfc_reader.py` — NDEF decode + Mifare keys
- `buzzer.py` — PWM buzzer wrapper
- `lis2dw12.py` — accelerometer driver

---

## Code structure (compacted version)

The module is organized as:

1. **Constants** — pins, message bytes, state IDs, motion tuning, timing
2. **Lookup tables** — `STATE_COLORS`, `STATE_ENTRY_SOUND`, `BROADCASTS`, `SOUNDS`
3. **Hardware setup** — antenna config, ESP-NOW init
4. **LED + sound helpers** — `_fill`, `_off`, `_flash`, `_sad_face`, `_play`
5. **NFC reader** — `_read_tag_text`
6. **`MotionChecker`** — three detectors + reset
7. **`FreezeDanceGame`** — main class
8. **Entry points** — `play()` for main.py, `main()` for standalone

### Lookup tables ↔ behavior

- **`STATE_COLORS[state] = (r, g, b)`** — `_render` does dict lookup; READY and OUT are special-cased
- **`STATE_ENTRY_SOUND[state] = 'name'`** — `_set_state` looks up the sound to play on entry
- **`BROADCASTS['name'] = (msg, state)`** — `_broadcast` looks up which message to send and which state to enter
- **`SOUNDS['name'] = [(freq, dur, gap), ...]`** — `_play` iterates the sequence

To add a new state, sound, or broadcast, add a row to the relevant dict — no other code changes needed for simple additions.

---

## Maintenance recipes

### Add a new state

1. Add to the tuple unpacking near the top: `STATE_NEW = 7`
2. Add color: `STATE_COLORS[STATE_NEW] = (r, g, b)`
3. Add entry sound (optional): `STATE_ENTRY_SOUND[STATE_NEW] = 'name'`
4. Add transition logic in `run()` for whatever event causes entry/exit

### Add a new sound

1. Add a row to `SOUNDS`:
   ```python
   'whatever': [(freq1, dur1, gap1), (freq2, dur2, gap2), ...]
   ```
2. Call `_play(self.buz, 'whatever')` wherever you want it

### Add a new caller broadcast

1. Define the message: `MSG_NEW = b"FD_NEW"`
2. Add to `BROADCASTS`: `'name': (MSG_NEW, STATE_NEW)`
3. Call `self._broadcast('name')` from caller logic
4. Add receive branch in the ESP-NOW handler:
   ```python
   elif msg == MSG_NEW and self.state != STATE_NEW:
       self._set_state(STATE_NEW); print("  NEW")
   ```

### Add a new NFC tag command

1. Add the tag string to `GAME_COMMANDS`
2. Add a branch in `run()` after the `cmd == "stop"` block:
   ```python
   elif cmd == "newcmd" and <preconditions>:
       <action>
   ```
3. Write the string to a Mifare tag (NDEF text, lowercase)

---

## Design decisions (and what got rejected)

### No animations (replaces pulse + green chase)

Original code had pulsing breathing on most states and a moving-dot chase for GO. Removed because:
- Animation math (sin wave) requires `import math` — extra RAM
- Per-frame computation runs every 40 ms — small but constant CPU cost
- Distinguishable by color alone once colors are bright enough
- Battery is the constraint outdoors; static colors at fixed brightness are predictable and easier to budget

If you want pulsing back, the simplest path is to add a `_pulse(np, r, g, b, period_ms)` helper using `time.ticks_ms()` for the phase, and call it from `_render` instead of `_fill`.

### Manual rejoin (no auto-recovery)

Original code had a 30-second auto-rejoin timer. Replaced with manual tag tap + button press because:
- Gives kids agency over when to rejoin (less arbitrary feeling)
- Simpler state machine — no timer to track
- Forces a deliberate action so kids know they're rejoining

The two-step process (tag → button) was specifically chosen to confirm intent and avoid accidental rejoins from a tag swipe.

### Caller shake gated to button-up

Shake detection during button-down would conflict with the natural arm movement of vigorous GO commanding. Restricting to "button up + state in READY/FREEZE" means the caller can't accidentally fire DANCE while waving the wand for GO.

### `STILL_THRESHOLD` is asymmetric (resets vs decrements)

`triggered` decrements its hit count slowly (forgiving recovery for FREEZE). `too_still` resets to 0 the moment any motion is detected. This asymmetry makes both detectors err on the side of giving the player benefit of the doubt — moving a little during FREEZE forgives gradually, but moving once during DANCE clears the stillness counter immediately.

### State ID via `range(7)` tuple unpacking

Means state IDs are positional. If you reorder the tuple, all IDs shift. Don't reorder unless you check for hardcoded numeric state IDs anywhere (there shouldn't be any — everything uses the symbolic names).

---

## Standalone test mode

Run `python freeze_dance.py` directly on the wand to test without the main.py boot sequence. The `main()` function reinitializes I2C, NeoPixel, accelerometer, NFC, and buzzer with the standard pin assignments, then runs the game. Ctrl-C exits cleanly.

This is useful for:
- Iterating on state transitions without re-flashing main.py
- Debugging ESP-NOW broadcasts in isolation
- Testing motion thresholds without other modules' interference

---

## Open knobs / future work

- **Player count display** — there's no UI showing how many players are still in. Could broadcast a "still in" heartbeat from each player and aggregate at the caller.
- **Caller-side last-out indicator** — caller has no way to know which player just got out. Could broadcast `FD_OUT:<mac>` from players when caught.
- **Tunable round timer** — currently the caller decides when to stop. A countdown or auto-end after N seconds would simplify scoring.
- **Music sync** — buzzer beeps are functional but not musical. A connected speaker via the splat companion could play actual music synced to GO/FREEZE.
- **Replace shake with a different trigger for DANCE** — shake works but is easy to do accidentally during energetic calling. A second NFC tag (`dance` tag) would be more deliberate, at the cost of needing the caller to put the wand down to scan.
