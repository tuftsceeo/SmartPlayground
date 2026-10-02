# NFC Station (M5 Dial 2)

Standalone NFC card reader/writer. Reads a card's NDEF text, writes known
tags grouped by game, and writes free text entered on the dial. USB serial
only; no radio.

Status: firmware written; **not yet run on hardware**. Logic is covered by
host tests (`tools/test_station.py`); LVGL layout and fonts are unverified.

## Hardware

Same as the Broadcast Dial: M5 Dial 2 (StampS3A), UIFlow2 MicroPython.
`dial_board.make_reader()` prefers an external Grove RFID2 (WS1850S) on
Port A (sda=13 scl=15) and falls back to the built-in reader.

## Files

| File | Role |
|---|---|
| `main.py` | Boot: M5, input, UI, then `Station.run()` |
| `station.py` | Mode machine, scan/write, serial commands |
| `station_ui.py` | Round-screen painter (ring, carousel, status, keyboard pages) |
| `station_fonts.py` | 28 / 40 / 48 px fonts; built-in or `/flash/fonts/*.bin` |
| `text_entry.py` | Ring keyboard state machine (no display code) |
| `tag_catalog.py` | Tags grouped by game; word bank |
| `tools/test_station.py` | Host tests (CPython, fakes) |
| `tools/font_probe.py`, `tools/ui_sketches.py` | On-device Phase 0 probes |
| `tools/deploy_station.py` | Verified per-file deploy |

Copies, not imports -- fixing one fixes only this copy:

| File | Source |
|---|---|
| `dial_board.py`, `ws1850s.py`, `card_writer.py`, `dial_input.py`, `boot.py`, `json_link.py` | `Bag3/Code/BroadcastCode/BroadcastDial/BDialFirmware/` |
| `game_tags.py` | `Bag3/Code/BroadcastCode/MockWand/lib/` |

## Controls

| Input | Action |
|---|---|
| Turn | Move selection |
| Click | Select |
| Hold 1 s | Back |
| Tap a rim item (keyboard) | Select and act on it |

## Screens

1. **Home** ring: Read / Tags / Text.
2. **Read**: hold a card; its text and card type show. Click copies the
   text to the next card presented.
3. **Tags**: game carousel, then that game's tags, then hold a card to
   write. A card already carrying the text is not rewritten.
4. **Text**: ring keyboard.
   - Rim: groups `a f k p u z 0 5` (first character shown, full group in
     the centre), words, delete, done.
   - Click a group to put its characters on the rim; click one to type it.
   - Words: whole tag names and `/flash/words.json` entries.
   - Centre: typed text, selection, byte count `n/54`.
   - Hold with text entered asks for a second hold to discard.

Writes are verified by reading back. A failed write re-arms the same scan.

## Card format, length and case

- Plain NDEF text (`card_writer.write_text`).
- **54 bytes max.** Readers read NTAG pages 4-19 (64 bytes); NDEF text
  overhead is 10 bytes.
- **Lowercase only.** MockWand, SplatCompanion and IconDisplay
  `nfc_reader.py` lowercase card text, so the keyboard has no capitals and
  serial `write` lowercases.
- The Bag3 Wand Module reads 4-byte opcodes (`Bag3/Code/lib/opcodes.py`)
  and does not read these cards.
- `getcode` tags are excluded: their written form needs a Broadcast
  Dial/Box host id.

## Catalog

`/flash/catalog.json` uses the Dial's `games/index.json` shape:

```json
{"goalrace": {"name": "Goalrace", "tags": ["goalrace", "teamgreen", "goal"]}}
```

A Dial's `index.json` can be copied as-is. Without the file, one group per
game in `game_tags.GAME_TAGS` is used. A "Controls" group (start, stop) is
always present.

## Serial (newline JSON)

| Command | Reply |
|---|---|
| `{"cmd":"identify"}` | `identity` with `text_max` |
| `{"cmd":"catalog.get"}` | `catalog` with `groups`, `words` |
| `{"cmd":"catalog.set","index":{...}}` | `ok`; saved to `/flash/catalog.json` |
| `{"cmd":"words.set","words":[...]}` | `ok`; saved to `/flash/words.json` |
| `{"cmd":"write","text":"..."}` | `ok`; opens a scan for that text |
| `{"cmd":"home"}`, `{"cmd":"reboot"}` | `ok` |

Events: `card_read`, `card_written`, `write_failed`, `heartbeat`.

## UI rules

- Minimum text 28 px; 40 px for the focused item; 48 px for glyphs.
- No rectangular roller. Selection lives on the rim (ring, arc); the
  centre names it large.
- Content inside the ~170 px inscribed square.
- Every result pairs a glyph and a beep with its colour.

## Running

```
python3 tools/test_station.py                       # host tests
python3 tools/deploy_station.py /dev/cu.usbmodemXXXX
mpremote run tools/font_probe.py                    # fonts present?
mpremote run tools/ui_sketches.py                   # layout comparison
```

If `font_probe.py` reports a size missing, convert Montserrat at that size
with the LVGL font converter (binary output, include the LVGL symbol range
F001-F8FF for the glyphs) to `/flash/fonts/montserrat_<size>.bin`.

Record hardware results in `docs/circular-ui-notes.md`.
