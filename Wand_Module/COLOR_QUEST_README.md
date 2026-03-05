# Color Quest — Wand Module System

A multi-device ESP-NOW game where students use a wand to find NFC-tagged color targets in order, racing against the clock. Scores are displayed live on a NeoPixel bar graph.

---

## System Overview

```
┌──────────────────┐      ESP-NOW broadcast       ┌─────────────────────┐
│  station_test/   │  ──────────────────────────►  │   color_quest.py    │
│  main.py         │   ["turnred","turnblue",...]   │   (Wand Module)     │
│  (4-reader hub)  │                                │   finds NFC tags    │
└──────────────────┘                                └──────────┬──────────┘
                                                               │
                                                   ESP-NOW unicast (SCORE_MAC)
                                                   {"type":"score","colors":[...]
                                                    "time_ms":...,"time_s":...}
                                                               │
                                                               ▼
                                                   ┌─────────────────────┐
                                                   │ slide_score_display │
                                                   │ .py  (Score Board)  │
                                                   │ 40-LED bar graph    │
                                                   └─────────────────────┘
```

---

## Devices & Files

### `station_test/main.py` — The Hub Station
- **Hardware:** ESP32-C6 with 4× PN532 NFC readers on a PCA9546 I2C mux, 18-LED NeoPixel strip
- **Role:** Operator presses a button → all 4 NFC readers are polled simultaneously → the color sequence is broadcast via ESP-NOW to all wand modules
- **Output message:** `["turnred", "turnblue", "turngreen", "turnpurple"]` (JSON array, broadcast to `FF:FF:FF:FF:FF:FF`)

### `color_quest.py` — The Wand Module
- **Hardware:** ESP32-C6 with one PN532 NFC reader, 5×5 NeoPixel matrix (25 LEDs), piezo buzzer, push button
- **Role:** Receives the color sequence, then the student searches for and taps matching NFC tags in the correct order
- **Display:**
  - Row 0 (top): target color sequence — dim = upcoming, pulsing = current, bright = done
  - Rows 1–3: scan animation and breathing glow of current target color
  - Row 4 (bottom): collected colors
- **On win:** calculates elapsed time and sends a score message to the scoreboard
- **Button:** replays the last received sequence; does nothing if no sequence has arrived yet

### `slide_score_display.py` — The Score Board
- **Hardware:** ESP32-C6 with a 40-pixel NeoPixel strip wired as a serpentine 4×10 grid
- **Role:** Listens for score messages via ESP-NOW and displays the last 4 scores as a proportional bar graph
- **Bar graph:** each column = one score; bar height proportional to `time_ms` relative to the longest time in the current set; bar color matches the player's device color
- **Startup:** sweeps all pixels white one-by-one, then flashes each of the 4 device colors across the full strip

### `target.py` — Scoreboard MAC Address
- **Role:** Stores the MAC address of the score display device so wand modules know where to send scores
- **Used by:** `color_quest.py` (imported as `SCORE_MAC`)

---

## ESP-NOW Message Formats

### Station → Wand (broadcast)
```json
["turnred", "turnblue", "turngreen", "turnpurple"]
```
A JSON array of color command strings. The wand module receives this as the sequence to hunt.

Special value `"stop"` (as a bare string or in the array) tells the wand to return to idle.

### Wand → Scoreboard (unicast to `SCORE_MAC`)
```json
{
  "type": "score",
  "colors": ["turnred", "turnblue"],
  "time_ms": 14230,
  "time_s": 14.23
}
```
- `colors` — the sequence the player completed (same as what was sent by the station)
- `time_ms` — elapsed time in milliseconds from sequence received to last tag found
- `time_s` — same value rounded to 2 decimal places

---

## Color Names

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
- A button-press reset **restarts the timer** for the same sequence
- If a new ESP-NOW sequence arrives mid-game, the timer resets for the new sequence
- The opening fanfare (~600ms) is included in the elapsed time — players hear the start tone and go

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
