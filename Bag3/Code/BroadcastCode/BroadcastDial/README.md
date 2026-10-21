# Broadcast Dial firmware (M5 Dial 2 / StampS3A, UIFlow2 MicroPython)

Sibling of `Bag3/Code/BroadcastCode/BroadcastBox/BBoxFirmware/`. Same product — write NFC
cards for a game, then serve that game's code to wands over ESP-NOW,
talking to ChatBroadcast over USB serial — on better hardware: a 240×240
round touch LCD, rotary encoder, button, and a built-in NFC reader.

The Dial keeps the Box's mode machine, wire contract, card-safety rules and
serial protocol byte-for-byte. Only the board, the input model and the
screen layer differ. ChatBroadcast accepts both devices from one app.

**Phase 0 (hardware gate) is mostly closed.** `dial_board.py`'s I2C pins
are filled in and the reader is confirmed live (`probe_dial.py` H2/H3:
WS1850S-class chip at `0x28`, `VersionReg` reads `0x15`, over the hardware
`machine.I2C` peripheral — SoftI2C ACKs a bare scan but times out on a real
register read on this bus). Still open: H6/H7. Software pass is P1/P4/P5 of
`.cursor/plans/dial.plan.md`.

## Filesystem

Write all device files to **`/flash`**, not `/`.

## Hardware

| Item | Value | Notes |
|---|---|---|
| Board | M5 Dial 2 (StampS3A) | UIFlow2 MicroPython; assume Dial family bring-up via `M5.begin()` + `m5ui.init()` (H1) |
| Display | LVGL / `m5ui`, 240×240 round | 4 pages built once, re-textured and swapped with `screen_load()` (was 17 — consolidated to fix an out-of-memory failure) |
| NFC | WS1850S @ I2C `0x28`, external Grove unit preferred | `dial_board.py`'s `make_reader()` auto-detects: it tries an external Grove RFID2 unit on Port A first (`sda=13 scl=15`, confirmed live 2026-09-22 via `probe_dial.py` stage 4 and a real card test) and falls back to the built-in reader (`sda=11 scl=12`, shares the bus with touch @ `0x38` and RTC @ `0x51`) when nothing acks on Port A. Both are hardware `machine.I2C` (confirmed H2/H3). The built-in reader's read/write was markedly less reliable than the Box's external Grove RFID2 unit despite identical code (`card_writer.py`/`ws1850s.py` are PEER copies, same poll timeouts) -- antenna detuning from sharing the enclosure with the LCD, touch controller, RTC, encoder and speaker, not software, confirmed by wiring the external unit and re-testing |
| Encoder | `hardware.Rotary` | CW/CCW → `NEXT`/`PREV`; magnitude honoured, capped |
| Button | `M5.BtnA` (encoder press) | Short click → `ACT` |
| Touch | LVGL callbacks | Enqueue intents only; server drains from its own loop |
| USB | native CDC | Port drops on every reset; `mpremote` resets the board |

Colours come from `Live_Page/.design_system/Sept 2026/tokens/` — the same
brand tokens `bbox_ui.py` carries, so the two devices read as one product.
Pink is the one primary action per screen, purple (`--write-fg`/`--write-bg`)
is the selection and anything write-mode, teal (`--serve-fg`) is success and
share-mode. `dial_ui.py` and `bbox_ui.py` hand-duplicate the palette block
because they are deliberately on **different rendering stacks** — M5's docs
warn against mixing M5GFX/M5Widgets/M5UI, and the Box's StickS3 build has no
`m5ui` at all — so they share tokens, never a renderer.

Form reference (not a logic peer): `Bag2/Code/DialSpeaker/Dial_Music.py` —
borderless buttons, generous radius, a large `montserrat_24` symbol, and soft
drop shadows, all already proven on this display. The shadows here are
coloured rather than grey, per the design system. The tag list is a
`m5ui.M5Roller` (centre-selected wheel) rather than three bare labels, with a
breadcrumb chip naming the current tier and a right-rim position track.

Screen copy is **Title Case**, which deliberately diverges from the design
system's "sentence case everywhere" rule: these screens are read at arm's
length in a classroom, not in a browser. ALL-CAPS is reserved for button
labels. See `dial_ui.py`'s module docstring for the full screen inventory and
what in it is still unverified on hardware.

