# NFC Station — standalone NFC card reader/writer (M5 Dial 2)

## Context
The Broadcast Dial (`Bag3/Code/BroadcastCode/BroadcastDial/BDialFirmware/`) writes NDEF-text game cards and also serves code over SoftAP. The goal here is a separate device that only reads and writes cards, with type readable from a short distance and a dial-based way to enter free text.

Decisions so far:
- **Link:** USB serial only. There is no radio, so the AP memory-order constraint doesn't apply.
- **Hardware:** M5 Dial 2. It prefers the external Grove RFID2 reader on Port A and falls back to the built-in reader.
- **Location:** `Bag3/Code/Stations/NFC Station/`, which sits next to `Icon Display Station`.
- **Screens:** Read, then a list of known tags grouped by game, then free text.
- **Text entry:** a grouped two-step picker, a word/phrase bank, and touch keys on the rim.
- **Font rule:** the smallest text on screen is 28 px, double the Dial's `montserrat_14`.

## Answer: tag case sensitivity
- **NDEF-text readers are case-insensitive.** MockWand, SplatCompanion and IconDisplay all use `lib/nfc_reader.py`, which calls `.strip().lower()` on the decoded text (MockWand `lib/nfc_reader.py:421,428`). `code_puller.py` compares names with `.lower()` as well.
- **The Bag3 Wand Module doesn't read text at all.** `Bag3/Code/lib/nfc_reader.py` + `opcodes.py` read a 4-byte opcode at page 5. The Dial's `card_writer.py` writes NDEF text and states it does not use opcodes. Cards written by the Dial, or by this station, are therefore **not read by the Bag3 Wand Module**. That is a gap that already exists, not one this device introduces.
- **Consequence:** the text-entry alphabet is lowercase `a–z 0–9 _ space`. Mixed case would be folded on read anyway, so offering it would only mislead.

## Files (new tree; copies, not imports)
Copy unchanged from `BDialFirmware/`:
- `dial_board.py` (provides `make_reader()`)
- `ws1850s.py`
- `card_writer.py` (provides `write_text`, `existing_text`, `build_ndef_text*`, `NfcWriter.detect_tag`)
- `dial_input.py`
- `boot.py`
- `reset_log.py`
- `json_link.py`, for the USB serial protocol

Copy `game_tags.py` from `Bag3/Code/BroadcastCode/MockWand/lib/` (text names).

New files:
- **`station.py`:** the mode machine and main loop. Each loop iteration calls `time.sleep_ms(1)`. It is adapted from the non-serving parts of `bdial_server.py`, such as `_init_nfc`, `_set_mode` and `_card_text`.
- **`station_ui.py`:** a rewrite of `dial_ui.py` that keeps the palette tokens, the `_label`/`_chip`/`_button` helpers, the beeps, and the page-swap via `screen_load()`.
- **`tag_catalog.py`:** builds `{game: [tags]}` from `game_tags.py` plus `/flash/tags.json`. ChatBroadcast can push that file over serial.
- **`text_entry.py`:** the `TextEntry` class.
- **`tools/font_probe.py`:** the Phase 0 check.
- **`README.md`**, and a line in AGENTS.md listing the new copies of the shared libraries.

## Circular UI design exploration (replaces the rectangular roller)
The rectangular `M5Roller` is not used. In a 240 px circle it leaves the corners and rim empty, and at 28 px it shows only about 3 rows. Instead, choose from patterns made for round screens with a rotary input:
- **Rim ring selector:** this follows the Samsung Gear S/Galaxy Watch bezel UI and Nest thermostat rings.
  - **Layout:** 6–10 items sit as labels or glyphs around the rim, placed by `x = cx + r·cos θ`.
  - **Selection:** the encoder moves a highlight arc (`lv.arc`) from item to item.
  - **Centre:** the middle shows the selected item large, at 40 px.
  - **Use:** Home, the game list, and the letter groups in the keyboard.
- **Rotating carousel:** this follows the Wear OS curved list and the Apple Watch crown list.
  - **Layout:** one item sits large in the centre, with its neighbours drawn smaller and faded at 10 and 2 o'clock.
  - **Motion:** turning the encoder slides the items along the arc.
  - **Use:** long lists, such as the tags within one game.
- **Ring keyboard:** this follows the Galaxy Watch bezel keyboard and rotary-phone layouts.
  - **Layout:** characters sit around the rim, and the encoder sweeps a cursor across them.
  - **Selection:** a click adds the character, and the composed text sits in the centre.
  - **Fit:** the full alphabet doesn't fit at 28 px, because the rim circumference of about 600 px holds only about 18 glyphs. The ring therefore shows one letter group, and an outer step picks the group. This replaces the two-step roller.
