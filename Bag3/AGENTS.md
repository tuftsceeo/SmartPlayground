# Bag3/AGENTS.md — Wand module firmware

Factual description of Bag3 only. See the root [`AGENTS.md`](../AGENTS.md) for the hub/module/
station vocabulary and the standing rule to ask which Bag a piece of work targets. This file does
not compare Bag3 to Bag2 — the two Wand module trees are expected to diverge, not stay in sync; see
root `AGENTS.md`'s Wand module edit rule.

## Hardware — dated August 2026, sole owner of these facts, and currently in flux

New Wand module boards are **on order and have not arrived.** Hardware facts below will change
between board revisions — confirm with the developer before relying on them for anything beyond the
current session, and if what you're told contradicts this section, trust the developer and flag the
discrepancy (see root `AGENTS.md`'s governance note) rather than treating this file as authoritative.

| Aspect | State as of August 2026 | Where the code is |
|---|---|---|
| LED matrix 6×10, 60 pixels | Committed on this branch (`Bag3/Code/lib/leds.py`) | This tree |
| NFC reader WS1850S @ I2C 0x28 | Committed on this branch (`Bag3/Code/lib/ws1850s.py`, `power_led.py` — both Bag3-only files) | This tree |
| LED matrix 5×5, 25 pixels + real PN532 @ I2C 0x24 | Explored, not merged | `origin/claude/pn532-5x5` commit `8e567ca` |
| Card storage: 4-byte opcode @ page/block 5 (vs. NDEF text) | Explored, not merged, not decided either way | `origin/claude/pn532-5x5` commits `71e7c08`, `9ccd917` (`lib/opcodes.py`, `utilities/migrate_cards.py`) |

New hardware inherently needs software to test its capabilities — drivers and bring-up scripts come
first, ahead of game/feature work on that hardware. That is why `Bag3/Code/` currently holds only
Wand module firmware: it reflects where the new-hardware work has reached, not that Bag3 is a
Wand-module-only system going forward.

## MicroPython reality

Constraints that actually hold in shipped device code — don't invent stricter ones:

- No `typing`, `dataclasses`, `pathlib`, or `logging` imports.
- No `f"{x=}"` debug specifier and no nested same-quote strings inside an f-string.
- **F-strings themselves are fine and already used** in `lib/actions.py`, `lib/buzzer.py`,
  `Wand Module/main.py`, and several game modules — do not "fix" them into `%`-formatting.
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
  `programming_station`, `score_board`). Only `wand` has firmware in this tree.
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

## Reference material — unverified for this Bag's committed hardware

`Wand Module/readme.md` and `Wand Module/GAME_AUTHORING_GUIDE.md` are byte-identical copies of
Bag2's (md5 `fe70b536…` / `3397c092…`). They describe a 5×5 matrix and a PN532 at 0x24 — which
matches neither the 6×10/WS1850S code currently committed in this tree nor a confirmed Bag3 target
(see the hardware table above). **Treat their hardware-specific sections (pin map, NeoPixel layout,
I2C addresses, LED shape constants) as unverified for Bag3** until this Bag has its own copy or an
explicit correction. Their non-hardware content (game-authoring patterns, the `play()` signature,
general driver API shapes) is not affected by this caveat.

## Verification

- There is no Flasher manifest for Bag3 hardware; use MicroPico's manual-connect upload.
- `utilities/UnitTest/Test1.py`, `Test2.py`, `CompleteTest.py` are interactive hardware bring-up
  scripts — run them from the device REPL and read the printed pass/warn/fail transcript yourself;
  they are not an automated test suite.
