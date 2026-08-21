# Bag3/AGENTS.md — wand firmware

Read [../AGENTS.md](../AGENTS.md) first for the Bag model, the developer-population table, and the
Bag2 verification gate. This file covers wand firmware specifics and applies to **both**
`Bag2/Code/Wand Module/` + `Bag2/Code/lib/` and `Bag3/Code/Wand Module/` + `Bag3/Code/lib/` — the
two trees are near-duplicates of the same firmware, diverging mainly on hardware-specific code.

## Which wand hardware am I on?

| Aspect | Current target | Where |
|---|---|---|
| LED matrix | **5×5, 25 pixels** — the next hardware round, 10+ prototypes in production | `Bag2/Code/lib/leds.py`; ported to Bag3 in `origin/claude/pn532-5x5` commit `8e567ca` |
| NFC reader | **Real PN532 @ I2C 0x24** | same |
| Card storage | NDEF text today; a 4-byte-opcode scheme is **still being explored, not decided** | `origin/claude/pn532-5x5` commits `71e7c08`, `9ccd917` |
| 6×10 / 60px matrix + WS1850S NFC @ 0x28 | **One-off exploration on `May_2026`; not going forward** | `Bag3/Code/lib/leds.py`, `ws1850s.py` on this branch |

**Most wand hardware in circulation is Bag2** (`Bag2/Code/Wand Module/`, `Bag2/Code/lib/`, 5×5
matrix, PN532). Bag3 work is ahead of a larger production batch and, as of this writing, the
committed `Bag3/Code/` tree still carries the abandoned 6×10 exploration rather than the 5×5 target
— don't take `Bag3/Code/lib/leds.py`'s `COLS=6, ROWS=10` as the design to extend.

## The Bag2 verification gate (restated)

**Bag2 wands are in classroom use.** You cannot verify a change to `Bag2/Code/` on real hardware.
Open a PR against `May_2026`, never merge, and say plainly in your summary what still needs
hardware testing. This is more likely to apply to your work than to most other edits in this repo,
since most wand hardware is Bag2.

## Governance protocol (restated)

If the user's statements about hardware contradict this file, **trust the user**, don't correct them
from the docs — but flag the discrepancy and ask whether it's a minor one-off (make the change,
leave docs alone) or a major round (add a dated entry to the tables here, in `Bag3/../AGENTS.md`,
and in the root `README.md`).

## MicroPython reality

Constraints that actually hold in shipped device code — don't invent stricter ones:

- No `typing`, `dataclasses`, `pathlib`, or `logging` imports.
- No `f"{x=}"` debug specifier and no nested same-quote strings inside an f-string.
- **F-strings themselves are fine and already used** in `lib/actions.py`, `lib/buzzer.py`,
  `Wand Module/main.py`, and several game modules — do not "fix" them into `%`-formatting.
- RAM is tight; avoid large intermediate allocations in per-frame code (LED animation loops,
  ESP-NOW `poll()` handlers).
- `machine`, `espnow`, `neopixel`, and `ubluetooth` do not exist off-device — nothing that imports
  them can be run or imported (only compiled) from a desktop Python environment.

## Layout

- `lib/` — shared modules copied to the device's `/lib`: device typing (`hubtype.py`, reads
  `/hubtype.txt`), ESP-NOW (`espnow_manager.py`), BLE-to-Splat driver (`ble_splat.py` — unused by
  the wand today), LED matrix (`leds.py`), tap-coding action runner (`actions.py`), buzzer, battery,
  ambient-brightness scaling, NFC card reading, and hardware drivers (NFC reader, accelerometer,
  fuel gauge, light sensor).
- `Wand Module/` — firmware root. `boot.py`, `main.py`, and **game modules as flat sibling files**
  — there is no `games/` subdirectory. `hubtype.txt` holds one word (`wand`) read at boot by
  `lib/hubtype.py`, which picks one of four device configs (`wand`, `splat_companion`,
  `programming_station`, `score_board`). Only `wand` has firmware in this tree — the other three
  device types are implemented in `Bag2/Code/Stations/` and `Bag2/Code/Splat Companion/`.
- `utilities/` — host/bench tools run interactively from a REPL, not deployed to the wand: NFC card
  reading/writing, hardware bring-up tests (`UnitTest/`).

## The tap-coding rule engine

Children build a program by tapping physical NFC cards in sequence. A rule is stored as
`TRIGGER → ACTION [and|then ACTION]*`, represented as `list[list[str]]` — the outer list is
sequential THEN-groups, the inner list is a simultaneous AND-group — and executed by
`ActionRunner` (`lib/actions.py`). The three trigger cards are `buttondown`, `buttonup`, and
`whenshake`.

The tap-coding *grammar* is settled. What's still open is the **card storage format** — NDEF text
today, with a 4-byte opcode scheme under exploration (see the hardware table above).

## Adding a game

The verified procedure, checked against all 16 shipped game modules:

1. Create `<name>.py` in `Wand Module/` exposing `def play(nfc, leds, buz, accel, i2c, enow):`.
   (`rainbow.py` is the sole exception, taking an extra `batt=None`.)
2. Add the tag name to `GAME_TAGS` in `lib/game_tags.py`.
3. Import the module and add it to `GAME_DISPATCH` in `main.py`.
4. Follow the cross-tree vocabulary obligations in the root `AGENTS.md` — game tags are also
   consumed by `Live_Page/WebApp2/hubCode2/game_tags.py`, `js/utils/commands.json`, and
   `wand_icons.html`.

`main.py` self-checks `set(GAME_DISPATCH) == GAME_TAGS | HIDDEN_TAGS` at boot and prints an
`[ERR]` line on mismatch — a missing or extra dispatch entry is a boot-time-visible bug, not silent.
`HIDDEN_TAGS` (currently just `finddevice`) are games reachable only over ESP-NOW, never by tapping
an NFC tag.

## Reference material (don't duplicate here)

Peripheral/driver APIs, the pin map, LED colors and shapes, and buzzer note names live in
`Wand Module/GAME_AUTHORING_GUIDE.md` (trusted) and `Wand Module/readme.md` ("v6", partially
stale). In `readme.md`, the sections describing a 5×5 matrix and a PN532 at 0x24 are **correct for
the target hardware**, even though they read as stale next to the 6×10 code currently committed on
this branch. Its genuinely stale sections are: the brightness table, the games list (only 6 of 16
games are documented), and the "Adding a New Game" walkthrough (describes an `if cmd == …` branch
in `main.py`, which now uses `GAME_DISPATCH`).

## Verification

- Flash via `Live_Page/Flasher` — its `wand.yml` manifest sources `Bag2/Code/`, which is correct for
  Bag2 hardware. There is no Flasher manifest for Bag3 hardware yet; use MicroPico's manual-connect
  upload for Bag3 devices.
- `utilities/UnitTest/Test1.py`, `Test2.py`, `CompleteTest.py` are interactive hardware bring-up
  scripts — run them from the device REPL and read the printed pass/warn/fail transcript yourself;
  they are not an automated test suite.
