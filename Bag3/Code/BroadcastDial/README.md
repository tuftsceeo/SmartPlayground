# Broadcast Dial firmware (M5 Dial 2 / StampS3A, UIFlow2 MicroPython)

Sibling of `Bag3/Code/BroadcastBox/BBoxFirmware/`. Same product — write NFC
cards for a game, then serve that game's code to wands over SoftAP + TCP,
talking to ChatBroadcast over USB serial — on better hardware: a 240×240
round touch LCD, rotary encoder, button, and a built-in NFC reader.

The Dial keeps the Box's mode machine, wire contract, card-safety rules and
serial protocol byte-for-byte. Only the board, the input model and the
screen layer differ. ChatBroadcast accepts both devices from one app.

**Phase 0 (hardware gate) is still open.** `dial_board.py` leaves I2C pins
as `None` until `probe_dial.py` fills them. Software pass is P1/P4/P5 of
`.cursor/plans/dial.plan.md`.

## Filesystem

Write all device files to **`/flash`**, not `/`.

## Hardware

| Item | Value | Notes |
|---|---|---|
| Board | M5 Dial 2 (StampS3A) | UIFlow2 MicroPython; assume Dial family bring-up via `M5.begin()` + `m5ui.init()` (H1) |
| Display | LVGL / `m5ui`, 240×240 round | Screens built once, swapped with `screen_load()` |
| NFC | Built-in reader, expected WS1850S @ I2C `0x28` | Pins TBD (H2/H3). `make_reader()` raises until pins are set |
| Encoder | `hardware.Rotary` | CW/CCW → `NEXT`/`PREV`; magnitude honoured, capped |
| Button | `M5.BtnA` (encoder press) | Short click → `ACT`; hold `SERVE_EXIT_MS` (1000 ms) → `EXIT` |
| Touch | LVGL callbacks | Enqueue intents only; server drains from its own loop |
| USB | native CDC | Port drops on every reset; `mpremote` resets the board |

Style reference (not a logic peer): `Bag2/Code/DialSpeaker/Dial_Music.py`.

## Modes

Same invariant as the Box: at most one of {WiFi AP, NFC RF field} is
energized at any instant.

| Mode | AP | Reader | Entered when |
|---|---|---|---|
| `IDLE` | down | off | No game on flash |
| `WRITE` | down | on only while scanning | Game on flash — boot state |
| `SERVE` | **up** (`SP-FILEPUSH`) | off, and no I2C at all | Teacher selects `DONE` + `ACT` |

`_set_mode()` in `bdial_server.py` is the only place modes change.

**The Dial does not serve code until a teacher selects `DONE` + ACT.** The
`WRITE` screen header says `pickup off` for this reason.

## WRITE mode

Two-level menu (groups → tags), same shape as the Box including `W_GROUP`.

| State | Screen | ACT | NEXT/PREV | BACK | EXIT |
|---|---|---|---|---|---|
| `menu` | group list, focused entry centred | open group (or `SERVE` on `DONE`) | scroll | — | — |
| `group` | that group's tags | start scan (or menu on `< back`) | scroll | to menu | — |
| `scan` | pulsing rim + label, field on | — | — | to group | — |
| `overwrite` | existing vs target + OK/X targets | write it | — | cancel to group | — |
| `splash` | result | to group | to group | to group | — |

Leaving `SERVE` is hold-to-`EXIT` **and** a CLOSE touch target — both emit
`EXIT`. The hold is kept deliberately so a stray bump (or stray tap) cannot
drop the AP. Sampled inside `CodeServer.poll()` via `should_abort`.

## Card text / wire contract

Identical to the Box. See `BroadcastBox/BBoxFirmware/README.md` and
`HARDWARE_PROTOCOL.md`. Plain NDEF text; Classic writes never touch sector
trailers; NTAG writes start at page 4 and stop after 36 pages;
`stop_crypto1()` before every re-select.

| Item | Value |
|---|---|
| SSID / password | `SP-FILEPUSH` / `playground1` |
| Port | `8266` |
| AP channel | `1` |
| AP power save | `ap.config(pm=0)` |
| Header | `size(4B BE) \| sha256(32B) \| name_len(1B) \| name` |
| Chunk / yield | `512` / `sleep_ms(20)` |

## Files

| File | Role |
|---|---|
| `main.py` | Boot entry; prints a `fatal` JSON rather than a bare traceback |
| `bdial_server.py` | Mode machine, WRITE sub-states, serial dispatch (`device=broadcast_dial`) |
| `dial_ui.py` | LVGL screens + speaker behind `bbox_ui`'s painter API |
| `dial_input.py` | Encoder + button + touch → `NEXT`/`PREV`/`ACT`/`BACK`/`EXIT` |
| `dial_board.py` | Screen size, speaker volume, I2C placeholders, `make_reader()` |
| `code_server.py` | SoftAP + TCP file server — **PEER of Box; keep in sync** |
| `card_writer.py` | NDEF text read/write — **PEER of Box** |
| `ws1850s.py` | WS1850S driver — **PEER of Box** (pending H2) |
| `json_link.py`, `reset_log.py`, `stats_log.py` | **PEER of Box** |
| `manifest.js` | `DIAL_FILES` / `loadDialFiles()` for ChatBroadcast |
| `boot.py` | M5Stack vendor UIFlow2 boot-option stub |

Copied peers differ from the Box originals only by a leading `# PEER: …`
header. `opcodes.py` / `pn532.py` / `nfc_reader.py` are not carried over.

## Serial protocol

Same commands and events as the Box. Identity payload:

```json
{"type":"identity","device":"broadcast_dial","version":"0.1.0","w":240,"h":240,"nfc":true|false}
```

**Liveness is `heartbeat`, nothing else.** Never gate the link on `identity`.

## Deploy

```bash
ls /dev/cu.usbmodem*
cd Bag3/Code/BroadcastDial/BDialFirmware
PORT=/dev/cu.usbmodemXXXX
python3 -m mpremote connect $PORT \
  fs cp dial_board.py :/flash/dial_board.py + \
  fs cp dial_input.py :/flash/dial_input.py + \
  fs cp dial_ui.py :/flash/dial_ui.py + \
  fs cp bdial_server.py :/flash/bdial_server.py + \
  fs cp card_writer.py :/flash/card_writer.py + \
  fs cp code_server.py :/flash/code_server.py + \
  fs cp ws1850s.py :/flash/ws1850s.py + \
  fs cp json_link.py :/flash/json_link.py + \
  fs cp reset_log.py :/flash/reset_log.py + \
  fs cp stats_log.py :/flash/stats_log.py + \
  fs cp main.py :/flash/main.py + \
  reset
```

Or ChatBroadcast's firmware installer, which picks `DIAL_FILES` when identity
reports `broadcast_dial` (defaults to Box when no identity yet).

Every module reachable from `main.py` must be listed in `manifest.js`.

## Verified vs open

Software skeleton (P1) is in tree; nothing below is hardware-confirmed yet.

Open / Phase 0–3:

- **H1–H7** in `.cursor/plans/dial.plan.md` — UIFlow2 Dial 2 bring-up, reader
  chip/pins, LVGL servicing during TCP, SoftAP coexistence, radio channel.
- Card writing (P2) and wand round trip (P3) — same bar the Box README records,
  plus the wand pull the Box itself has not yet proven.
- Off-USB (battery) speaker volume check for `SPEAKER_VOLUME` in `dial_board.py`.

Static checks done off-device: `python3 -m py_compile` on every `.py`; import
graph from `main.py` matches `DIAL_FILES`.
