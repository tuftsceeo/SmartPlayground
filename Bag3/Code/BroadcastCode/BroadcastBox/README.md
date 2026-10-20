# Broadcast Box firmware (M5Stack StickS3, UIFlow2 MicroPython)

Writes NFC cards for a game, then serves that game's code to wands over
ESP-NOW. Talks to the ChatBroadcast web app over USB serial
(newline-delimited JSON).

The box is **modal**: at most one of {radio, NFC RF field} is energized at
any instant. Both were previously live from boot whenever a game was on
flash, which is the load the box browned out under on a current-limited USB
port (`../../known_issues/2026-09-01-bbox-usb-reboots.md`).

Hardware: M5Stack StickS3 (ESP32-S3) + M5Stack RFID 2 Unit (WS1850S).
Bench tested over USB -- see **Verified vs open** below.

## Filesystem

Write all device files to **`/flash`**, not `/`.

## Hardware

| Item | Value | Notes |
|---|---|---|
| Board | M5Stack StickS3 | ESP32-S3, UIFlow2, boots in >20 s |
| Display | `M5.Widgets` **portrait** 135×240 | `ROTATION = 0` in `bbox_ui.py` — a physical-orientation change from the landscape 240×135 every earlier version of this file used; confirm the Box's mounting/holding tolerates it. Two UI attempts preceded this one: an LVGL/`m5ui` port **failed on this board** (`ImportError: no module named 'm5ui'`, confirmed 2026-09-10 -- the module isn't in this board's UIFlow2 build, not a heap issue), then a direct `M5.Lcd`/M5GFX landscape restyle worked but was superseded by this `Widgets`-based portrait version, modeled on a hand-drawn UIFlow2 mockup. Colors/type come from `Live_Page/.design_system/Sept 2026/`, adapted to what `Widgets` can render (no gradients, no confirmed rounded corners, Montserrat standing in for Nunito) — see `bbox_ui.py`'s module docstring for the full mapping |
| NFC | WS1850S @ I2C `0x28` | Grove HY2.0-4P, SDA=G9 SCL=G10. Replaces the PN532 (`0x24`, same pins): ~30 mA read burst vs the PN532's ~150 mA. |
| BtnA | large front button | Act: start scan / confirm / select |
| BtnB | small side button | Scroll / back out |
| USB | native CDC | Port drops on every reset; `mpremote` resets the board |

This unit has exactly two buttons. `BtnA` is wired to G11 and `BtnB` to G12,
but `buttons.py` reads them through `M5.BtnA`/`M5.BtnB` rather than raw
`machine.Pin`, so nothing depends on those GPIO numbers. Reading G11 directly
*and* through `M5.BtnA` at the same time gave two debouncers fighting over
one button; don't reintroduce that.

## Radio memory order -- nothing new ahead of `prewarm()`

The radio needs one large **contiguous** block of IDF DRAM and takes it early;
nothing later in boot can un-fragment the heap enough to find it again.
`gc.mem_free()` does not measure this: the failure is fragmentation, not
exhaustion.

`run()` calls `code_link.prewarm()` (ESP-NOW and STA up, then down) right after
`M5.begin()`, before the UI and reader are built. `code_link.py` is imported at
`bbox_server.py` module scope, so anything added to it is allocated before
`prewarm()`. `code_sender.py` is imported inside `CodeLink.arm()`, after the
radio is up.

Rules:

1. No new module-scope content in `code_link.py`.
2. Diagnostics go in a separate module imported after the radio is up.
3. `prewarm()` stays directly after `M5.begin()`.

Full note: [`docs_and_design/2026-09-23-ap-memory-order.md`](../docs_and_design/2026-09-23-ap-memory-order.md)

## Modes

At most one of {radio, NFC RF field} is energized at any instant.

| Mode | ESP-NOW | Reader | Entered when |
|---|---|---|---|
| `IDLE` | down | off | No game on flash (`/flash/payload.py` absent or empty) |
| `WRITE` | up while the field is off (`SHARE_IN_MENUS`) | on only while scanning | Game on flash -- this is the boot state |
| `SERVE` | up | off, and no I2C at all | Teacher selects `DONE` + BtnA, or serial `arm` |

`_set_mode()` in `bbox_server.py` is the only place modes change, and it
de-energizes what it is leaving before energizing what it is entering.
`_nfc_field()` disarms the radio before the field comes up; `_menu_share()`
re-arms it from the WRITE loop once the field is down. A failed arm is
retried after `SHARE_RETRY_MS` (2000 ms). If `CodeLink.arm()` fails on the
way into `SERVE` the Box paints an error and stays put.

