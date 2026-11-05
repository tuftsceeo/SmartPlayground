# Color Wheel Station

Bag3 station: four **XIAO ESP32-C6** boards in a daisy chain, each with an
M5Stack **WS1850S** RFID reader. Press the button on the first board; each
board in turn reads its own NFC tag's text (a colour like `green`, `blue`),
concatenates it, and passes the growing string down a one-way soft-UART
chain. The last board broadcasts the full chain over ESP-NOW.

```
[first] --UART--> [middle] --UART--> [middle] --UART--> [last] ==ESP-NOW==>
 ESP1              ESP2               ESP3               ESP4
 button            scan+append        scan+append        scan+append+broadcast
```

Beta / bench prototype — not used by teachers or the team.

## Wiring (per XIAO ESP32-C6)

Pin *positions* are the silkscreen D-numbers; GPIOs are what the code uses.

| Function | Position | GPIO | Notes |
|---|---|---|---|
| Button | D2 | 2 | first node only; bench board is active-high (to 3V3 + external pull-down). Set `BUTTON_ACTIVE_HIGH` in main.py |
| RFID SDA | D4 | 22 | I2C, WS1850S @ 0x28, 100 kHz |
| RFID SCL | D5 | 23 | |
| UART TX out | D0 | 0 | -> next board's D7 (RX) |
| UART RX in | D7 | 17 | <- previous board's D0 (TX) |

UART is **crossed by the cable** (`D0 -> D7`), so every board runs the same
single-UART config. The first node uses only TX, the last only RX. The two
leftover wires per link (D1/D6) carry the unused reverse direction. A
**common ground** between boards is required.

> **Power:** if the boards are each USB-powered, do *not* also link 3V3
> between them — just TX/RX/GND. The last node runs the radio, and a shared
> 3V3 rail (four readers + ESP-NOW) can brown out. See the EspnowModem notes.

## Antenna

These boards use the **onboard** antenna (no u.FL fitted). Only the last
node brings up the radio; `espnow_manager.py` here sets `EXTERNAL_ANTENNA =
False` (GPIO14 = 0). See `Bag3/AGENTS.md`.

## Flashing

Same files on all four boards; set `ROLE` at the top of `main.py` per board:

- ESP1 -> `ROLE = "first"`
- ESP2, ESP3 -> `ROLE = "middle"`
- ESP4 -> `ROLE = "last"`

Tunables in `main.py`: `SCAN_TIMEOUT_MS`, `NO_TAG` (placeholder when a station
has no readable tag), `DELIM`, `UART_BAUD`.

The last node broadcasts a bare list of colour names, e.g.
`["green", "blue", "red", "yellow"]`. `espnow_manager.poll()` classifies a
JSON list as msg_type `"colors"`, which is what the `color_quest` wand game
(`Bag3/Code/Wand Module/color_quest.py`) listens for; it filters each entry
against its known colours, so a `NO_TAG` `"?"` is dropped wand-side.

## Files

`main.py` is the only original file. The rest are **per-tree copies** from
`Bag3/Code/Stations/IconDisplay/lib/` (same XIAO C6 + WS1850S hardware),
kept by hand per the repo's duplication convention — fixing one does not fix
the others:

- `ws1850s.py` — WS1850S I2C driver
- `nfc_ws1850s.py` — PN532-shaped shim over the WS1850S (`Ws1850sReader`)
- `nfc_reader.py` — NDEF text read for MIFARE Classic 1K + NTAG
- `espnow_manager.py` — ESP-NOW; **diverges** from the copy source only in
  the antenna comment (onboard, as there too)

## Status

Written against known-good sibling drivers; **not yet run on hardware.**
`python -m py_compile` passes (the only off-device check — `machine`,
`espnow`, etc. do not exist off-device). Verify on the four boards before a PR.
