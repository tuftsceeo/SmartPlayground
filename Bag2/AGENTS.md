# Bag2/AGENTS.md

Bag2 has been given to classrooms; it is fielded, not frozen. This file describes Bag2 only — see
the root [`AGENTS.md`](../AGENTS.md) for the hub/module/station vocabulary, the two meanings of
"hub", and the standing rule to ask which Bag a piece of work targets.

## The fielded-hardware gate

**A change reaching Bag2 hardware needs real hardware testing, which an agent cannot do.** Open a PR
against `May_2026`, never merge, and state plainly what still needs testing (which device, which
behavior).

## Components in this Bag

| Component | Code | Communicates |
|---|---|---|
| **Wand module** | `Code/Wand Module/` + `Code/lib/` | ESP-NOW (broadcast JSON via `espnow_manager.py`), NFC (tap-coding) |
| **Splat Companion module** | `Code/Splat Companion/` | Bridges ESP-NOW ↔ BLE to a stock third-party splat toy (`ble_splat.py`) |
| **narrator module** | `Code/StickS3 Narrator/` | ESP-NOW, **receive-only** — listens for `start_game`/`stop` and Freeze Dance's raw calls, speaks a WAV clip + shows an LCD label. M5Stack StickS3 (ESP32-S3), UIFlow2 MicroPython |
| **paper remote module** | `Code/M5Paper Remote/` | ESP-NOW (broadcasts commands directly to wands — no USB hub needed). M5Paper (ESP32-D0WDQ6), UIFlow2 MicroPython, e-ink display |
| **speaker station** | `Code/Speaker/` | ESP-NOW receive-only; plain ESP32 + SD card, headless |
| **dial station** | `Code/DialSpeaker/Dial_Music.py` | ESP-NOW receive-only; M5Stack Dial + AudioPlayer Unit, LVGL round-screen UI, self-described "Musical Chairs Controller" |
| **coding station** | `Code/Stations/Programming Station/` | ESP-NOW broadcast (4-reader NFC → color sequence) |
| **slide station** | `Code/Stations/Slide Score Station/` | ESP-NOW receive (game sequences + score submissions) |

**Not every component uses the shared `HUB_CONFIG` mechanism.** The Wand module, Splat Companion
module, coding station, and slide station read `hubtype.txt` and import `Code/lib/hubtype.py`
(`_CONFIGS` keys: `wand`, `splat_companion`, `programming_station`, `score_board`). The **paper
remote module and narrator module do not** — they run on M5Stack UIFlow2, have their own
`hubtype.txt` (`paper_remote` — not a recognized `HUB_CONFIG` key) or none at all, and neither
`main.py` imports `hubtype.py`. Speaker station and dial station have no `hubtype.txt` either.

## Wand module hardware — dated August 2026, sole owner of these facts

From `Code/lib/hubtype.py`, `"wand"` config: **25 LEDs (5×5 matrix)** on GPIO 20, **PN532 NFC @ I2C
0x24**, buzzer GPIO 19, vibration motor GPIO 21, button GPIO 0 (active low), accelerometer INT1 on
GPIO 1, I2C SDA 22 / SCL 23 @ 100 kHz, plus a battery gauge. BLE hardware present but
`uses_ble = False`. Other configured types in the same file: `splat_companion` (3 LEDs, I2C @
400 kHz), `programming_station` (18 LEDs), `score_board` (40 LEDs).

**Coding station hardware** (`Stations/Programming Station/README.md`): PCA9546 I2C multiplexer
(address 0x70) shares one I2C bus across 4 PN532 readers (fixed address 0x24 each), since only one
channel is active at a time; 18-LED NeoPixel strip on GPIO21; button GPIO0.

**Slide station hardware** (`Stations/Slide Score Station/README.md`): single 40-LED NeoPixel strip
on GPIO0, physically arranged as a serpentine 4×10 grid.

## Wand module firmware

- `lib/` (14 modules) copied to the device's `/lib`. `Wand Module/` files sit flat at the device
  root — **there is no `games/` subdirectory.**