With `SHARE_IN_MENUS = False`, WRITE keeps the radio down and only `SERVE`
serves.

## WRITE mode

A sub-state machine. No press-and-hold anywhere.

| State | Screen | BtnA | BtnB |
|---|---|---|---|
| `menu` | group list, cursor row in the fixed SELECTED slot | open the group (or `SERVE` on the `DONE` row) | next row (wraps) |
| `group` | that group's tags, cursor row in the fixed SELECTED slot | start scan (or back on `< back`) | next row (wraps) |
| `scan` | title + hint on the shared status screen, field on | — | back to `group` |
| `splash` | result of the last action | to `group` | to `group` |

No overwrite confirmation: a card holding different text is overwritten
the same as a blank one. A teacher who wants to check a card before
writing uses the read utility for that, rather than a prompt on every
write.

The list screen is a fixed 5-row carousel (`Widgets.Rectangle` +
`Widgets.Label` pairs): 2 rows above the cursor, the cursor's own row
always rendered in one visually distinct SELECTED slot (purple, the
brand's `--write-fg`/`--write-bg` tokens), 2 rows below — see
`bbox_ui.py`'s module docstring. A column of small indicator dots to the
right shows which of those 5 slots hold real list entries. This board
has no touch, so `BtnA`/`BtnB` are always physical buttons read through
`buttons.py`; the on-screen action label and the small chevron button
are display-only.

The menu is two levels. Top level is one row per game, then `Utility Tags`,
then `DONE`; opening a game lists `getcode:<slug>`, `<slug>`, the tags the game
declares, and `< back`. So the number of presses to reach `DONE` tracks the
number of games, not the number of tags — melody alone contributes eleven.

A game's own tags come from `/flash/games/<slug>.tags.json`, written beside the
`.py` by ChatBroadcast in the same REPL session and re-read on every boot scan.
A game with no sidecar contributes only its two pickup tags.

`UTILITY_TAGS` = `stop`, `battery`. They are always offered, including when no
game is loaded, so a `stop` card can be written on a bare box. With an empty
index the first group falls back to `TAG_LIST` = `getcode`, `jumpin`.

Scan and splash both return to the open group rather than the top level, so
writing eight note cards does not mean re-entering the group eight times.

`Widgets.Label` does not clip, so `bbox_ui._fit()` caps each row at
`ROW_CHARS`/`SELECTED_CHARS`, keeping the start of the name and appending
`...` — reported on hardware that splitting the budget between both ends
(the earlier design, to keep a numbered variant like `_melody_2`
distinguishable) cut the meaningful prefix down past legibility. The
budgets are character-count estimates for proportional Montserrat on a
119px-wide card, not measured pixel widths; confirm on the device.

On detection the scan always ends, one of two ways:

| Card holds | Result |
|---|---|
| the target text | `Already "<tag>"` splash, no write |
| anything else (nothing, or different text) | written immediately, then splash |

Leaving `SERVE` is the one remaining hold: **BtnA for `SERVE_EXIT_MS` (1000 ms)**.
It is rare and should not fire from a stray bump. The hold is sampled inside
`CodeLink.poll()` via `should_abort`, once per tick; every in-flight wand is
dropped and its pull fails.

## Serving over ESP-NOW

`code_link.CodeLink` serves; `code_sender.CodeSender` runs the protocol;
`NativeManager` drives `espnow` directly. The wand drives the transfer:

| Direction | Message |
|---|---|
| wand -> broadcast | `{"type":"code_req","id":r,"slug":s,"hub":h[,"host":id]}` |
| Box -> wand | `{"type":"code_offer","id":r,"name":n,"size":N,"sha":hex,"chunks":K,"chunk":245}`; `size` 0 is a refusal (`why`) |
| display -> Box | `{"type":"code_req","id":r,"slug":s,"hub":h,"file":<icon>}` (one icon) or `{...,"list_from":k}` (next page of icon names) |
| Box -> display | `{"type":"code_icons","id":r,"from":k,"n":total,"icons":[...]}` |
| wand -> Box | `{"type":"code_get","id":r,"from":i,"n":w}` (window of at most 16) |
| Box -> wand | raw frames `CX` + id(1) + seq(2) + up to 245 B |
| wand -> Box | `{"type":"code_done","id":r,"ok":b[,"why":...]}` |

A `code_req` with `host` set to another device's `HOST_ID` is ignored: a card
written for a Dial (`@004c`) does nothing on the Box. Up to `MAX_SESSIONS` (6)
wands are served at once; more get a `busy` offer and retry. A session idle
for `SESSION_IDLE_MS` (15 s) is dropped and reported as a failed pull. Files
are `/flash/games/<slug>.py`; an empty slug means `/flash/active.txt`.

Roles served (`code_sender.ROLE_FILES`): `wand` (and an empty `hub`) gets
`<slug>.py`; `icon_display` gets `<slug>_icon.py`, offered as `<slug>.py`. The
`icon_display` offer also carries `icons_n` (how many files are in
`/flash/games/<slug>_icons/`, `.py` only, at most 64) and `icons`, the names
that fit one 250 B ESP-NOW frame. The display asks for the rest with
`list_from`, answered by `code_icons`, then sends one `code_req` with `file`
per icon, offered under that name. A `file` request needs an explicit slug and
a role with icons; names containing `/` or `..`, or not ending in `.py`, are
refused with `why` `"no such icon"`. Icon transfers are counted in
`icons_served` / `icons_failed` and do not touch `last_result` or `stats_log`.
The `pull` serial event carries the served game's `slug` and the requester's
`hub` as `role`.

`CodeLink.poll(on_event, should_abort)` handles one radio message per call.
`on_event` fires `'serving'` when a wand is offered a file and `'ok'`/`'fail'`
when it finishes; the finished transfer is in `last_result`, recorded to
`stats_log`. The SERVE screen shows the live count (`serving_count`).

### TX power

`TX_POWER_DBM = 8` in `bbox_server.py`; `CodeLink(tx_power=TX_POWER_DBM)`
passes it to `NativeManager`, which sets `sta.config(txpower=...)`. `None`
leaves the driver default. At the default power the Box reset (PWRON) under
transmit load on USB; at 8 dBm it did not. Wands are held next to the Box.

### Power

`bbox_ui.py` sets `DARK = True` (black page ground, brightened hues) and
`SOUND = False` (no speaker) to reduce draw on a current-limited supply.

## Card text

Plain NDEF text records, **not** `opcodes.py`'s 4-byte scheme. The wand
matches by exact set membership, so the strings must stay exactly `getcode`
(the wand's `BROADCAST` set) and `jumpin` (its `GAME_TAGS`). Build/parse logic
is ported from `Bag2/Utilities/writetoNFCcards.py` and
`Bag2/Code/lib/nfc_reader.py`. That opcode scheme is still used for ESP-NOW
game names; `MockWand/lib/nfc_reader.py` does not consult it.
`card_writer.py` keeps a hand-copied `_decode_ndef_text` mirroring the
wand's — keep the two in sync.

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

ESP-NOW, channel 1 (STA default, not connected). The wand drives the transfer;
the messages are in "Serving over ESP-NOW" above. `getcode:<slug>@<id>` cards
carry `<id>` = `code_link.HOST_ID` (cd64 on the bench Box); `_write_card()`
appends it to `getcode` rows only. Frame chunk 245 B.

`_icon` and `_splat` are reserved suffixes on the Box and the Dial (the full
list is `Bag3/Code/HARDWARE_PROTOCOL.md`, "Reserved Box/Dial staging
suffixes"): `_boot_scan_games()` skips any name ending in one of them when
building the game menu. A game slug may not end in a reserved suffix.
`ChatBroadcast/js/gameName.js` refuses these slugs client-side; the
device-side scan is the backstop for anything that reaches it another way.

Alongside `/flash/games/<slug>.py`, ChatBroadcast pushes
`/flash/games/<slug>.tags.json` -- a JSON array of the game's tag names --
in the same raw-REPL session, no extra reset. The Box reads it in
`_boot_scan_games()`; it fills that game's group in the WRITE menu, and
without it a game offers only its two pickup tags. The list derives from
the game's own `COMMANDS` set by `ChatBroadcast/js/nfc.js`, which also
drives the send checklist. `tools/check_tags.mjs` in `ChatBroadcast/`
asserts that derivation against every game source.

`stop` and `battery` are always writable from the Box's `Utility Tags`
group, whatever is loaded.

The protocol is hand-duplicated in `BBoxFirmware/code_sender.py`,
`BroadcastDial/BDialFirmware/code_sender.py`, `EspnowModem/host/code_sender.py`
and the wand and display receivers (`espnow_code.py`); no shared module. Each carries a `PEER:` comment.
Change them together.

## Files

| File | Role |
|---|---|
| `main.py` | Boot entry; prints a `fatal` JSON rather than a bare traceback |
| `bbox_server.py` | Mode machine, WRITE sub-states, serial dispatch |
| `bbox_ui.py` | LCD screens + speaker feedback |
| `buttons.py` | BtnA/BtnB press edge and hold timing via `M5.BtnA`/`M5.BtnB` |
| `code_link.py` | `CodeLink`, `NativeManager`, `prewarm()`, `HOST_ID`; see "Serving over ESP-NOW" — **PEER of Dial** |
| `code_sender.py` | ESP-NOW sender — **PEER of `EspnowModem/host/code_sender.py`** |
| `stats_log.py` | Pull and tag-write counters |
| `card_writer.py` | NDEF text read/write over the WS1850S |
| `ws1850s.py` | WS1850S register driver (MFRC522-compatible) |
| `json_link.py` | Non-blocking newline-delimited JSON over stdin/stdout |
| `reset_log.py` | Persists reset cause + last mode across the USB CDC drop |
| `manifest.js` | File list for ChatBroadcast's installer |
| `boot.py` | M5Stack vendor UIFlow2 boot-option stub |
| `pn532.py`, `nfc_reader.py`, `opcodes.py` | Not imported at runtime; kept for the opcode scheme and the superseded PN532 path |
| `code_server.py`, `serve_probe.py`, `serve_guard.py` | Superseded SoftAP/TCP path; not in `BOX_FILES`, not imported |
| `tools/probe_stick.py` | Bench probe: Phase 0 StickS3 checks |
| `tools/probe_ap_cycle.py` | Bench probe for the superseded SoftAP path; not part of `BOX_FILES` |
| `tools/box_menu_check.py` | Host-side (no hardware) check of the WRITE-menu logic |
| `tools/widget_test.py` | Bench diagnostic: `Widgets` glyph coverage + a same-value-redraw theory, both raised by hardware bug reports on `bbox_ui.py` |

## Serial protocol

Host sends `cmd`, device replies with `type`. See
`Bag3/Code/Stations/serial_protocol_notes.md`.

Commands: `identify`, `info`, `mode`, `arm`, `disarm`, `repl`, `reboot`,
`games.list`, `games.select`, `games.delete`, `games.clear`, `stats.get`,
`stats.reset`

`games.list` returns `slug`, `name`, `bytes`, `pulls` and `tags` per game.
`tags` is the game's own card list, read from `<slug>.tags.json`; it is what
lets a host show the right expected-card list for a game that host never sent.
Empty for a game pushed without a sidecar.

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
  `games` and `active`; `ssid` is always `null`. Emitted from `_set_mode()` on every transition,
  including exits, and once at boot.

Do not add changing values to `identity`, and do not use it as a handshake --
that conflation is what this split exists to prevent.

`arm` means "go to `SERVE`" (its reply and `armed` carry `ssid: null`) and `disarm` means "return to `WRITE`/`IDLE`".
They are REPL/legacy entry points; the app does not call them after pushing
code.

`repl`, a soft `reboot`, or an uncaught exception all unwind through
`run()`'s `finally`, which calls `_shutdown_radios()` to bring the radio down
and the field off.

## Payload flow

1. App writes `/flash/payload.py` over the raw REPL and soft-resets.
2. On that reboot the box sees a game on flash and starts in `WRITE`. With
   `SHARE_IN_MENUS` the radio is up whenever the reader field is off. There
   is no `RECEIVING` mode -- the push interrupts this program, so an upload
   is never a state the firmware occupies.
3. Teacher opens the game's group in the `WRITE` menu and writes its cards --
   `getcode:<slug>`, `<slug>`, and whatever the game itself needs.
4. Teacher taps the card on a wand (or selects `DONE` + BtnA for `SERVE`).
5. The wand sends a `code_req`, pulls the file over ESP-NOW, and reboots into
   the game (`MockWand/code_puller.py`).

## Serial logging

Each of `bbox_server.py`, `card_writer.py` and `bbox_ui.py` has a
module-level `VERBOSE = False`. Set one to `True` to trace it.

Gated: button presses, mode/sub-state transitions, antenna toggles,
per-attempt re-select misses, auth-OK narration, per-font-selection lines.

Never gated: card detected, read result, write attempt and
outcome, verify result, every abort with its reason, any exception, and
`shutdown: AP down` (the radio-down line). A failure always prints.

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

## Stats log

`stats_log.py` -> `/flash/stats.log` (200 lines) plus `/flash/stats_since.txt`.
Product data, never gated:

```
<ticks> pull <slug> ok|fail
<ticks> tag  <label> ok
```

`aggregate()` returns `{pulls:{slug:n}, writes:{label:n}, since:<ticks>}`.
Written from `code_link._record()` (every completed serve, attributed to the
requested slug) and from the card-write success branch in `bbox_server.py`.

The Box/Dial screen reads this at boot via `_load_stats()`, then counts in
memory -- WRITE tag list and SERVE "pickups" are cumulative totals across
all boots, not a session tally. `stats.reset` zeroes both the log and the
in-memory counters.

## Deploy

Confirm the port first -- names change between sessions and the box and wand
enumerate as sibling names:

```bash
ls /dev/cu.usbmodem*
```

Nothing else may hold the port; ChatBroadcast holds it over WebSerial while
connected. Pass `resume` on every `mpremote` call against this board or the
first `fs`/`exec` de-enumerates the USB CDC port (see
`Bag3/Code/HARDWARE_PROTOCOL.md`). Batch work into one invocation, then a
plain `reset` (no `resume`) to bring the new code up -- `resume` avoids the
reboot on the write, it does not restart the program.

```bash
cd Bag3/Code/BroadcastCode/BroadcastBox/BBoxFirmware
PORT=/dev/cu.usbmodemXXXX
python3 -m mpremote connect $PORT resume \
  fs cp bbox_server.py :/flash/bbox_server.py + \
  fs cp bbox_ui.py :/flash/bbox_ui.py + \
  fs cp buttons.py :/flash/buttons.py + \
  fs cp card_writer.py :/flash/card_writer.py + \
  fs cp code_link.py :/flash/code_link.py + \
  fs cp code_sender.py :/flash/code_sender.py + \
  fs cp stats_log.py :/flash/stats_log.py + \
  fs cp ws1850s.py :/flash/ws1850s.py + \
  fs cp json_link.py :/flash/json_link.py + \
  fs cp reset_log.py :/flash/reset_log.py + \
  fs cp main.py :/flash/main.py
python3 -m mpremote connect $PORT reset
```

Or use ChatBroadcast's firmware installer, which pushes `BOX_FILES` from
`manifest.js`. Every module reachable from `main.py` must be listed there --
a missing one is an `ImportError` at boot and a `fatal` JSON, which looks
like a bricked box. Check mechanically: walk the import graph from `main.py`
and compare against `BOX_FILES`. `boot.py` is deliberately absent; game
files are pushed separately to `/flash/games/<slug>.py` by
`boxFirmwareInstaller.js`.

`mpremote ... exec` enters the raw REPL, which interrupts the running
program; the server does not restart until the next reset. To watch the log
without interrupting it, read the port passively instead.

## Verified vs open

Verified on hardware 2026-10-20 (`docs_and_design/2026-10-20-espnow-serving/RESULTS.md`),
over USB at `TX_POWER_DBM = 8`:

- 3/3 pulls to a wand.
- Earlier runs at the default TX power reset the board (PWRON) mid-transfer.

Verified on hardware 2026-09-02, over USB (mode machine, card writes):

- Boots to the `WRITE` tag list.
- BtnA/BtnB drive the menu, scan and splash states.
- Repeated card reads and writes within one boot, across two cards, both
  directions (`getcode` <-> `jumpin`), each `verify OK`.
- `WRITE` -> `SERVE` -> `WRITE` without a reboot.

Open:

- Off-USB (battery) operation.
- Readability of the black UI (`DARK`) in a classroom.
- Several wands at once, and the icon-display role on hardware (offline tests only).
- **Re-selects miss intermittently at the RF level.** Seen with
  `crypto=False`, i.e. not the latch above -- a card drifting out of range.
  Costs a retry; a write aborts on the first miss rather than retrying.
- The reader is still driven over `machine.SoftI2C` with no clock-stretch
  timeout, the second hypothesis in `../../known_issues/2026-09-01-bbox-usb-reboots.md`.

Static check done off-device: `python3 -m py_compile` on every `.py`.