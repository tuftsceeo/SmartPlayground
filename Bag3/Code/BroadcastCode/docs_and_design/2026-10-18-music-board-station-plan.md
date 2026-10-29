---
status: historical
note: >-
  Old development note, kept as a record. Not current guidance: rules, paths and plans
  here may be out of date. Check AGENTS.md and the code for current behavior.
---
# Music Board Station: plan

Rebuild the February 2025 Music Control Board (`old_stuff/Music_Control_Board/`, see its README)
as a Bag3 ESP-NOW station that plays back melodies collected in the MockWand `melody` game.
Hardware is reused as-is; the board firmware is a full rewrite.

## Old system vs. Bag3

| Step | Feb 2025 | Bag3 |
|---|---|---|
| Collect a note | Splat press sends its number over ESP-NOW (RSSI > -85) | Wand taps a `note_*` NFC tag |
| Confirm the note | Plushie button within 3 s | Implicit on scan; `backspace` / `erase` tags edit |
| Store | Plushie list, max 8 | `MelodyGame.current_melody`, max 25 (`melody.py:43`) |
| Hand off to board | RSSI > -70 then button press | **Tap an NFC sticker on the board** |
| Address the board | Hardcoded board MAC in plushie | Board id written on the sticker |
| Play back | Board WAVs, column highlight | Same, rewritten |

The note sets already match: old 1..8 = `note_c, note_d, note_e, note_f, note_g, note_a, note_b,
note_c_high`, same colour order. The existing `notet*.wav` files can be reused.

## Hand-off design

**Sticker.** A passive NTAG on the board's face holding NDEF text `musicbox@<id>`, where `<id>` is
the board's `HOST_ID` (lowercase hex, `HOST_ID_MAX = 8`, e.g. last 4 hex of its MAC). This reuses
the existing `<prefix>[:<slug>]@<host_id>` convention and `split_prefixed()` in
`MockWand/lib/nfc_reader.py`. The board itself needs no NFC reader.

**Wand, on tapping the sticker while in `melody`:**

```
broadcast {"type": "song", "to": "<id>", "n": "cegCa", "seq": <int>}
```

- `n` is one character per note (`c d e f g a b C`), so 25 notes fit well under the 250-byte
  ESP-NOW frame; a list of `note_*` strings would not.
- `seq` increments per send so the board can drop retries it has already played.
- The wand retries up to 3 times until it gets an ack, then shows success (or a sad face).
- `current_melody` is kept, not cleared, so the student can resend or keep editing.

**Board:** ignores `song` whose `to` is not its id, otherwise replies by unicast to the sender:

```
{"type": "song_ack", "seq": <int>, "len": <notes accepted>}
```

Proximity comes from the NFC tap, not RSSI. Two boards in a room are told apart by id.

## Board firmware (rewrite)

Target: XIAO ESP32-C6, the existing pins (NeoPixel 21, I2S BCLK 20 / LRC 18 / DIN 19, buttons
1 / 2 / 0). New folder: `Bag3/Code/Experiments/Music Board Station/`.

```
boot.py            # minimal
main.py            # ESPNowManager().init() FIRST, then everything else
hubtype.txt        # music_board
lib/espnow_manager.py   # copy from BroadcastCode/MockWand/lib (flag divergence, do not reconcile)
music_board.py     # state machine: IDLE -> LOADED -> PLAYING
grid.py            # 8x8 column-major mapping, button LEDs 64-66
audio.py           # streamed WAV -> I2S, one preallocated buffer
notes/notet*.wav   # copied from old_stuff/Common/Software/Sound Files
```

Rules this follows (AGENTS.md):

- **Radio first.** `main.py` brings up ESP-NOW before importing `neopixel`, building the 67-pixel
  buffer, or allocating the I2S/WAV buffer. Diagnostics live in a separate lazily imported module.
- **Onboard antenna** (GPIO3 = 0, GPIO14 = 0) unless told otherwise.
- **Main loop** polls `enow.poll(0)` and buttons, with `time.sleep_ms(1)` every iteration.
- **Playback outside IRQs.** Buttons set flags; the main loop plays one note per step so ESP-NOW
  and the Stop/Play button stay responsive. Fixes the old in-IRQ blocking playback.

Behaviour:

| Input | Effect |
|---|---|
| `song` for this board | Store, draw, ack; auto-play once (option) |
| Play button | Play / stop toggle |
| Style button | normal / fast / slow (WAV suffix, as before) |
| Coder button | Replay last song, or clear (to decide) |
| `["stop"]` broadcast | Stop playback, clear |

**More than 8 notes:** the grid has 8 columns. During playback the view pages in 8-note windows;
at rest it shows the first 8 with the last column dimmed if more exist.

## Wand changes (MockWand only)

`Bag3/Code/BroadcastCode/MockWand/melody.py` and `lib/espnow_manager.py`. `Bag3/Code/Wand Module/`
is not touched unless asked.

1. Recognise `musicbox` as a prefixed card in `melody.py` (register the prefix with `NfcReader`).
2. Add `send_song(host_id, notes)` with seq + ack retry, matching splatecho's ACK pattern.
3. Show send state on the 5x5: arrow while sending, check on ack, sad face on timeout.
4. Allow `song_ack` through `poll()` (it currently returns unknown dict types as `"raw"`).

## Tag consistency

`musicbox` is a station sticker, not a game tag. Decide whether it belongs in `game_tags.py`
(e.g. `HIDDEN_TAGS`) and therefore also in `hubCode2/game_tags.py`, `commands.json`, and
`wand_icons.html`. If it is added in one place, add it in all four.

## Test plan

1. **Bench audio:** `audio.py` plays all 24 WAVs on the C6 after radio bring-up (checks memory
   order with I2S allocated).
2. **Scripted wand:** a devtest in `tools/devtests/` broadcasts `song` frames with good / wrong id /
   repeated seq, and checks acks.
3. **End to end:** melody on a MockWand, tap 5 notes, tap the sticker, board plays.
4. **Two boards:** two stickers with different ids; each wand's song lands only on the tapped
   board.

## Decisions (2026-10-18)

Implemented in `Bag3/Code/Experiments/Music Board Station/` (see its README) and
`MockWand/melody.py`; this section overrides earlier sections where they differ.

- **Standalone melody unchanged.** The wand only gains the `musicbox` sticker branch.
- **Auto-play once** on receipt; Play button plays / stops.
- **Wand keeps** its melody after a send. Success (check) needs `len > 0` in the ack.
- **Person+ button** (person with "+" icon): the next song received is appended (one-shot, 30 s
  timeout). Board cap 64 notes.
- **Voice button:** piano / guitar / violin = normal / `_fast` / `_slow` WAVs, as in the pilot.
- **Note lengths:** song tokens may carry `+` (half) or `-` (eighth), and `r` is a rest. The
  board supports them now; MockWand sends bare letters (quarters). Lengths exist only in Bag2's
  `Wand Module/melody.py`, which has scoping bugs (`DOUBLE_LENGTH` assigned without `global`,
  undefined `leds`) and was not changed.
- **Staff:** one column per eighth-beat, head + dim tail, scrolling under a playhead at column 3.
- **Ack:** `{"type": "song_ack", "seq", "len"}`; retries are re-acked with the earlier `len`.
- **`musicbox` is melody-only**; not added to the shared game-tag lists.
