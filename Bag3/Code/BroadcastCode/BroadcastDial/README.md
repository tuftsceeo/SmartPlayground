# Broadcast Dial firmware (M5 Dial 2 / StampS3A, UIFlow2 MicroPython)

Sibling of `Bag3/Code/BroadcastCode/BroadcastBox/BBoxFirmware/`. Same product — write NFC
cards for a game, then serve that game's code to wands over SoftAP + TCP,
talking to ChatBroadcast over USB serial — on better hardware: a 240×240
round touch LCD, rotary encoder, button, and a built-in NFC reader.

The Dial keeps the Box's mode machine, wire contract, card-safety rules and
serial protocol byte-for-byte. Only the board, the input model and the
screen layer differ. ChatBroadcast accepts both devices from one app.

**Phase 0 (hardware gate) is mostly closed.** `dial_board.py`'s I2C pins
are filled in and the reader is confirmed live (`probe_dial.py` H2/H3:
WS1850S-class chip at `0x28`, `VersionReg` reads `0x15`, over the hardware
`machine.I2C` peripheral — SoftI2C ACKs a bare scan but times out on a real
register read on this bus). Still open: H4 (LVGL servicing during a TCP
transfer), H5 (SoftAP heap headroom with the UI resident — the redesign in
`dial_ui.py` exists to fix an earlier FAIL here; re-run `probe_dial.py`
stage 11 and the real `bdial_server` boot log after any UI change and
update the H5 line in `dial_board.py`), H6/H7. Software pass is P1/P4/P5 of
`.cursor/plans/dial.plan.md`.

## Filesystem

Write all device files to **`/flash`**, not `/`.

## Hardware

