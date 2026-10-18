# Music Control Board

Earliest-prototype SmartPlayground station, used in the February 2025 pilot. A student collects
notes on a plushie by pressing splats, carries the plushie to this board, sends the sequence, and
the board displays and plays it back.

This predates the Bag1 `games/` system and the `{'topic', 'value'}` protocol. It uses the CEEO
`networking.py` ESP-NOW library and plain string / list messages.

`Software/music_controlboard.py` is unchanged since commit `9ac355b` ("Initial upload of Jan 2025
files"). The companion plushie and splat code exists only in that commit:

```
git show "9ac355b:Plushie Module/Software/overall_module_main.py"
git show "9ac355b:Plushie Module/Software/imports/module.py"
git show "9ac355b:Splats/Software/overall_splat_main.py"
git show "9ac355b:Splats/Software/imports/splat.py"
git show "9ac355b:Music Control Board/Software/imports/networking.py"
```

## Files

| Path | Contents |
|---|---|
| `Software/music_controlboard.py` | Board program |
| `Software/imports/music_board_testing.py` | Bench test: rainbow cycle over all 67 LEDs; WAV calls commented out |
| `../Common/Software/Sound Files/notet{1-8}[_fast\|_slow].wav` | 24 note files, 8 kHz, 16-bit, mono |
| `Hardware/placeholder.md` | Empty |

`networking.py` is not in this folder; it is in commit `9ac355b` and in `../Common/Software/`
(that copy differs).

## Operation

1. **Splat press.** A splat with a hardcoded number (`Splat('3')`) plays its own note WAV and sends
   its number as a string to every nearby module whose name is an animal (`Lion`, `Tiger`, ...) and
   whose RSSI is above -85 dBm.
2. **Plushie accepts the note.** The plushie OLED shows `Add Note?` and the LED matrix shows the
   digit in the note's colour. A press of the select button within 3 s appends the note, up to 8.
   The sequence is drawn in the matrix's top row.
3. **Plushie sends to the board.** Every 3 s the plushie pings the hardcoded board MAC
   `8C:BF:EA:CB:B4:D0`. When RSSI is above -70 dBm the OLED shows `Send?`; a button press sends
   the sequence as a list, e.g. `[3, 1, 5, 5]`.
4. **Board displays the sequence.** Any list of 8 or fewer notes from any sender is accepted. Each
   note is one grid column; row = note (1 at the bottom, 8 at the top). State becomes `PAUSED`.
5. **Play button.** Plays each note's WAV back to back. The current column fills from the bottom
   to the note row in the note's colour. The grid returns to the plain sequence afterwards.
6. **Style button.** Cycles `normal` -> `fast` -> `slow`, which selects the WAV file suffix
   (`''`, `_fast`, `_slow`). Note spacing is the WAV length; the `TEMPOS` delay values are unused.
7. **Coder button.** Broadcasts `'Coder'`. A plushie that accepts within 5 s replies `'Coder'`;
   the board stores it in `current_coder` / `coders_list`, which nothing reads. Plushies boot with
   status `'Coder'`, so this step was not needed for play.

Playback runs to completion inside the Play button IRQ handler, so presses during playback are
ignored and each press plays the sequence once. `main()` only sleeps; all work happens in the
button IRQs and the ESP-NOW `irq` callback.

### Messages

| Direction | Payload | Meaning |
|---|---|---|
| Splat -> plushie | `'1'`..`'8'` (str) | Note number |
| Board -> broadcast | `'Coder'` | Coder invitation |
| Plushie -> board | `'Coder'` | Coder accepted |
| Plushie -> board | `[n, ...]` (list, len <= 8) | Collected sequence |

The plushie ignores board messages unless the sender is its stored board MAC, and only offers
splat notes when `peer_name(board_mac) == 'Music'`.

## Notes and colours

| # | Note | WAV | Board RGB |
|---|---|---|---|
| 1 | C4 | `notet1.wav` | (100, 0, 0) red |
| 2 | D4 | `notet2.wav` | (255, 127, 0) orange |
| 3 | E4 | `notet3.wav` | (255, 255, 0) yellow |
| 4 | F4 | `notet4.wav` | (0, 255, 0) green |
| 5 | G4 | `notet5.wav` | (0, 255, 255) cyan |
| 6 | A4 | `notet6.wav` | (0, 0, 255) blue |
| 7 | B4 | `notet7.wav` | (50, 0, 255) purple |
| 8 | C5 | `notet8.wav` | (150, 70, 200) pink |

The plushie and splat use the same colour order.

## Hardware

### Board: Seeed XIAO ESP32-C6

| Function | GPIO (XIAO pin) | Notes |
|---|---|---|
| NeoPixel chain, 67 LEDs | 21 (D3) | 0-63: 8x8 grid, column-major, `index = col*8 + (7-row)`; 64-66: button LEDs |
| I2S amp BCLK | 20 (D9) | Mono TX; rate and bit depth read from each WAV header |
| I2S amp LRC / WS | 18 (D10) | |
| I2S amp DIN | 19 (D8) | |
| Coder button | 1 (D1) | Pull-up, IRQ on falling edge; LED = pixel 66 |
| Play button | 2 (D2) | LED = pixel 65 |
| Style button | 0 (D0) | LED = pixel 64: green normal, red fast, blue slow |

The amplifier part is not named in the code. WAVs are read from on-board flash.

Button LED colours by state: `READY` coder green; `WAITING` coder green; `PAUSED` coder and play
green; `PLAYING` coder and play yellow.

### Plushie (as configured for this board)

- **Controller:** XIAO ESP32 (C3 pinout); `Module('Lion', 'Music')`.
- **Select button:** GPIO 9. **Vibration motor:** GPIO 2.
- **I2C (SoftI2C SCL 7, SDA 6):** SSD1306 128x64 OLED and Grove RGB LED Matrix 8x8 (0x65).
- **ADC:** battery on 4; pot on 3 and light on 5 are unused here.

### Splat (DIY, pre-BLE)

- **Switches:** GPIO 0, 1, 2, 21; any press counts.
- **NeoPixel strip:** 14 LEDs on GPIO 22, lit in the splat's note colour.
- **PWM:** GPIO 23, 1 kHz.
- **I2S amp:** same pins as the board (20/18/19); plays at most 40 KB (about 2.5 s) of its WAV.

## Code comments that do not match behaviour

- Button LED indices: comments say Coder 64 and Style 66; code uses 66 and 64.
- WAVs are described as read from an SD card; they are on flash.
- Colours are described as GRB; they render as RGB.
- The `INVITING` state and invitation timer are commented out.
- `TEMPOS` delays are documented as note spacing; they are unused.
- `_play_note` claims I2S error recovery; there is none. `handle_error_state` reads
  `self.error_state`, which exists only if timer setup fails.
- `self.game_state == 'PAUSED'` (lines 430, 577) is a comparison, not an assignment; line 578
  references the global `board`.
- `music_board_testing.py` labels LRC D8 and DIN D10; the code wires LRC to D10 and DIN to D8.
- `play_sound` catches `KeyboardInterrupt` and continues; it never calls `i2s.deinit()`.