## Radio memory order — nothing new ahead of `prewarm()`

The radio needs one large **contiguous** block of IDF DRAM and takes it early;
nothing later in boot can un-fragment the heap enough to find it again.
`gc.mem_free()` does not measure this: the failure is fragmentation, not
exhaustion.

`run()` calls `code_link.prewarm()` (ESP-NOW and STA up, then down) right after
`M5.begin()`, before the UI and reader are built. `code_link.py` is imported at
`bdial_server.py` module scope, so anything added to it is allocated before
`prewarm()`. `code_sender.py` is imported inside `CodeLink.arm()`, after the
radio is up.

With the UI built before the radio, transfers fail: each send blocks 2 s and
raises `ESP_ERR_ESPNOW_NO_MEM`, with about 8.5 KB of internal heap free
(`docs_and_design/2026-10-20-espnow-serving/RESULTS.md`).

Rules:

1. No new module-scope content in `code_link.py`.
2. Diagnostics go in a separate module imported after the radio is up.
3. `prewarm()` stays directly after `M5.begin()`.

Full note: [`docs_and_design/2026-09-23-ap-memory-order.md`](../docs_and_design/2026-09-23-ap-memory-order.md)

## Modes

At most one of {radio, NFC RF field} is energized at any instant.

| Mode | ESP-NOW | Reader | Entered when |
|---|---|---|---|
| `IDLE` | down | off | No game on flash |
| `WRITE` | up while the field is off | on only while scanning | Game on flash — boot state |

There is no user-visible mode switch: the Dial serves the active game from
the menus whenever the field is off. `_set_mode()` in `bdial_server.py` is the only place modes change.
`_nfc_field()` is the only place the field changes: it disarms the radio before
the field comes up, and after the field goes down it clears `MFCrypto1On`
(`stop_crypto1()`); the WRITE loop then re-arms the radio. A failed arm is
retried after `SHARE_RETRY_MS`. With `SHARE_IN_MENUS = False` the radio
stays down.

## WRITE mode

Two-level menu (groups → tags), same shape as the Box including `W_GROUP`.

| State | Screen | ACT | NEXT/PREV | BACK | EXIT |
|---|---|---|---|---|---|
| `menu` | group list (roller), focused entry centred | open group | scroll | — | — |
| `group` | that group's tags (roller) | start scan (or menu on `< back`) | scroll | to menu | — |
| `scan` | rim ring + label, field on | — | — | to group | — |
| `splash` | result | to group | to group | to group | — |

The utility group carries a third entry the Box has no equivalent for:
`Read Card` (`READ_ENTRY`). It is a sentinel `_scan_step()` special-cases
before the row is ever treated as NDEF text, so it is never written; the
result lands on `paint_read_result()`.

The Dial has **no `overwrite` state** — unlike the Box, it auto-overwrites
and confirms only with `beep_success()`/`beep_fail()`. The antenna sits
under the screen, so a card actually on the reader covers the same touch
targets a confirm/cancel prompt would need.

## Serving over ESP-NOW

`code_link.CodeLink` serves; `code_sender.CodeSender` (a PEER copy of
`EspnowModem/host/code_sender.py`) runs the protocol; `NativeManager` drives
`espnow` directly (no C6 antenna pins). The wand drives the transfer:

| Direction | Message |
|---|---|
| wand → broadcast | `{"type":"code_req","id":r,"slug":s,"hub":h[,"host":id]}` |
| Dial → wand | `{"type":"code_offer","id":r,"name":n,"size":N,"sha":hex,"chunks":K,"chunk":245}`; `size` 0 is a refusal (`why`) |
| display → Dial | `{"type":"code_req","id":r,"slug":s,"hub":h,"file":<icon>}` (one icon) or `{...,"list_from":k}` (next page of icon names) |
| Dial → display | `{"type":"code_icons","id":r,"from":k,"n":total,"icons":[...]}` |
| wand → Dial | `{"type":"code_get","id":r,"from":i,"n":w}` (window of at most 16) |
| Dial → wand | raw frames `CX` + id(1) + seq(2) + up to 245 B |
| wand → Dial | `{"type":"code_done","id":r,"ok":b[,"why":...]}` |