- Games expose `play(nfc, leds, buz, accel, i2c, enow)` (`rainbow.py` alone takes an extra
  `batt=None`).
- `main.py::GAME_DISPATCH` holds 14 entries matching `game_tags.py::GAME_TAGS`
  (`colorquest, freezedance, jumpin, cooking, melody, shake, shakerainbow, rainbow, jump, sound,
  nfcsound, simpleicecream, multiicecream, gestures`) plus hidden `finddevice`
  (`HIDDEN_TAGS`, reachable only over ESP-NOW). `main.py` self-checks
  `set(GAME_DISPATCH.keys()) != (GAME_TAGS | HIDDEN_TAGS)` at boot and prints `[ERR]` on mismatch —
  this is not silent. `main.py` also carries an accurate inline "adding a game" comment block.
- Tap-coding grammar: `TRIGGER → ACTION [and|then ACTION]*`, stored as `list[list[str]]` (outer =
  sequential THEN-groups, inner = simultaneous AND-groups). Triggers: `buttondown`, `buttonup`,
  `whenshake`.

## Cross-component conventions (documented in `Code/lib/README.md` — cite, don't duplicate)

- **Bundled-copy convention.** Components outside `lib/` (paper remote module, narrator module) keep
  a **bundled copy** of `espnow_manager.py` / `game_tags.py`, synced by hand rather than imported
  across directories. A fix in `lib/` must be manually copied to each bundled copy.
- **`poll()` blocking semantics.** `ESPNowManager.poll(timeout_ms=0)` is non-blocking by default; a
  nonzero `timeout_ms` blocks inside a C call with **no Python-level yield point** until it returns.
  Polling loops should call `poll()` with no argument and pace themselves with `time.sleep_ms()`, as
  every `Wand Module/*.py` game and `M5Paper Remote/main.py` do. `color_quest.py`'s `poll(50)` is
  the one documented exception, inside a loop that also does per-iteration display work.

## Doc trust map (Bag2's own 17 markdown files)

| Path | Trust | Notes |
|---|---|---|
| `Code/Wand Module/README.md` | Trusted | 5×5 / PN532 @ 0x24 matches this Bag's hardware |
| `Code/Wand Module/GAME_AUTHORING_GUIDE.md` | Trusted | |
| `Code/lib/README.md` | Trusted | Non-obvious content — the bundled-copy convention and `poll()` semantics above come from here |
| `Code/M5Paper Remote/README.md` | Trusted | |
| `Code/StickS3 Narrator/README.md` | Trusted | References `assets/_generate_phrases.py`, noted in that file as "not present in this checkout" |
| `Code/Speaker/README.md` | Trusted | ESP-NOW command reference |
| `Code/Stations/Programming Station/README.md`, `Code/Stations/Slide Score Station/README.md` | Trusted | |
| `Documentation/README.md` | **Broken link** | Links `FREEZE_DANCE_README.md`; the file on disk is `freeze-dance-readme.md` |
| `Documentation/COLOR_QUEST_README.md`, `espnow_control.md`, `freeze-dance-readme.md` | Trusted | |
| `Documentation/color_quest_issues.md` | Issues log, not a spec | |
| `Utilities/README.md`, `Unit Tests/README.md` | Not verified this pass | |
| `Code/README.md` | Trusted | |

## Other directories (not fully explored this pass)

- `Code/legacy/` — `gesture.py`, `gesture_engine.py`. Purpose and status not confirmed.
- `Battery Tests/` — CSV drain-test runs plus an HTML comparison viewer
  (e.g. `Drain test with LED/Brightness at (10,10,10)/*.csv`), not referenced by any other doc.
- `Design Files/CAD Files/` — `Splat Companion/` (V2 STLs) and `Slide Loom/` (`SLIDE_LOOM.pdf`,
  `SLIDE_LOOM_mm.dxf`) — CAD for the slide station's mounting.
- `Utilities/`, `Unit Tests/` — one line each in the trust map above; contents not read this pass.
- `Code/encrypted_key.txt`, `Utilities/encrypted_key.txt` — present; purpose undocumented. Do not
  open or describe their contents.
