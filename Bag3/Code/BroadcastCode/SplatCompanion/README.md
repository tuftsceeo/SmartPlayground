# Splat Companion station

A Bag3 game station for stock Splat toys, built from two Seeed XIAO
ESP32-C6 boards:

```
SPLAT <-[BLE]-> Companion (hub) <-[UART]-> ESPNowModem <-[ESP-NOW]-> playground
```

| Tree | Board | Role |
|---|---|---|
| `Companion/` | XIAO C6 #1 (hub) | Games, BLE to the Splats, PN532 card reader, MAX17048, 12-LED ring; reaches ESP-NOW only through the modem |
| `ESPNowModem/` | XIAO C6 #2 | UART <-> ESP-NOW bridge (EUM firmware) |

Both boards run plain MicroPython; files go to `/` and `/lib/`.

## Wiring between the boards

| Hub | Modem |
|---|---|
| GPIO16 (D6), TX | GPIO17 (D7), RX |
| GPIO17 (D7), RX | GPIO16 (D6), TX |
| GND | GND |

Hub-only wiring (PN532 I2C on GPIO22/23, NeoPixel ring on GPIO20) is in
`Companion/README.md`.

## Upload

- **Modem:** `ESPNowModem/main.py` → `/main.py`; `ESPNowModem/lib/*.py` →
  `/lib/`.
- **Hub:** see `Companion/README.md` "Deploying". Bring it up in stages
  with `Companion/bench/` first.

## Relation to `../EspnowModem/`

`../EspnowModem/` is the separate S3-to-S3 proof of concept and is left
as is. `ESPNowModem/main.py` is a C6-only copy of its `modem/main.py`
(pins and board setup changed, logic unchanged). These files are byte
copies of it, checked by `Companion/test_splat_companion.py`
(`test_copies_match`):

- `ESPNowModem/lib/eum_proto.py`, `ESPNowModem/lib/eum_classify.py`
- `Companion/lib/eum_proto.py`, `Companion/lib/espnow_manager.py`
