# Broadcast Box firmware (M5Stack StickS3, UIFlow2 MicroPython)

Writes NFC cards for a game, then serves that game's code to wands over a
SoftAP + TCP transfer. Talks to the ChatBroadcast web app over USB serial
(newline-delimited JSON).

The box is **modal**: at most one of {WiFi AP, NFC RF field} is energized at
any instant. Both were previously live from boot whenever a game was on
flash, which is the load the box browned out under on a current-limited USB
port (`known_issue.md`).

Hardware: M5Stack StickS3 (ESP32-S3) + M5Stack RFID 2 Unit (WS1850S).
Bench tested over USB on 2026-09-02 -- see **Verified vs open** below.

## Filesystem

Write all device files to **`/flash`**, not `/`.

## Hardware

| Item | Value | Notes |
|---|---|---|
| Board | M5Stack StickS3 | ESP32-S3, UIFlow2, boots in >20 s |
| Display | `M5.Lcd` landscape 240×135 | `ROTATION = 1` in `bbox_ui.py` |
| NFC | WS1850S @ I2C `0x28` | Grove HY2.0-4P, SDA=G9 SCL=G10. Replaces the PN532 (`0x24`, same pins): ~30 mA read burst vs the PN532's ~150 mA. |
| BtnA | large front button | Act: start scan / confirm / select |
| BtnB | small side button | Scroll / back out |
| USB | native CDC | Port drops on every reset; `mpremote` resets the board |

This unit has exactly two buttons. `BtnA` is wired to G11 and `BtnB` to G12,
but `buttons.py` reads them through `M5.BtnA`/`M5.BtnB` rather than raw
`machine.Pin`, so nothing depends on those GPIO numbers. Reading G11 directly
*and* through `M5.BtnA` at the same time gave two debouncers fighting over
one button; don't reintroduce that.

## Modes

| Mode | AP | Reader | Entered when |
|---|---|---|---|
| `IDLE` | down | off | No game on flash (`/flash/payload.py` absent or empty) |
| `WRITE` | down | on only while scanning | Game on flash -- this is the boot state |
| `SERVE` | **up** (`SP-FILEPUSH`) | off, and no I2C at all | Teacher selects `DONE` + BtnA |

`_set_mode()` in `bbox_server.py` is the only place modes change, and it
de-energizes what it is leaving before energizing what it is entering. If
`CodeServer.arm()` fails on the way into `SERVE` it paints an error and stays
put rather than sitting on a dead AP.

**The box does not serve code until a teacher selects `DONE` + BtnA.** A wand
tapping `getcode` before that burns its two-attempt budget (~31 s each) and
error-blinks. The `WRITE` screen header says `pickup off` for this reason.

## WRITE mode

A sub-state machine. No press-and-hold anywhere.

| State | Screen | BtnA | BtnB |
|---|---|---|---|
| `menu` | tag list, cursor on one row | start scan (or `SERVE` on the `DONE` row) | next row (wraps) |
| `scan` | `Scanning: <tag>`, field on | — | back to `menu` |
| `overwrite` | card's current text vs target | write it | cancel to `menu` |
| `splash` | result of the last action | to `menu` | to `menu` |

Tag list is `TAG_LIST` + `DONE` = `getcode`, `jumpin`, `DONE`.

On detection the scan always ends, one of three ways:

| Card holds | Result |
|---|---|
| the target text | `Already "<tag>"` splash, no write |
| nothing | written immediately, then splash |
| different text | `overwrite` prompt, BtnA commits |

Leaving `SERVE` is the one remaining hold: **BtnA for `SERVE_EXIT_MS` (1000 ms)**.
It is rare and should not fire from a stray bump. The hold is sampled inside
`CodeServer.poll()` via `should_abort`, because a transfer blocks the main
loop for its duration.

## Card text