A `code_req` with `host` set to another Dial's `HOST_ID` is ignored. Up to
`MAX_SESSIONS` (6) wands are served at once; more get a `busy` offer and
retry. A session idle for `SESSION_IDLE_MS` (15 s) is dropped and reported as
a failed pull. Files are `/flash/games/<slug>.py`; an empty slug means
`/flash/active.txt`.

Roles served (`code_sender.ROLE_FILES`): `wand` (and an empty `hub`) gets
`/flash/games/<slug>.py`; `icon_display` gets `<slug>_icon.py`, offered as
`<slug>.py`. The `icon_display` offer also carries `icons_n` (how many files
are in `/flash/games/<slug>_icons/`, `.py` only, at most 64) and `icons`, the
names that fit one 250 B ESP-NOW frame. The display asks for the rest with
`list_from`, answered by `code_icons`, then sends one `code_req` with `file`
per icon; the sender offers it under that name. A `file` request needs an
explicit slug and a role with icons; names containing `/` or `..`, or not
ending in `.py`, are refused with `why` `"no such icon"`. Icon transfers are
counted in `icons_served` / `icons_failed` and do not touch `last_result` or
`stats_log`.

`CodeLink.poll(on_event, should_abort)` handles one radio message per call.
`on_event` fires `'serving'` when a wand is offered a file and `'ok'`/`'fail'`
when it finishes; the finished transfer is in `last_result`, recorded to
`stats_log`, and emitted as a `pull` serial event.

Verification: `tools/devtests/test_dial_code_link.py` (CPython, the real wand
receiver over a fake radio) and `EspnowModem/tests/test_code_xfer.py`.

## Card text / wire contract

Identical to the Box. See `BroadcastBox/BBoxFirmware/README.md`. Plain NDEF
text; Classic writes never touch sector trailers; NTAG writes start at page
4 and stop after 36 pages; `stop_crypto1()` before every re-select.

| Item | Value |
|---|---|
| getcode card | `getcode:<slug>@<id>` (`<id>` = `code_link.HOST_ID`) |
| ESP-NOW channel | 1 (STA default, not connected) |
| Frame chunk | 245 B |

## Files

| File | Role |
|---|---|
| `main.py` | Boot entry; prints a `fatal` JSON rather than a bare traceback |
| `bdial_server.py` | Mode machine, WRITE sub-states, serial dispatch (`device=broadcast_dial`) |
| `dial_ui.py` | 4 LVGL screens (brand palette, roller list) + speaker behind `bbox_ui`'s painter API |
| `dial_input.py` | Encoder + button + touch → `NEXT`/`PREV`/`ACT`/`BACK`/`EXIT` |
| `dial_board.py` | Screen size, speaker volume, I2C pins, `make_reader()` |
| `code_link.py` | `CodeLink`, `NativeManager`, `prewarm()`, `HOST_ID`; see "Serving over ESP-NOW" |
| `code_sender.py` | ESP-NOW sender — **PEER of `EspnowModem/host/code_sender.py`** (defines `mac_str_to_bytes()` itself) |
| `card_writer.py` | NDEF text read/write — **PEER of Box** |
| `ws1850s.py` | WS1850S driver — **PEER of Box** (H2 PASS: 0x28, VersionReg 0x15) |
| `json_link.py`, `reset_log.py`, `stats_log.py` | **PEER of Box** |
| `manifest.js` | `DIAL_FILES` / `loadDialFiles()` for ChatBroadcast |
| `boot.py` | M5Stack vendor UIFlow2 boot-option stub |
| `tools/probe_dial.py` | Bench probe: Phase 0 hardware discovery, not part of `DIAL_FILES` |
| `tools/dial_menu_check.py` | Host-side (no hardware) check of the WRITE-menu logic, `_fit()` and `_display_tag()` |

Copied peers differ from the Box originals only by a leading `# PEER: …`
header. `opcodes.py` / `pn532.py` / `nfc_reader.py` are not carried over.

## Serial protocol

Same commands and events as the Box, with these differences:

