# NFC Station (M5 Dial 2)

Standalone NFC card reader/writer. Reads a card's NDEF text, writes known
tags grouped by game, and writes free text entered on the dial. USB serial
only; no radio.

Status: Phase 0 (hardware and layout probes). No station firmware yet.

## Hardware

Same as the Broadcast Dial: M5 Dial 2 (StampS3A), UIFlow2 MicroPython.
`dial_board.make_reader()` prefers an external Grove RFID2 (WS1850S) on
Port A (sda=13 scl=15) and falls back to the built-in reader.

## Copied files

Copies, not imports. Fixing one fixes only this copy.

| File | Source |
|---|---|
| `dial_board.py`, `ws1850s.py`, `card_writer.py`, `dial_input.py`, `boot.py`, `reset_log.py`, `json_link.py` | `Bag3/Code/BroadcastCode/BroadcastDial/BDialFirmware/` |
| `game_tags.py` | `Bag3/Code/BroadcastCode/MockWand/lib/` |

## Card format and case

Cards carry plain NDEF text (`card_writer.write_text`). Readers that consume
text (MockWand, SplatCompanion, IconDisplay `nfc_reader.py`) lowercase it,
so text entry offers lowercase only. The Bag3 Wand Module reads 4-byte
opcodes (`Bag3/Code/lib/opcodes.py`) and does not read these cards.

## UI rules

- Minimum text 28 px; 40 px for the focused item; 48 px for glyphs
  (`station_fonts.py`).
- No rectangular roller. Layouts use the rim: ring selector, curved
  carousel, ring keyboard (`tools/ui_sketches.py`).
- Content inside the ~170x170 inscribed square; rim reserved for
  selection/position arcs and touch keys.

## Phase 0 tools

Copy the tree to `/flash`, then:

```
mpremote run tools/font_probe.py    # which of 28/32/36/40/48 px fonts exist
mpremote run tools/ui_sketches.py   # turn = move, click = select, hold = next sketch
```

If `font_probe.py` reports a size missing, convert Montserrat at that size
with the LVGL font converter (binary output) to
`/flash/fonts/montserrat_<size>.bin`; `station_fonts.py` loads it.

Record results (fonts found, legibility at ~1 m, detents per selection,
`mem_free` per sketch) in `docs/circular-ui-notes.md`.
