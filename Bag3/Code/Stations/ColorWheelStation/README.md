# Color Wheel Station

Bag3 station: **one XIAO ESP32-C6** with **four M5Stack WS1850S RFID readers**.
Press the button and it scans all four readers, reads each tag's NDEF text (a
colour like `turngreen`), and broadcasts the four colours over ESP-NOW for the
`color_quest` wand game.

```
          ┌─ reader 1 (SoftI2C)
          ├─ reader 2 (SoftI2C)
button ─▶ ESP32-C6 ─ reader 3 (SoftI2C) ──ESP-NOW──▶ wand (color_quest)
          └─ reader 4 (SoftI2C)
```

Beta / bench prototype — not used by teachers or the team.

## Why four SoftI2C buses

The WS1850S readers are all fixed at I2C address **0x28**, so they can't share
one bus. Each reader gets its own bit-banged `SoftI2C` bus on its own pins.
The scan is sequential (reader 1→4), so only one bus is active at a time.

## Wiring (pins fixed by the breakout board)

Silk D-number → GPIO:

| Item | Pins | GPIO |
|---|---|---|
| Reader 1 | SCL D5 / SDA D4 | 23 / 22 |
| Reader 2 | SCL D2 / SDA D3 | 2 / 21 |
| Reader 3 | SCL D7 / SDA D6 | 17 / 16 |
| Reader 4 | SCL D0 / SDA D1 | 0 / 1 |
| Button | D8 | 19 |
| NeoPixel (later) | free pin (e.g. D9) | 20 |

> **Reader 3 is on D6/D7 = GPIO16/17, the C6's UART0 console pins** — verified
> working for I2C in testing. If the REPL ever misbehaves while reader 3 is
> active, that's the reason.

All readers share 3V3 + GND from the one ESP (its own USB powers everything —
no multi-board rail, no brown-out chain).

## The button

Set `BUTTON_ACTIVE_HIGH` in `main.py`. The bench button was active-high (to
3V3 with an external pull-down); flip to `False` for a button wired to GND.
Boot log prints each reader's version, so a mis-wired bus is visible there.

## ESP-NOW message

Broadcasts a bare list of colour names, e.g.
`["turngreen", "turnblue", "turnred", "turnyellow"]`. `espnow_manager.poll()`
classifies a JSON list as msg_type `"colors"`, which `color_quest`
(`Bag3/Code/Wand Module/color_quest.py`) consumes; it keeps only entries that
match its known colours, so a `NO_TAG` `"?"` is dropped wand-side.

**Valid colour tags** (the wand's `COLOR_BRIGHT` keys): `turnred`,
`turngreen`, `turnblue`, `turnpurple`, `turnpink`, `turnyellow`, `turnwhite`,
`turnoff`. Write your reader tags with those exact strings.

## Starting the wand game

Tap an NFC tag with the text **`colorquest`** on the wand to launch Color
Quest; it then waits for a colour sequence. Press this station's button to
send one.

## Files

`main.py` is the only original file. The rest are **per-tree copies** from
`Bag3/Code/Stations/IconDisplay/lib/` (same XIAO C6 + WS1850S hardware), kept
by hand per the repo's duplication convention:

- `ws1850s.py` — WS1850S I2C driver
- `nfc_ws1850s.py` — PN532-shaped shim over the WS1850S (`Ws1850sReader`)
- `nfc_reader.py` — NDEF text read for MIFARE Classic 1K + NTAG
- `espnow_manager.py` — ESP-NOW; onboard antenna (`EXTERNAL_ANTENNA = False`)

## Status

Reader driver and ESP-NOW verified on hardware (single board). Full 4-reader
scan + broadcast not yet confirmed end-to-end; reader 3 on the console pins is
untested. `python -m py_compile` passes (the only off-device check).

Earlier revisions of this folder held a 4-board UART-chain design; see git
history on branch `color-wheel-station`.