| Item | Value | Notes |
|---|---|---|
| Board | M5 Dial 2 (StampS3A) | UIFlow2 MicroPython; assume Dial family bring-up via `M5.begin()` + `m5ui.init()` (H1) |
| Display | LVGL / `m5ui`, 240×240 round | 4 pages built once, re-textured and swapped with `screen_load()` (was 17 — consolidated to fix H5's SoftAP OOM) |
| NFC | WS1850S @ I2C `0x28`, external Grove unit preferred | `dial_board.py`'s `make_reader()` auto-detects: it tries an external Grove RFID2 unit on Port A first (`sda=13 scl=15`, confirmed live 2026-09-22 via `probe_dial.py` stage 4 and a real card test) and falls back to the built-in reader (`sda=11 scl=12`, shares the bus with touch @ `0x38` and RTC @ `0x51`) when nothing acks on Port A. Both are hardware `machine.I2C` (confirmed H2/H3). The built-in reader's read/write was markedly less reliable than the Box's external Grove RFID2 unit despite identical code (`card_writer.py`/`ws1850s.py` are PEER copies, same poll timeouts) -- antenna detuning from sharing the enclosure with the LCD, touch controller, RTC, encoder and speaker, not software, confirmed by wiring the external unit and re-testing |
| Encoder | `hardware.Rotary` | CW/CCW → `NEXT`/`PREV`; magnitude honoured, capped |
| Button | `M5.BtnA` (encoder press) | Short click → `ACT`; hold `SERVE_EXIT_MS` (1000 ms) → `EXIT` |
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

## AP memory order — do not add prints ahead of `arm()`

The SoftAP needs one large **contiguous** block of IDF DRAM and takes it early;
nothing later in boot can un-fragment the heap enough to find it again.
`gc.mem_free()` does not measure this, because MicroPython's GC heap comes out
of the same DRAM — the failure mode is fragmentation, not exhaustion, and it
reads as a healthy free-heap number next to `WiFi Out of Memory`.

``bdial_server.py`` is imported at module scope, so **anything added
to `code_server.py` — a docstring, a format string, a function — is allocated
before `prewarm_ap()` and long before `arm()`**. Diagnostic prints added there
on 2026-09-23 left `idf_largest=7680` against `idf_free=12456` and both Dials
unable to arm until they were power-cycled. Reverting them fixed it.

Rules, in order of how easy they are to break:

1. No new module-scope content in `code_server.py` (or `code_puller.py` on the
   clients). Import-time cost is paid whether or not the code runs.
2. Nothing between `gc.collect()` and `_start_ap()` in `arm()` — the collect is
   what makes the block findable.
3. Diagnostics go in `serve_probe.py`, imported lazily at the end of `arm()`
   behind `DEBUG_SERVE` (default off), so with the flag off it is never parsed.
4. `prewarm_ap()` is required, not an experiment. `PREWARM_AP` exists to A/B it
   deliberately; expect `False` to make `arm()` fail more often.

Full note: [`docs_and_design/2026-09-23-ap-memory-order.md`](../docs_and_design/2026-09-23-ap-memory-order.md)

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
`WRITE` screen's breadcrumb chip reads `Tag Writer` — a positive mode label
rather than the older `pickup off`, which read as an alarm about a normal,
permanent state (WRITE mode always has the AP down). The `DONE` row itself
displays as `Enable Share`; the underlying sentinel is still `DONE`.

## WRITE mode

Two-level menu (groups → tags), same shape as the Box including `W_GROUP`.

| State | Screen | ACT | NEXT/PREV | BACK | EXIT |
|---|---|---|---|---|---|
| `menu` | group list (roller), focused entry centred | open group (or `SERVE` on `DONE`) | scroll | — | — |
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

Leaving `SERVE` is hold-to-`EXIT` **and** a CLOSE touch target — both emit
`EXIT`. The hold is kept deliberately so a stray bump (or stray tap) cannot
drop the AP. Sampled inside `CodeServer.poll()` via `should_abort`.

## SERVE mode concurrency

Both devices serve up to `MAX_CLIENTS` (4) wands at once. The old
single-client `CodeServer` accepted one TCP connection and blocked the
whole main loop until that transfer finished (or timed out at 30s) —
everyone else waited, and one stalled wand stalled the room. Now `poll()`
never blocks: it accepts any pending connections (up to `MAX_CLIENTS`, and
skipping an accept if `gc.mem_free()` is below `MIN_FREE_ACCEPT` — SoftAP
bring-up is this board's known OOM-fragile spot, see H5 above), then
advances every in-flight wand's transfer by one step (`select.select()`
picks the ready sockets) each tick. The wire protocol on the wire is
byte-for-byte the same as before — `MockWand/code_puller.py` and
`IconDisplay/code_puller.py` need no change, and a single wand sees exactly
what it always did.

A device taking the icon leg (a role whose `ROLE_FILES` entry sets `icons`)
walks header → body → ack once for the game file and then once per icon,
all inside the same per-client state machine; `_step_ack()` is what routes
between the two legs. An icon that fails is printed and the leg carries
on — the game is already on the device by then, so a failed picture never
turns a successful pull into a failed one.

Each client resolves its own requested game independently
(`CodeServer._lookup()`), so two wands requesting different games at the
same time can't cross-contaminate each other's transfer — that race
existed in the old single-client code too, it just never had a second
client to race against.

`CodeServer.poll(on_event, should_abort)`'s contract changed to fit:
`on_event` now fires `'serving'` once per accepted wand and `'ok'`/`'fail'`
once per finished wand (a single tick can finish several), and `poll()`
itself returns `'abort'` or `None` rather than a per-transfer result
string. `should_abort()` is sampled once per tick, not once per chunk per
client, since the main loop's own `_input.update()` runs every tick now
(`poll()` no longer blocks it).

`bdial_server.py`'s SERVE screen shows the wand count via
`paint_receiving()`'s existing free-text slot (`"3 Wands"`) — no
`dial_ui.py` change was needed for this.

`BBoxFirmware/code_server.py` carries the same rewrite, and
`bbox_server.py` the same SERVE glue (its abort gesture is the B1 hold
rather than `EXIT`), so the two devices behave identically here.

Verification: `BroadcastBox/tools/devtests/wire_test.py` and
`wire_test_dial.py` run the same cases — in `wire_contract.py` — against
each device's `code_server.py` over a real loopback listener, covering the
v1/v2 request shapes, the icon leg, three concurrent mixed-role pulls, a
refusal alongside live transfers, and an abort mid-transfer.
`tools/pull_bench.py` drives N concurrent pulls against real hardware in
SERVE mode (either device — it joins `SP-FILEPUSH` like a wand does), which
is what the radio and heap behaviour still need.

## Card text / wire contract

Identical to the Box. See `BroadcastBox/BBoxFirmware/README.md`. Plain NDEF
text; Classic writes never touch sector trailers; NTAG writes start at page
4 and stop after 36 pages; `stop_crypto1()` before every re-select.

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
| `dial_ui.py` | 4 LVGL screens (brand palette, roller list) + speaker behind `bbox_ui`'s painter API |
| `dial_input.py` | Encoder + button + touch → `NEXT`/`PREV`/`ACT`/`BACK`/`EXIT` |
| `dial_board.py` | Screen size, speaker volume, I2C pins, `make_reader()` |
| `code_server.py` | SoftAP + TCP file server, multi-client — **PEER of Box** (differs only in heap comments and the Dial-only `prewarm_ap()`); see "SERVE mode concurrency" above |
| `card_writer.py` | NDEF text read/write — **PEER of Box** |
| `ws1850s.py` | WS1850S driver — **PEER of Box** (H2 PASS: 0x28, VersionReg 0x15) |
| `json_link.py`, `reset_log.py`, `stats_log.py` | **PEER of Box** |
| `manifest.js` | `DIAL_FILES` / `loadDialFiles()` for ChatBroadcast |
| `boot.py` | M5Stack vendor UIFlow2 boot-option stub |
| `tools/probe_dial.py` | Bench probe: Phase 0 hardware discovery, not part of `DIAL_FILES` |
| `tools/dial_menu_check.py` | Host-side (no hardware) check of the WRITE-menu logic, `_fit()` and `_display_tag()` |
| `tools/pull_bench.py` | Laptop-side (no hardware needed on the laptop end) CPython bench client: N concurrent pulls against a real Dial **or Box** in SERVE mode, to confirm they overlap instead of queueing — not device firmware, not in `DIAL_FILES` |

Copied peers differ from the Box originals only by a leading `# PEER: …`
header. `opcodes.py` / `pn532.py` / `nfc_reader.py` are not carried over.

## Serial protocol

Same commands and events as the Box. Identity payload:

```json
{"type":"identity","device":"broadcast_dial","version":"0.1.0","w":240,"h":240,"nfc":true|false}
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
  fs cp code_server.py :/flash/code_server.py + \
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

## Verified vs open

Phase 0 bring-up is partly done — **H1 PASS** (UIFlow2, 240×240, Rotary,
`m5ui`, BtnA/BtnB present), **H2 PASS** (WS1850S at `0x28`, VersionReg
`0x15`), **H3 PASS for pins** (`sda=11 scl=12`, on the hardware `machine.I2C`
peripheral). Everything below is still unconfirmed on hardware.

Open / Phase 0–3:

- **H1–H7** in `.cursor/plans/dial.plan.md` — UIFlow2 Dial 2 bring-up, reader
  chip/pins, LVGL servicing during TCP, SoftAP coexistence, radio channel.
- Card writing (P2) and wand round trip (P3) — same bar the Box README records,
  plus the wand pull the Box itself has not yet proven.
- Off-USB (battery) speaker volume check for `SPEAKER_VOLUME` in `dial_board.py`.

Static checks done off-device: `python3 -m py_compile` on every `.py`;
`python3 tools/dial_menu_check.py` (menu logic, row truncation, tag display)
green; import graph from `main.py` matches `DIAL_FILES`.
