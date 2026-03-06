# Freeze Dance — Wand Module Multiplayer Game

A wireless multiplayer motion game where one caller controls the music (GO / FREEZE) and all player wands detect whether someone moved when they shouldn't have.

---

## How To Play

1. Every player taps the **FREEZEDANCE** tag on their wand to enter the game.
2. One person taps the **CALLER** tag — they become the DJ/controller. Everyone else taps **PLAYER**.
3. The caller taps **GO** — all player wands light up with a green chase animation. Players dance!
4. The caller taps **FREEZE** — all player wands turn blue. Players must freeze immediately.
5. After a 2-second grace period, wands start checking for motion. If a player moves, their wand beeps three times, flashes a red X, and they're **OUT for 30 seconds**.
6. After the penalty, the player automatically rejoins and waits for the next GO/FREEZE.
7. Tap **STOP** on any wand to exit back to programming mode.

---

## System Architecture

Every wand runs the same code. There is no dedicated station device — any wand can be the caller.

```
  ┌─────────────┐          ESP-NOW broadcast          ┌─────────────┐
  │  Caller      │  ──── FD_GO / FD_FREEZE ────────►  │  Player A   │
  │  Wand        │                                     │  Wand       │
  │  (scans GO / │                                     │  (motion    │
  │   FREEZE)    │                                     │   checked)  │
  └─────────────┘                                      └─────────────┘
         │                                                    │
         │             ESP-NOW broadcast                      │
         └──────────────────────────────────►  ┌─────────────┐
                                               │  Player B   │
                                               │  Wand       │
                                               └─────────────┘
```

---

## Game States

| State | LED Effect | Description |
|---|---|---|
| **Role Select** | Gentle white/purple breathing | Just entered — waiting for CALLER or PLAYER tag |
| **Ready** | Yellow-green pulse (player) / Amber pulse (caller) | Role chosen, waiting for GO or FREEZE |
| **GO** | Green chase animation | Players are dancing — no motion checking |
| **FREEZE** | Blue breathing glow | Players must hold still — motion checked after 2s grace |
| **OUT** | Blinking red X pattern | Caught moving — 30-second penalty, then auto-rejoin |

---

## ESP-NOW Messages

All messages are plain byte strings broadcast to `FF:FF:FF:FF:FF:FF`:

| Message | Sent by | Effect on players |
|---|---|---|
| `FD_GO` | Caller | Enter GO state (green chase) |
| `FD_FREEZE` | Caller | Enter FREEZE state (blue glow + motion detection) |
| `FD_RESET` | Any | Return all wands to READY state |
| `stop` | Any | Exit the game entirely |

---

## NFC Tags

| Tag text | Who scans it | What it does |
|---|---|---|
| `freezedance` | Anyone (in programming mode) | Enters the Freeze Dance game |
| `caller` | The DJ/controller | Assigns caller role — can scan GO and FREEZE |
| `player` | Everyone else | Assigns player role — dances and gets motion-checked |
| `go` | Caller only | Broadcasts GO to all players |
| `freeze` | Caller only | Broadcasts FREEZE to all players |
| `stop` | Anyone | Exits back to programming mode |

---

## Motion Detection

During FREEZE, the accelerometer is polled every ~40ms. The change in acceleration across all three axes is summed:

```
movement = |Δx| + |Δy| + |Δz|
```

If `movement ≥ 0.70g`, a hit counter increments. If below threshold, the counter decrements by 1 (preventing false positives from single jolts). When the counter reaches 2 consecutive hits, the player is caught.

A **2-second grace period** after FREEZE begins gives players time to actually stop — motion checking only activates after the grace window.

### Tuning

| Parameter | Default | Description |
|---|---|---|
| `MOVE_THRESHOLD` | 0.70g | Sum-of-deltas threshold per frame |
| `MOVE_HITS_NEEDED` | 2 | Consecutive frames above threshold to trigger |
| `FREEZE_GRACE_MS` | 2000 | Grace period before motion checking starts |
| `OUT_DURATION_MS` | 30000 | Penalty duration when caught |

To make the game harder (more sensitive), lower `MOVE_THRESHOLD` or reduce `MOVE_HITS_NEEDED` to 1. To make it more forgiving, increase the grace period or raise the threshold.

---

## Integration with main.py

Freeze Dance plugs into the programming engine exactly like Color Quest:

1. `"freezedance"` is added to the `CONTROLS` set in `main.py`.
2. When the tag is scanned, `play_freeze_dance(nfc, leds, buz, accel, i2c)` is called.
3. The game takes over the wand until STOP is triggered.
4. On return, `main.py` restores the programming mode display and state.

The game creates its own ESP-NOW instance on entry and tears it down on exit, so it doesn't interfere with the programming engine's state.

---

## File Deployment

| File | Goes on |
|---|---|
| `freeze_dance.py` | Each wand module (root `/`) |
| Updated `main.py` | Each wand module (root `/`) |

The game uses `/lib/pn532.py`, `/lib/nfc_reader.py`, `/lib/buzzer.py`, and `/lib/lis2dw12.py` — all of which should already be on the wand from the standard setup.

---

## Standalone Testing

`freeze_dance.py` can also be run directly without `main.py` for testing:

```python
import freeze_dance
freeze_dance.main()
```

This initializes all hardware inline and enters the game loop. Press Ctrl+C to exit.
