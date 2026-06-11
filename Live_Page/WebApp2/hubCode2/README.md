# Hub2 — USB Serial to ESP-NOW Bridge (Wand Protocol)

## Overview

Hub2 is an ESP32-C6 hub that bridges LivePage2 (USB Serial/WebSerial) to Bag2 wands (ESP-NOW). It speaks the wand protocol: game commands are dispatched by **name** via `broadcast_start_game()`, not the Bag1 plushie `GAME_MAP` integer indices.

## Hardware

- **ESP32-C6** with external antenna (recommended)
- USB cable for Serial communication
- MicroPython firmware
- Optional SSD1306 OLED (128x64, I2C pins SCL=23, SDA=22)

External antenna GPIO is configured automatically on **ESP32-C6 only** (`espnow_manager._is_esp32c6()`). Other boards (S3, C3, generic) skip antenna pin setup.

## Files

```
hubCode2/
├── main.py              # Serial bridge + command handler
├── espnow_manager.py    # Copy of Bag2/Code/lib/espnow_manager.py
├── game_tags.py         # Copy of Bag2/Code/lib/game_tags.py
├── ssd1306.py           # Optional OLED driver
└── manifest.js          # File list for webapp firmware upload
```

## Installation

### Flash MicroPython

```bash
esptool.py --chip esp32c6 --port /dev/ttyUSB0 erase_flash
esptool.py --chip esp32c6 --port /dev/ttyUSB0 write_flash -z 0x0 micropython_esp32c6.bin
```

### Upload files

```bash
ampy --port /dev/ttyUSB0 put main.py
ampy --port /dev/ttyUSB0 put espnow_manager.py
ampy --port /dev/ttyUSB0 put game_tags.py
ampy --port /dev/ttyUSB0 put ssd1306.py   # optional
```

Or use LivePage2 **Setup as Hub** (uploads via WebSerial REPL).

## Serial Protocol (Hub2 ↔ LivePage2)

- Line-delimited JSON, 115200 baud, each message ends with `\n`

### Commands (webapp → hub)

```json
{"cmd": "colorquest"}
{"cmd": "freezedance"}
{"cmd": "stop"}
{"cmd": "poll"}
```

Valid `cmd` values: any tag in `game_tags.py::GAME_TAGS`, plus `"stop"` and `"poll"`.

### Responses (hub → webapp)

```json
{"type": "ready", "mac": "AA:BB:CC:DD:EE:FF", "version": "v1.0.0", "timestamp": 12345}
{"type": "ack", "command": "colorquest", "status": "sent"}
{"type": "heartbeat", "timestamp": 12345, "uptime": 5000}
{"type": "poll_started", "timestamp": 12345}
{"type": "device_report", "id": "W-A1B2", "mac": "...", "battery": 85, "rssi": -55, "timestamp": 12345}
{"type": "devices", "list": [...], "timestamp": 12345}
```

## ESP-NOW Protocol (Hub2 → Wands)

| Serial `cmd`   | ESP-NOW payload                              |
|----------------|----------------------------------------------|
| `<game_tag>`   | `{"type": "start_game", "name": "<tag>"}`    |
| `stop`         | `["stop"]`                                   |
| `poll`         | `{"type": "status_poll"}` (×3)               |

Game commands are sent **twice** with a 100ms gap for reliability (broadcast is unacknowledged).

## Bench Testing

1. Flash and boot — confirm `ESPNow: active (MAC: ...)` and `{"type":"ready",...}` on serial.
2. Send `{"cmd":"colorquest"}\n` — wand in range should enter Color Quest.
3. Send `{"cmd":"freezedance"}\n` — wand force-switches games.
4. Send `{"cmd":"stop"}\n` — wand returns to idle.
5. Send `{"cmd":"poll"}\n` — wands reply with battery/signal; hub streams `device_report` then `devices`.
6. Send `{"cmd":"nonsense"}\n` — hub logs `Unk:`, no ack, wand unchanged.

## References

- Wand protocol: `Bag2/Code/lib/espnow_manager.py`
- Game tags: `Bag2/Code/lib/game_tags.py`
- LivePage2 webapp: `../` (parent directory)