- **Progress / position:** a thin arc along the rim shows where the user is in a list, replacing the right-rim track.
- **Deliverable for Phase 0b:** a short design note in `docs/` with sketches or screenshots of 2–3 layouts on the real 240×240 screen. It records:
  - legibility at about 1 m
  - the number of encoder detents per selection
  - frame rate and heap usage of each layout in LVGL

  One pattern is picked per screen type before Phases 1–3 build the screens.

## Round-screen UI rules
- **Type sizes:** 28 px minimum, 40 px for the selected item and titles, 48 px for glyphs. Use a single text line per element.
- **Safe area:** keep content inside the inscribed square of about 170×170, centred. The rim is reserved for the position track and the touch keys.
- **Density:** one task per screen. The selected item sits large in the centre, and its neighbours or choices sit on the rim.
- **Text fitting:** about 9 characters fit per row at 28 px. Long labels scroll in a marquee (`LONG_MODE_SCROLL_CIRCULAR`) instead of being truncated mid-word.
- **Feedback:** every result pairs colour with a glyph and a beep, so colour never carries meaning alone. Use high-contrast ink on the page background.
- **Input mapping:** this matches the Dial everywhere.
  - Encoder: move.
  - Click: select.
  - Hold: back.
  - Touch the rim at 9 o'clock: delete.
  - Touch the rim at 3 o'clock: done.

## Screens and flow
1. **Home roller:** `Read` / `Tags` / `Text`.
2. **Read:** waits for a card, then shows its text at 40 px plus the card type. Click writes a copy of that text to another card.
3. **Tags:**
   1. Pick a game.
   2. Pick a tag from that game.
   3. Hold the card on the reader to write it. The write uses the existing "already written" check and verify step.
4. **Text:**
   1. Enter text with `TextEntry`.
   2. Confirm.
   3. Write the card. A byte counter shows how much of the NTAG213 limit (about 137 bytes) is used.

## TextEntry design
- **Top line:** the composed text in 28 px, with a cursor. It scrolls left once it runs long.
- **Two-step picker:** the layout is chosen in Phase 0b, and the default is a ring keyboard.
  - The encoder picks a group from a ring on the rim: `abcde`, `fghij`, `klmno`, `pqrst`, `uvwxy`, `z_ 0-4`, `5-9`, `words`.
  - Click opens that group's characters on the ring, and the encoder then picks a single character.
  - Click commits the character and returns to the group ring.
- **`words` group:** a phrase bank of tag names from `tag_catalog` and `/flash/words.json`. Choosing an item appends the whole word.
- **Rim keys:** touch delete (left) and done (right). Hold the encoder to cancel, with a confirmation if the text isn't empty.
- **Outputs:** emits `done(text)` or `cancel`. It has no NFC knowledge, so it can be tested on its own.

## Phases
0b. **Circular UI exploration:** build `tools/ui_sketches.py`, which renders the ring selector, the carousel and the ring keyboard on the device. Then write the design note and choose a pattern per screen type.
0. **Probe:** `font_probe.py` tries `lv.font_montserrat_28/40/48`. If they're missing, fall back to `lv.binfont_create("/flash/fonts/…")` loading a converted `.bin` font. The probe also logs heap with all pages built.
1. **Skeleton:** Home and Read working on hardware.
2. **Tags:** the game and tag lists, plus writing.
3. **Text:** TextEntry and writing.
4. **Serial and docs:** a `tags.json`/`words.json` push command, the README, and the AGENTS.md note.

## Verification
- **Static:** run `python -m py_compile` on every new `.py`. This is the only check possible off-device.
- **Device:** deploy with an adapted `deploy_dial.py` and run `font_probe.py`. Then:
  - Read a card that the Dial wrote.
  - Write a tag, then confirm a MockWand or IconDisplay reads it.
  - Enter free text, write it, read it back.
  - Check legibility at about 1 m.
- **Fault cases:** test with no external reader (built-in fallback), a full card (byte limit), and a card removed mid-write (verify fails loudly).

## Implementation status (2026-10-02, no hardware run yet)

Done, host-tested only (`tools/test_station.py`, 26 tests):
- Phases 1-4 in code: `station.py`, `station_ui.py`, `text_entry.py`,
  `tag_catalog.py`, `main.py`, serial commands, `tools/deploy_station.py`.

