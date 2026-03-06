# Color Quest — Wand Module System

A multi-device ESP-NOW game where students use a wand to find NFC-tagged color targets in order, racing against the clock. Scores are displayed live on a NeoPixel bar graph.

---

## System Overview

```
┌──────────────────┐   ESP-NOW broadcast (new game)    ┌─────────────────────┐
│  station_test/   │  ──────────────────────────────►  │   color_quest.py    │
│  main.py         │   ["turnred","turnblue",...]        │   (Wand Module)     │
│  (4-reader hub)  │                                     │   finds NFC tags    │
└──────────────────┘                                     └──────────┬──────────┘
         │                                                          │
         │  ESP-NOW broadcast (also received                        │ ESP-NOW unicast
         │  by scoreboard for game-reset detection)                 │ (SCORE_MAC)
         │                                                          │
         └──────────────────────────────────────┐                  │
                                                ▼                  ▼
                                       ┌──────────────────────────────┐
                                       │     slide_score_display.py   │
                                       │     (Score Board)            │
                                       │     40-LED bar graph         │
                                       └──────────────────────────────┘
```

---

## Devices & Files

### `station_test/main.py` — The Hub Station
- **Hardware:** ESP32-C6 with 4× PN532 NFC readers on a PCA9546 I2C mux, 18-LED NeoPixel strip
- **Role:** Operator presses a button → all 4 NFC readers are polled simultaneously → the color sequence is broadcast via ESP-NOW to all wand modules **and** the scoreboard
- **Output message:** `["turnred", "turnblue", "turngreen", "turnpurple"]` (JSON array, broadcast to `FF:FF:FF:FF:FF:FF`)
- **Effect on scoreboard:** Any station broadcast is treated as the start of a new game — the scoreboard resets automatically

### `color_quest.py` — The Wand Module
- **Hardware:** ESP32-C6 with one PN532 NFC reader, 5×5 NeoPixel matrix (25 LEDs), piezo buzzer, push button
- **Role:** Receives the color sequence, then the student searches for and taps matching NFC tags in the correct order
- **Display:**
  - Row 0 (top): target color sequence — dim = upcoming, pulsing = current, bright = done
  - Rows 1–3: scan animation and breathing glow of current target color
  - Row 4 (bottom): collected colors
- **On win:** calculates elapsed time and sends a score message to the scoreboard via `SCORE_MAC`
- **Button:** replays the last received sequence; prints a waiting message if no sequence has arrived yet
- **Timer:** starts when the game begins; resets on button-press restart or if a new sequence arrives mid-game

### `slide_score_display.py` — The Score Board
- **Hardware:** ESP32-C6 with a 40-pixel NeoPixel strip wired as a serpentine 4×10 grid
- **Role:** Listens for score messages and station broadcasts, displays the last 4 scores as a bar graph
- **Bar graph:**
  - Each column = one score, left-to-right in arrival order (oldest drops when a 5th arrives — FIFO)
  - **Fastest time = tallest bar** (full 10 rows); all others scale down proportionally
  - Each bar has a guaranteed minimum height (`MIN_ROWS = 2`) so even slow players have a visible bar
  - **Bar colors are assigned per score in arrival order** from a vivid palette (orange → cyan → magenta → yellow → spring green → …), cycling every 8 scores. The same wand submitting again (retry or shared between kids) just gets the next color naturally
- **Score arrival animation:** four-phase magical sequence — gold sparkles scatter across the strip, a comet shoots up the new column, the column bursts white, then a rainbow blooms row-by-row before settling into the final bar graph
- **New game detection:** resets automatically when a station broadcast arrives, or when a score's game sequence doesn't match the current one. Reset plays a white pixel-wipe animation
- **Startup:** sweeps all pixels white one-by-one, then flashes each of the 4 game colors across the full strip

### `target.py` — Scoreboard MAC Address
- **Role:** Stores the MAC address of the score display device so wand modules know where to send scores
- **Used by:** `color_quest.py` (imported as `SCORE_MAC`)

---

## ESP-NOW Message Formats