- `ssid` is always `null` in `armed`, `mode` and the `arm` reply.
- `arm` brings the radio up from the menus (error `no_payload` with no game);
  `disarm` replies `ok` and changes nothing. `mode` is always `WRITE` or `IDLE`.
- `games.list` `pulls` is the number of successful wand pulls of that game
  since boot; the menu crumb shows it for the active game as `Pulled by N`.
- Each finished transfer sends
  `{"type":"pull","slug":s,"role":r,"wand":"<mac>","ok":b,"ms":n,"why":w}`;
  `slug` and `role` are the served game's slug and the requester's `hub`
  (`wand` or `icon_display`). An idle-dropped session has `slug`, `wand` and
  `ms` null and `why` `"idle"`.

Identity payload:

```json
{"type":"identity","device":"broadcast_dial","version":"0.1.0","w":240,"h":240,"nfc":true|false,"host_id":"004c"}
```

**Liveness is `heartbeat`, nothing else.** Never gate the link on `identity`.

## Deploy

Pass `resume` on every `mpremote` call against this board or the first
`fs`/`exec` de-enumerates the USB CDC port (see
`Bag3/Code/HARDWARE_PROTOCOL.md`). Batch work into one invocation, then a
plain `reset` (no `resume`) to bring the new code up.

```bash
ls /dev/cu.usbmodem*
cd Bag3/Code/BroadcastCode/BroadcastDial/BDialFirmware
PORT=/dev/cu.usbmodemXXXX
python3 -m mpremote connect $PORT resume \
  fs cp dial_board.py :/flash/dial_board.py + \
  fs cp dial_input.py :/flash/dial_input.py + \
  fs cp dial_ui.py :/flash/dial_ui.py + \
  fs cp bdial_server.py :/flash/bdial_server.py + \
  fs cp card_writer.py :/flash/card_writer.py + \
  fs cp code_link.py :/flash/code_link.py + \
  fs cp code_sender.py :/flash/code_sender.py + \
  fs cp ws1850s.py :/flash/ws1850s.py + \
  fs cp json_link.py :/flash/json_link.py + \
  fs cp reset_log.py :/flash/reset_log.py + \
  fs cp stats_log.py :/flash/stats_log.py + \
  fs cp main.py :/flash/main.py
python3 -m mpremote connect $PORT reset
```

Or ChatBroadcast's firmware installer, which picks `DIAL_FILES` when identity
reports `broadcast_dial` (defaults to Box when no identity yet).

Every module reachable from `main.py` must be listed in `manifest.js`.

`tools/deploy_dial.py` is an alternative to the batched chain above — one
`mpremote` invocation per file, with a full read-back to verify each write
actually landed:

```bash
python3 tools/deploy_dial.py $PORT
```

It reads the file list from `manifest.js` itself, so it can't drift from
what the batched command or the installer deploy.

`tools/deploy.py` is only for a very stale device or freshly re-flashed blank firmware; for routine updates copy the changed files in one `mpremote` call (HARDWARE_PROTOCOL.md, "Routine updates"). `python3 tools/deploy.py --type dial --changed $PORT` does the same from the shared tool, copying only
files whose on-device sha256 differs.

## Verified vs open

Verified on hardware 2026-10-20 (`docs_and_design/2026-10-20-espnow-serving/RESULTS.md`),
36 KB game to a MockWandEUM wand from a real card:

- SERVE: 2/2 pulls; 2/2 with a host-pinned card (`@004c`).
- WRITE menus (`SHARE_IN_MENUS`): 3/3 pulls, including one after an NFC card write.
- Single state (`c566a21`): `mode` reports `WRITE`, `arm` replies `armed: true`, 3/3 pulls, `games.list` counts them for the active game only.
- `arm`/`disarm` over serial, 20/20 cycles in place.

Open:

- Several wands at once, and the icon-display role on hardware (offline tests only).
- Off-USB (battery) speaker volume check for `SPEAKER_VOLUME` in `dial_board.py`.
- The buzzer was reported as only clicking on 2026-10-20; not yet compared with the
  pre-ESP-NOW firmware.

Static checks done off-device: `python3 -m py_compile` on every `.py`;
`python3 tools/dial_menu_check.py` (menu logic, row truncation, tag display)
green; import graph from `main.py` matches `DIAL_FILES`.
