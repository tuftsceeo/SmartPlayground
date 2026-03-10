# Code

All MicroPython application code for the Smart Playground system. Four device types communicate over ESP-NOW and BLE.

## Folder Structure

```
Code/
├── lib/                              Shared library (copy to ALL devices)
│   ├── hubtype.py                    Device type detection from hubtype.txt
│   ├── espnow_manager.py            Unified ESP-NOW communication
│   ├── pn532.py                      PN532 NFC reader driver (I2C)
│   ├── lis2dw12.py                   LIS2DW12 accelerometer driver
│   ├── max17048.py                   MAX17048 battery fuel gauge driver
│   ├── opt3002.py                    OPT3002 ambient light sensor driver
│   ├── nfc_reader.py                 NFC scanning, NDEF decode, SC tag passthrough
│   ├── leds.py                       NeoPixel control (auto-adapts to LED count)
│   ├── buzzer.py                     Piezo buzzer sounds
│   ├── actions.py                    Action defs, resource mapping, chain execution
│   ├── battery.py                    Battery display (works with any LED count)
│   ├── gesture.py                    Legacy gesture module
│   └── gesture_engine.py            Gesture recognition with NFC templates
│
├── Wand Module/
│   ├── main.py                       NFC trigger→action engine
│   ├── color_quest.py                Color Quest scavenger hunt
│   ├── freeze_dance.py               Freeze Dance multiplayer game
│   ├── target.py                     Scoreboard MAC config
│   ├── hubtype.txt                   Contains: wand
│   └── readme.md
│
├── Splat Companion/
│   ├── main.py                       ESP-NOW ↔ BLE bridge
│   ├── ble_splat.py                  BLE driver for Open Splat
│   ├── hubtype.txt                   Contains: splat_companion
│   └── readme.md
│
└── Stations/
    ├── Programming Station/
    │   ├── main.py                   4×PN532 hub, broadcasts via ESP-NOW
    │   ├── hubtype.txt               Contains: programming_station
    │   └── readme.md
    └── Slide Score Station/
        ├── main.py                   40-LED serpentine bar graph
        ├── hubtype.txt               Contains: score_board
        └── readme.md
```

## How hubtype.txt Works

Each device has a `hubtype.txt` file in its root containing a single word. The shared `hubtype.py` library reads this at boot and configures hardware constants:

| hubtype.txt | LEDs | LED Pin | Battery | NFC | Accel | Buzzer | BLE | Uses BLE |
|---|---|---|---|---|---|---|---|---|
| `wand` | 25 | GPIO20 | Yes | Yes | Yes | Yes | Yes | No |
| `splat_companion` | 3 | GPIO20 | Yes | No | No | No | Yes | Yes (Splat) |
| `programming_station` | 18 | GPIO21 | No | Yes | No | No | Yes | No |
| `score_board` | 40 | GPIO0 | No | No | No | No | Yes | No |

All ESP32-C6 boards have BLE hardware. The `uses_ble` flag indicates whether the device actively maintains a BLE connection (currently only the Splat Companion).

## Deployment

### Every device needs:

1. **`/lib/` folder** — copy the entire lib folder
2. **`hubtype.txt`** — one word identifying the device type
3. **Device-specific files** — `main.py` and any extras

### Per-device files:

| Device | Root files needed |
|---|---|
| **Wand** | `main.py`, `color_quest.py`, `freeze_dance.py`, `target.py`, `hubtype.txt` |
| **Splat Companion** | `main.py`, `ble_splat.py`, `hubtype.txt` |
| **Programming Station** | `main.py`, `hubtype.txt` |
| **Scoreboard** | `main.py`, `hubtype.txt` |

### Quick deploy with mpremote:

```bash
# Copy lib to any device:
mpremote connect <PORT> fs cp -r lib/ :/lib/

# Create hubtype.txt (example for wand):
echo "wand" > /tmp/hubtype.txt
mpremote connect <PORT> fs cp /tmp/hubtype.txt :/hubtype.txt

# Copy device main:
mpremote connect <PORT> fs cp "Wand Module/main.py" :/main.py
```

## Station Broadcast Commands

The Programming Station broadcasts whatever tags are on its 4 readers. Special broadcasts recognized by all devices:

| Station Tags | Broadcast | Effect |
|---|---|---|
| `battery` | `["battery"]` | All devices show their battery level on LEDs |
| `stop` | `["stop"]` | All devices return to default state |
| Colors | `["turnred", "turnblue", ...]` | Wands enter Color Quest, scoreboard resets |

## ESP-NOW Message Types

All devices use `ESPNowManager` which classifies messages:

| msg_type | Source | Format | Description |
|---|---|---|---|
| `"colors"` | Station | `["turnred", ...]` | Color/command list |
| `"score"` | Wand | `{"type":"score", ...}` | Game score |
| `"splat_config"` | Wand | `{"type":"splat_config", "actions":[...]}` | Config for companion |
| `"stop"` | Any | `["stop"]` or `{"type":"stop"}` | Stop everything |
| `"battery"` | Station | `["battery"]` | Show battery levels |
| `"raw"` | Any | bytes | Freeze Dance messages etc. |

## NFC Tag Summary

| Category | Tags |
|---|---|
| **Triggers** | `buttondown`, `buttonup`, `shake` |
| **Colors** | `turnred`, `turngreen`, `turnblue`, `turnpurple`, `turnyellow`, `turnwhite`, `turnoff` |
| **Notes** | `notea`–`noteg`, `playnote` |
| **Animal Sounds** | `cat`, `chicken`, `cow`, `dog`, `pig`, `duck`, `elephant`, `horse`, `goat` |
| **Combinators** | `and`, `then` |
| **Controls** | `start`, `stop`, `colorquest`, `freezedance` |
| **Utility** | `battery` |
| **Splat Companion** | `SC:<MAC>` (e.g., `SC:B4:3A:45:86:1C:8C`) |
| **Gestures** | Binary `G:` prefix (written by gesture engine) |