### Station → Everyone (broadcast to `FF:FF:FF:FF:FF:FF`)
```json
["turnred", "turnblue", "turngreen", "turnpurple"]
```
A JSON array of color command strings. Wand modules receive this as the sequence to hunt. The scoreboard receives it as a new-game signal and resets.

Special value `"stop"` (as a bare string or in the array) tells wand modules to return to idle.

### Wand → Scoreboard (unicast to `SCORE_MAC`)
```json
{
  "type": "score",
  "colors": ["turnred", "turnblue"],
  "time_ms": 14230,
  "time_s": 14.23
}
```
- `colors` — the game sequence the player completed (used to detect game changes)
- `time_ms` — elapsed time in milliseconds from game start to last tag found
- `time_s` — same value rounded to 2 decimal places

---

## Score Bar Color Palette

Bar colors are assigned in arrival order, cycling through this palette regardless of which wand sent the score:

| # | Color | RGB |
|---|---|---|
| 1 | Orange | (255, 80, 0) |
| 2 | Cyan | (0, 220, 220) |
| 3 | Magenta | (220, 0, 220) |
| 4 | Yellow | (220, 220, 0) |
| 5 | Spring green | (0, 200, 80) |
| 6 | Crimson | (200, 0, 80) |
| 7 | Periwinkle | (80, 100, 255) |
| 8 | Pink | (255, 100, 180) |

Colors reset to orange at the start of each new game.

---

## Game Color Names

These are the NFC tag values used in the game sequence:

| Name | Color |
|---|---|
| `turnred` | Red |
| `turnblue` | Blue |
| `turngreen` | Green |
| `turnpurple` | Purple |
| `turnyellow` | Yellow |
| `turnwhite` | White |
| `turnoff` | Off |

---

## Setup

### 1. Find the scoreboard MAC address
Flash and run this snippet on the score display device:
```python
import network
sta = network.WLAN(network.STA_IF)
sta.active(True)
print(':'.join('%02X' % b for b in sta.config('mac')))
```

### 2. Update `target.py`
```python
SCORE_MAC = b'\xB4\x3A\x45\x86\x1A\x5C'  # replace with your device's MAC
```

### 3. Deploy files
| File | Goes on |
|---|---|
| `station_test/main.py` | Hub station ESP32-C6 |
| `color_quest.py` + `target.py` + `/lib/*` | Each wand module ESP32-C6 |
| `slide_score_display.py` | Score display ESP32-C6 |

### 4. Required `/lib/` files on wand modules
- `pn532.py`
- `nfc_reader.py`
- `buzzer.py`

---

## Timing Notes

- The timer starts when `run_game()` begins (after the color sequence is received and the display clears)
- The opening fanfare (~600ms) is included in the elapsed time — players hear the start tone and go
- A button-press reset **restarts the timer** for the same sequence
- If a new ESP-NOW sequence arrives mid-game, the timer resets for the new sequence

---

## Score Display Scaling

The score board is designed for obstacle course times roughly in the **30 second – 3 minute** range.

- Fastest player in the current set always gets the **full 10-row bar**
- All others: `proportion = fastest_ms / this_ms` — a player who took twice as long gets half the bar
- `MIN_ROWS = 2` ensures even a slow player has a visible bar
- When a faster time arrives and beats the current leader, **all bars rescale** — kids can watch the leaderboard shift in real time

---

## Wiring Summary

### Hub Station (`station_test/main.py`)
| ESP32-C6 Pin | Connected To |
|---|---|
| GPIO22 (SDA) | PCA9546 SDA |
| GPIO23 (SCL) | PCA9546 SCL |
| GPIO1 | PCA9546 RESET |
| GPIO2 | All PN532 RSTPDN |
| GPIO21 | LED strip DIN |
| GPIO0 | Button → GND |

### Wand Module (`color_quest.py`)
| ESP32-C6 Pin | Connected To |
|---|---|
| GPIO22 (SDA) | PN532 SDA |
| GPIO23 (SCL) | PN532 SCL |
| GPIO20 | NeoPixel matrix DIN |
| GPIO19 | Buzzer |
| GPIO0 | Button → GND |

### Score Display (`slide_score_display.py`)
| ESP32-C6 Pin | Connected To |
|---|---|
| GPIO0 (A0) | NeoPixel strip DIN |
