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
| `station_ui.py` | Round-screen painter (icon ring, dot ring, result ring, ring keyboard) |
| `station_fonts.py` | 28 / 40 / 48 px built-in fonts, smaller fallback |
| `text_entry.py` | Ring keyboard state machine (no display code) |
| `tag_catalog.py` | Tags grouped by game; word bank |
| `tools/test_station.py` | Host tests (CPython, fakes) |
| `tools/font_probe.py`, `tools/ui_sketches.py` | On-device Phase 0 probes |
| `docs/ui_simulator.html` | Browser simulation of every screen |

Copies, not imports -- fixing one fixes only this copy:

| File | Source |
|---|---|
| `dial_board.py`, `ws1850s.py`, `card_writer.py`, `dial_input.py`, `json_link.py` | `Bag3/Code/BroadcastCode/BroadcastDial/BDialFirmware/` |
| `game_tags.py` | `Bag3/Code/BroadcastCode/MockWand/lib/` |

`dial_input.py` has diverged on purpose: it adds `hold_fraction()` for the
hold-progress ring, and `clear()` marks a still-held press as spent so its
release after a hold does not register as a click.

## Controls

| Input | Action |
|---|---|
| Turn | Move selection |
| Click | Select |
| Hold 1 s | Back (a grey rim ring fills while holding; nothing on Home) |
| Tap a rim item (keyboard) | Select and act on it |

## Screens

Every selector puts its choices on the rim at fixed angles: turning the
dial moves the highlight around the ring the same way the knob turns, and
the centre names the selection large.

1. **Home**: icon ring -- three coloured circles (Read, Tags, Text); the
   selected one is enlarged and outlined, its name in the centre.
2. **Read**: hold a card; its text and card type show inside a result
   ring. Click copies the text to the next card presented.
3. **Tags**: dot ring of games, then a dot ring of that game's tags (one
   dot per item, selected dot large, name in the centre, `n/N` below;
   past 24 items a position arc replaces the dots). Hold a card to write.
   A card already carrying the text is not rewritten.
4. **Text**: segmented ring keyboard.
   - Rim: `a`-`z`, `_` (space), `#`, delete, done -- 30 items, one detent
     each, in tinted sections of three. Each item's arc slot is sized to
     its glyph width, so `m` and `w` do not crowd their neighbours.
   - Click types the highlighted item; the highlight stays, so repeated
     and nearby letters need no extra turns. Tapping a rim item types it.
   - `#` swaps the rim to `0`-`9`, `-`, `.`, words, `abc`, delete, done.
   - Words: dot ring of tag names and `/flash/words.json` entries; the
     chosen word is appended with a space.
   - Centre: typed text (trimmed from the left to fit), the highlighted
     item at 48 px, byte count `n/54`.
   - Hold leaves. If the text is not yet on a card, a trash glyph asks
     for a second hold to discard it.

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
- No rectangular roller. Selection lives on the rim and rotates with the
  dial; the centre names it large.
- Content inside the ~170 px inscribed square.
- Every result pairs a glyph and a beep with its colour.

## Running

Device files (12): `main.py station.py station_ui.py station_fonts.py
text_entry.py tag_catalog.py game_tags.py dial_board.py dial_input.py
card_writer.py ws1850s.py json_link.py`. Everything under `tools/` and
`docs/` stays on the host. Fonts are the firmware's built-in Montserrat;
a missing size falls back to the next smaller one and prints
`# font: ...` on serial.

Copying `main.py` replaces whatever `main.py` the Dial runs now
(e.g. the Broadcast Dial firmware).

```
cd "Bag3/Code/Stations/NFC Station"
python3 -m mpremote connect PORT resume fs cp main.py station.py station_ui.py \
  station_fonts.py text_entry.py tag_catalog.py game_tags.py dial_board.py \
  dial_input.py card_writer.py ws1850s.py json_link.py :/flash/
python3 -m mpremote connect PORT reset
```

Keyboard ring images (`IMAGE_RING = True` in `station_ui.py`): also copy
`kb_letters.bin kb_rings.json` to `:/flash/` (115 KB; the `#` ring stays live labels). They are
pre-rendered by `python3 tools/gen_ring.py` (rerun after changing the ring
items, fonts or geometry); `tools/kb_*.png` are previews. With
`IMAGE_RING = False` the ring is drawn from 30 live rotated labels.

Host tests: `python3 tools/test_station.py`.

Record hardware results in `docs/circular-ui-notes.md`.
