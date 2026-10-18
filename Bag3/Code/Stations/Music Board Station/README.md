# Music Board Station

Bag3 firmware for the February 2025 Music Control Board hardware (see
`old_stuff/Music_Control_Board/README.md`). A MockWand in the `melody` game taps the NFC sticker
on the board; the board shows the melody on its 8x8 staff and plays it through its speaker.

Melody on the wand alone is unchanged. The board adds louder playback, three voices, a shared
display, and combining songs from several students.

## Files

| Path | Contents |
|---|---|
| `main.py` | Brings up ESP-NOW first, then imports and runs `music_board` |
| `music_board.py` | Song protocol, parsing, playback state, buttons |
| `staff.py` | 8x8 staff timeline rendering and button LEDs |
| `audio.py` | Streamed WAV to I2S, one chunk per main-loop pass |
| `lib/espnow_manager.py` | Copy of `BroadcastCode/MockWand/lib/espnow_manager.py` with `EXTERNAL_ANTENNA = False` |
| `notes/notet{1-8}[_fast\|_slow].wav` | Note sounds, 8 kHz 16-bit mono, from the pilot |
| `hubtype.txt` | `music_board` |

`lib/espnow_manager.py` is a per-tree copy. It differs from the IconDisplay copy; it matches the
MockWand copy except for the antenna setting.

## Hardware (unchanged from the pilot)

Seeed XIAO ESP32-C6, onboard antenna.

| Function | GPIO |
|---|---|
| NeoPixel chain, 67 LEDs (0-63 staff, 64 voice LED, 65 play LED, 66 person+ LED) | 21 |
| I2S BCLK / LRC / DIN | 20 / 18 / 19 |
| Person+ button | 1 |
| Play button | 2 |
| Voice button | 0 |

Staff index = `col * 8 + (7 - row)`; row 0 = low C at the bottom.

## Setup

1. Copy the folder contents to the board root (`lib/` and `notes/` as folders).
2. Boot once and read the serial line `Music Board ready: sticker text musicbox@<id>`. `<id>` is
   the last two bytes of `machine.unique_id()` in hex, the same scheme as `code_server.HOST_ID`.
3. Write an NTAG sticker with NDEF text `musicbox@<id>` and fix it to the board face.

## Protocol

Wand broadcast, sent when the sticker is tapped:

```
{"type": "song", "to": "<id>", "n": "<song>", "seq": <int>}
```

Board unicast reply to the sender:

```
{"type": "song_ack", "seq": <seq>, "len": <notes taken>}
```

- A song addressed to another id gets no reply.
- A repeated `seq` from the same sender is re-acked with the earlier `len` and not replayed.
- `len: 0` means the song was rejected (malformed) or the board was full.

Song string: one token per note: `c d e f g a b C` or `r` (rest), optionally followed by `+`
(half note) or `-` (eighth note). No mark = quarter. Example: `ce-e-g+r`. The current MockWand
melody sends bare note letters only; length marks are for wands that add length tags later.

## Behaviour

| Input | Effect |
|---|---|
| Song received | Replaces the board song (or appends, after person+) and plays it once |
| Play | Play from the start / stop |
| Voice | piano (green) -> guitar (red) -> violin (blue); takes effect on the next note |
| Person+ | LED blue: the next song received is appended. One-shot; cancels after 30 s or a second press |
| `stop` broadcast | Stop and clear |

The board holds at most 64 notes.

Play LED: off = empty, green = song loaded, yellow = playing. Person+ LED: off = empty, green =
song loaded, blue = waiting to add.

### Staff

One column is one eighth-beat. An eighth note takes 1 column, a quarter 2, and a half 4: the head
in full colour, the rest a dim tail. Rests are empty columns. During playback the sounding column
fills from the bottom to its note, holds at column 3, and the song scrolls left under it. At rest
the first 8 columns are shown, with a dim pixel top-right when more follows.

### Timing

Each note's WAV starts on its beat and is cut at the next onset. Quarter-note length per voice:
piano 600 ms, guitar 320 ms, violin 1000 ms (`VOICES` in `music_board.py`).

## Tests

- `python3 -m py_compile` on each file.
- `BroadcastCode/tools/devtests/music_board_song.py` runs the song handling under stubs:
  addressing, ack, retry de-dup, person+ append, the 64-note cap, malformed input, timing per
  voice, and that `MockWand/melody.py`'s `NOTE_CHAR` matches `NOTE_CHARS`.
- Not yet run on hardware.