Changes from the plan above:
- **Text limit is 54 bytes, not ~137.** `card_writer.existing_text()` and
  the wands' `nfc_reader.py` read NTAG pages 4-19 (64 bytes); longer text
  would fail verify and never read on a wand.
- **Rim touch keys:** every keyboard rim item is tappable (select + act),
  and delete/done are rim items, instead of fixed zones at 9 and 3 o'clock.
  Encoder-only use still works.
- **Home** uses the ring selector; game and tag lists use the carousel;
  keyboard uses the ring keyboard. Phase 0b on hardware may change these.
- **getcode tags excluded** from the catalog: they need a Dial/Box host id.
- `reset_log.py` not copied (unused).

Open, needs hardware:
- Fonts at 28/40/48 px present (`font_probe.py`), and whether LVGL symbol
  glyphs exist in any `.bin` replacement.
- Ring label positions vs. centre text overlap at 28 px; legibility at 1 m.
- LVGL calls in `station_ui.py` (arc rotation, `set_ext_click_area`,
  `LONG_MODE.SCROLL_CIRCULAR` names) against this UIFlow2 build.
- Read/write reliability with external and built-in readers.

## Revision: rotation-aligned UI (2026-10-02)

Reference images from the user: the segmented alphabet ring keyboard, the
M5 Dial icon ring menu, the circular slider, and a full-height watch-face
roller. Direction taken: every selector is rotation-aligned (choices on
the rim, highlight moves with the knob, selection enlarged in the centre).
The CHI 2023 paper (doi 10.1145/3544548.3580770) could not be read from
this environment (dl.acm.org blocked by the network policy).

- **Keyboard**: the two-step group picker is replaced by a single ring
  with the whole alphabet (`a`-`z`, space, `#`, delete, done; 30 items, one
  detent each) in tinted sections of three. `#` swaps to digits, `-`,
  `.`, and the word bank.
- **Fit at 28 px** (Montserrat Medium widths measured from the Google
  Fonts TTF): uniform 20.3 px pitch at r=97 overlaps at `l m n` (needs
  24.4 px). Slots are sized per glyph width (`station_ui.slot_angles`);
  `tools/test_station.py` checks both rings fit with the measured widths.
  The centre trims typed text by measured width.
- **Lists**: the vertical carousel is replaced by a dot ring; past 24
  items, a position arc.
- **Home**: icon ring of three coloured circles.
- **Status**: full rim arc coloured by result; partial arc while writing.
- `tools/ui_sketches.py` now drives the real `StationUI` pages.

Still needs hardware: whether LVGL label widths match the TTF
measurement, `update_layout()`/`get_width()` cost per keyboard repaint
(30 labels), arc z-order under labels, and touch accuracy on 20 px rim
targets.

## Revision: simulator findings (2026-10-02)

`docs/ui_simulator.html` renders every StationUI page on a 240 px canvas
with the firmware's geometry, colours and Montserrat sizes, and runs the
station flow interactively (LVGL symbols redrawn as vector icons).

- **Upright rim letters overlap** at 3 and 9 o'clock: neighbours stack
  vertically there, so line height, not glyph width, sets the spacing,
  and 30 upright 28 px labels do not fit. Rim labels are now rotated
  tangent to the ring (`station_ui.rim_rotation`, LVGL
  `transform_rotation`) with every letter's bottom toward the centre, so
  the ring reads continuously (lower half upside down, as on a dial).
  Unverified on hardware: label rotation draws through an LVGL layer.
- **Status hints clipped** by the circle ("Hold: Back", "Hold card
  still"); removed or shortened. Hold-to-back is the same on every screen.
- **Crownboard comparison** (Gupta et al., CHI 2023, out-of-vocabulary
  multi-tap): the simulator has a "zone + multi-tap" keyboard variant with
  live detent/click counts. Turning replaces Crownboard's 1,000 ms
  auto-scan and double-press. Not in firmware.
- **Write-failed screen**: title "Oops" (106 px at 40 px) with body
  "Hold Still" (127 px at 28 px); red X, red ring and fail beep carry
  the meaning. "Try Again" needed 192 px in a 180 px
  title box and scrolled.

## Revision: minimal first hardware test (2026-10-05)

Bundled `.bin` fonts, `tools/gen_fonts.sh`, `tools/deploy_station.py` and
`boot.py` removed. Device code is 12 `.py` files copied with one
`mpremote ... resume fs cp ... :/flash/`. Fonts are built-in only; a missing
28/40/48 px size falls back to the next smaller built-in and prints
`# font: ...`. Earlier plan text about `.bin` fonts and the deploy tool is
superseded.