Plain NDEF text records, **not** `opcodes.py`'s 4-byte scheme. The wand
matches by exact set membership, so the strings must stay exactly `getcode`
(the wand's `BROADCAST` set) and `jumpin` (its `GAME_TAGS`). Build/parse logic
is ported from `Bag2/Utilities/writetoNFCcards.py` and
`Bag2/Code/lib/nfc_reader.py`.

MIFARE Classic reads and writes authenticate per sector. **Any auth latches
the reader's `MFCrypto1On` bit, and while it is set the reader cannot answer a
plain `REQA`** -- so detection silently returns nothing. Toggling the antenna
does not clear it; only `stop_crypto1()` or a chip reset does. Before this was
handled, exactly one scan per boot worked and every later one found no card.
`card_writer.py` therefore calls `stop_crypto1()` before every re-select, and
`_to_scan()` clears it on scan entry.

Writes only ever target blocks `sector*4 + {0,1,2}` for sectors 1-15. Sector
trailers (`sector*4 + 3`, which hold the keys and access bits) and sector 0
are never addressed, so this code cannot set a card key or lock a sector.
NTAG writes start at page 4 and stop at 36 pages, below the NTAG21x
config/password pages.

## Wire contract (frozen -- the wand depends on every row)

| Item | Value |
|---|---|
| SSID / password | `SP-FILEPUSH` / `playground1` |
| Port | `8266` |
| AP channel | `1` (an idle ESP-NOW radio sits here, so the wand never changes channel to join) |
| AP power save | `ap.config(pm=0)` |
| Header | `size(4B big-endian) \| sha256(32B) \| name_len(1B) \| name` |
| Source / dest | `/flash/payload.py` -> `jumpin.py` |
| Chunk / yield | `512` / `sleep_ms(20)` |
| Ack | client writes `OK` / `NO`, 2 bytes |

Changing any row breaks the wand silently.

## Files

| File | Role |
|---|---|
| `main.py` | Boot entry; prints a `fatal` JSON rather than a bare traceback |
| `bbox_server.py` | Mode machine, WRITE sub-states, serial dispatch |
| `bbox_ui.py` | LCD screens + speaker feedback |
| `buttons.py` | BtnA/BtnB press edge and hold timing via `M5.BtnA`/`M5.BtnB` |
| `code_server.py` | SoftAP + TCP file server (`CodeServer`) |
| `card_writer.py` | NDEF text read/write over the WS1850S |
| `ws1850s.py` | WS1850S register driver (MFRC522-compatible) |
| `json_link.py` | Non-blocking newline-delimited JSON over stdin/stdout |
| `reset_log.py` | Persists reset cause + last mode across the USB CDC drop |
| `manifest.js` | File list for ChatBroadcast's installer |
| `boot.py` | M5Stack vendor UIFlow2 boot-option stub |
| `probe_stick.py` | Bench probe: Phase 0 StickS3 checks |
| `probe_ap_cycle.py` | Bench probe: AP down/up over repeat cycles; side-key check |
| `pn532.py`, `nfc_reader.py`, `opcodes.py` | Not imported at runtime; kept for the opcode scheme and the superseded PN532 path |

## Serial protocol

Host sends `cmd`, device replies with `type`. See
`Bag3/Code/Stations/serial_protocol_notes.md`.

Commands: `identify`, `info`, `mode`, `arm`, `disarm`, `repl`, `reboot`,
`games.list`, `games.select`, `games.delete`, `games.clear`, `stats.get`,
`stats.reset`

Events: `identity`, `info`, `mode`, `heartbeat`, `armed`, `card_present`,
`card_written`, `games`, `stats`, `ok`, `error`, `bye`, plus `fatal` from
`main.py`

**Liveness is `heartbeat`, nothing else.** The Box sends one every
`HEARTBEAT_MS` (5s) unconditionally while `run()` is looping. A host decides
the link is up on *any* typed message and must never wait on a specific one.

**`identify` vs `info` vs `mode`** -- three different questions, kept apart on
purpose:

- `identify` -> `identity`: who and what this device is. `device`, `version`,
  screen `w`/`h`, and `nfc` (the real `_init_nfc()` result, not a hardcoded
  `true`). Every field is fixed for the life of a boot. The Box also volunteers
  this once at boot, which is *informational only* -- it is not an introduction
  or a readiness signal, and a host that attaches later never sees it.
- `info` -> `info`: live runtime status. `mem`, `armed`, `linked`,
  `payload_ready`, `written`, `up`.
- `mode` -> `mode`: which mode the Box is in (`WRITE`/`SERVE`/`IDLE`) plus
  `games`, `active` and `ssid`. Emitted from `_set_mode()` on every transition,
  including exits, and once at boot.

Do not add changing values to `identity`, and do not use it as a handshake --
that conflation is what this split exists to prevent.

`arm` means "go to `SERVE`" and `disarm` means "return to `WRITE`/`IDLE`".
They are REPL/legacy entry points; the app does not call them after pushing
code.

`repl`, a soft `reboot`, or an uncaught exception all unwind through
`run()`'s `finally`, which calls `_shutdown_radios()` to bring the AP down
and the field off. Without it the AP stayed up with nothing serving it.

## Payload flow

1. App writes `/flash/payload.py` over the raw REPL and soft-resets.
2. On that reboot the box sees a game on flash and starts in `WRITE`. **The AP
   stays down.** There is no `RECEIVING` mode -- the push interrupts this
   program, so an upload is never a state the firmware occupies.
3. Teacher writes `getcode` / `jumpin` cards from the `WRITE` menu.
4. Teacher selects `DONE` + BtnA. AP comes up; box is serving.
5. Wand taps `getcode`, reboots, joins `SP-FILEPUSH` on a cold radio, pulls
   `jumpin.py`, reboots into the game (`MockWand/code_puller.py`).

## Serial logging

Each of `bbox_server.py`, `card_writer.py` and `bbox_ui.py` has a
module-level `VERBOSE = False`. Set one to `True` to trace it.

Gated: button presses, mode/sub-state transitions, antenna toggles,
per-attempt re-select misses, auth-OK narration, per-font-selection lines.

Never gated: card detected, read result, overwrite prompt, write attempt and
outcome, verify result, every abort with its reason, any exception, and
`shutdown: AP down`. A failure always prints.

Output is `print()` to USB serial and is not stored; only `reset_log` writes
to flash.

## Reset cause

The board's USB is native CDC, so a reset drops the port and any message goes
into a port the host has already lost. `reset_log.record()` runs as the first
statement of `run()` and appends this boot's `machine.reset_cause()` to
`/flash/resetlog.txt`, capped at 40 lines.

`note_mode()` persists the current mode to `/flash/lastmode.txt` on every
change, so each line names the mode the box was in **before** the reset:

```
2906 HARD was:SERVE
2794 HARD was:?
```

Read it with `reset_log.last(n)`, newest first. `was:?` means no mode was
recorded, not `IDLE`.

## Deploy

Confirm the port first -- names change between sessions and the box and wand
enumerate as sibling names:

```bash
ls /dev/cu.usbmodem*
```

Nothing else may hold the port; ChatBroadcast holds it over WebSerial while
connected. Every `mpremote` command resets the box and it boots in >20 s, so
batch work into one invocation.

```bash
cd Bag3/Code/BroadcastBox/BBoxFirmware
PORT=/dev/cu.usbmodemXXXX
python3 -m mpremote connect $PORT \
  fs cp bbox_server.py :/flash/bbox_server.py + \
  fs cp bbox_ui.py :/flash/bbox_ui.py + \
  fs cp buttons.py :/flash/buttons.py + \
  fs cp card_writer.py :/flash/card_writer.py + \
  fs cp code_server.py :/flash/code_server.py + \
  fs cp ws1850s.py :/flash/ws1850s.py + \
  fs cp json_link.py :/flash/json_link.py + \
  fs cp reset_log.py :/flash/reset_log.py + \
  fs cp main.py :/flash/main.py + \
  reset
```

Or use ChatBroadcast's firmware installer, which pushes `BOX_FILES` from
`manifest.js`. Every module reachable from `main.py` must be listed there --
a missing one is an `ImportError` at boot and a `fatal` JSON, which looks
like a bricked box.

`mpremote ... exec` enters the raw REPL, which interrupts the running
program; the server does not restart until the next reset. To watch the log
without interrupting it, read the port passively instead.

## Verified vs open

Confirmed on hardware 2026-09-02, over USB:

- Boots to the `WRITE` tag list; screens legible at 240×135.
- BtnA/BtnB drive the menu, scan, overwrite and splash states.
- Repeated card reads and writes within one boot, across two cards, both
  directions (`getcode` <-> `jumpin`), each `verify OK`.
- `WRITE` -> `SERVE` -> `WRITE` without a reboot.
- `arm` then `repl` brings the AP down (`shutdown: AP down`).
- 200+ s of steady heartbeats with free memory flat; no `BROWNOUT`, no `WDT`.

Open:

- **No wand round trip yet.** Nothing has pulled code from this build, so
  step 5 of the payload flow is unproven end to end.
- **In-place AP cycling is only lightly exercised.** `probe_ap_cycle.py`
  exists for this (10 cycles, then leaves the AP up for a wand join) and has
  not been run. If a repeat cycle within one boot proves unreliable,
  `_set_mode()` is the single place that would switch to writing a mode flag
  and resetting into the new mode.
- **Re-selects miss intermittently at the RF level.** Seen with
  `crypto=False`, i.e. not the latch above -- a card drifting out of range.
  Costs a retry; a write aborts on the first miss rather than retrying.
- The reader is still driven over `machine.SoftI2C` with no clock-stretch
  timeout, the second hypothesis in `known_issue.md`.
- Off-USB (battery) operation is untested for this build.
