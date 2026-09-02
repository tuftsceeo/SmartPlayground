---
title: "Phase A — Box power modes (radio/NFC mutual exclusion)"
description: >
  Make the Broadcast Box explicitly modal so the SoftAP and the NFC RF field
  are never energized simultaneously. Box firmware only; the wand's validated
  ESP-NOW/WiFi sequence is not touched.
status: draft
created: 2026-09-02
branch: claude/broadcast-box-exploration-7f9qs8
scope: Bag3/Code/BroadcastBox/BBoxFirmware
phase: A
risk: medium
hardware_required: true
guardrails:
  - "MockWand/ must be byte-identical at the end of this round"
  - "Box-side wire contract (SSID/PWD/port/channel/header/ack) is frozen"
  - "Card text stays exactly 'getcode' and 'jumpin' — the wand matches by exact set membership"
todos:
  - id: T1
    title: "Bench probe: does AP down/up survive repeat cycles in one boot?"
    status: pending
    parallel: true
    depends_on: []
    owner: subagent
    files: ["BBoxFirmware/probe_ap_cycle.py"]
    gates: ["T6"]
  - id: T2
    title: "reset_log.py — persist reset_cause across the USB CDC drop"
    status: pending
    parallel: true
    depends_on: []
    owner: subagent
    files: ["BBoxFirmware/reset_log.py"]
  - id: T3
    title: "code_server.py — abortable serve, reachable 'serving', settle delay, pickup count"
    status: pending
    parallel: true
    depends_on: []
    owner: subagent
    files: ["BBoxFirmware/code_server.py"]
  - id: T4
    title: "bbox_ui.py — tag-list, serve and mode-change screens"
    status: pending
    parallel: true
    depends_on: []
    owner: subagent
    files: ["BBoxFirmware/bbox_ui.py"]
  - id: T5
    title: "Two-button input layer — B1/B2 edge + hold timing"
    status: pending
    parallel: true
    depends_on: []
    owner: subagent
    files: ["BBoxFirmware/buttons.py"]
  - id: T6
    title: "bbox_server.py — the mode machine (integration)"
    status: pending
    parallel: false
    depends_on: ["T2", "T3", "T4", "T5"]
    owner: lead
    files: ["BBoxFirmware/bbox_server.py"]
  - id: T7
    title: "manifest.js + README — deploy list and hardware/mode documentation"
    status: pending
    parallel: true
    depends_on: []
    owner: subagent
    files: ["BBoxFirmware/manifest.js", "BBoxFirmware/README.md"]
  - id: T8
    title: "Guardrail audit — wand tree untouched, wire contract unchanged"
    status: pending
    parallel: false
    depends_on: ["T6"]
    owner: lead
    files: []
---

# Phase A — Box power modes

## Context

The Box browns out on USB because the SoftAP and the NFC reader are both live
whenever a game is on flash: `BboxServer.run()` calls `_try_arm()`
unconditionally, and `_try_arm()` raises the AP *and* enables card writing
together (`bbox_server.py:_try_arm`, `code_server.py:_start_ap`). The WS1850S
swap (~30 mA burst vs the PN532's ~150 mA) and the G11 field gate lowered the
peaks without removing the overlap. Field observation on 2026-09-01: unplugging
the reader entirely took the box from a 30 s–2 min reset cycle to 73 s+ clean
uptime, but that test removes the I2C path and the RF draw together, so it does
not separate H1 (brownout) from H2 (SoftI2C stall) — see `known_issue.md`.

Phase A makes the Box modal so that **at most one of {WiFi AP, NFC RF field} is
energized at any instant**, and adds the reset-cause logging that finally
discriminates H1 from H2. Box firmware only.

## Evaluation of the FSM outline — what changed

Reviewing `design/2026-09-01-power-modes-and-fsm.md` against the code turned up
five things the outline got wrong or left implicit:

1. **"Hold B1 to leave SERVE" is unreachable during a transfer.**
   `CodeServer.poll()` serves the whole file synchronously — up to
   `SOCK_REPLY_TIMEOUT_S = 30` — and nothing else in the loop runs meanwhile.
   Fixed here by an abort callback sampled between chunks (T3), which also
   makes the existing per-chunk `sleep_ms(YIELD_MS)` the natural hook.
2. **AP down/up within one boot is unvalidated on this hardware.** This is the
   same class of operation that cost the wand three days. Gated behind a
   standalone probe (T1) before the mode machine is allowed to depend on it.
   Per the hardware note: the first `tags → wifi` transition is a fresh boot and
   is safe regardless; only a repeat cycle without a reboot is at risk.
3. **Phase A changes field behavior.** A box carried to the playground no longer
   auto-serves — it boots into `WRITE`. A wand tapping `getcode` while the box
   is in `WRITE` burns two boots (~31 s each) and shows its error blink. This is
   intended, but the Box UI has to say so plainly, and the deploy note has to
   call it out.
4. **The hybrid dispatch precedence in the outline is backwards** (Phase B, but
   recording it now): built-ins-first would mean a teacher's re-pulled `melody`
   never runs, because the built-in wins. Pulled games must take precedence.
5. **Card text cannot change yet.** The outline's `getcode:<name>` format needs
   the wand to prefix-parse; the wand is frozen this round, so Phase A's tag
   list uses only text today's wand already matches by exact set membership:
   `getcode` and `jumpin`. The format swap lands with the wand change in Phase B.

## GUARDRAIL — the radio contract (read before writing any code)

The wand's ESP-NOW → WiFi handling is hardware-validated (4/4 field test,
commits `cfed7a4` and `c6f0716`) and is **out of scope this round**.

**Files that must be byte-identical when this round ends:**

```
Bag3/Code/BroadcastBox/MockWand/main.py
Bag3/Code/BroadcastBox/MockWand/code_puller.py
Bag3/Code/BroadcastBox/MockWand/pull_flag.py
Bag3/Code/BroadcastBox/MockWand/lib/espnow_manager.py
```

No task below has a reason to open them except to read. The sequence they
encode, for reference — do not "simplify" any of it later:

- `main()` checks `pull_flag.is_pending()` as its **first statement**, before
  `_boot_grace()` and before `ESPNowManager` is ever constructed (`main.py:432`).
- `_run_pull_mode()` must touch no ESP-NOW. `pull()` is called **without**
  `enow=`, which deliberately keeps `_shutdown_espnow()` out of the path
  (`main.py:402-404`).
- A failed pull leaves the flag set and calls `machine.reset()` — the retry
  needs a cold radio too (`main.py:417-424`). Attempts are bumped *before* the
  try so a mid-pull crash cannot boot-loop.
- Antenna pins (GPIO 3 enable / GPIO 14 select) are owned by
  `espnow_manager.EXTERNAL_ANTENNA`; `code_puller` imports it rather than
  defining its own, and sets both directions explicitly.
- `_reset_sta()` cycles the interface fully per join attempt; `JOIN_ATTEMPTS=2`,
  `CONNECT_TIMEOUT_S=15`, `RADIO_SETTLE_MS=300`.

**The Box owns the other half of that contract. These are frozen in Phase A:**

| Item | Value | Where |
|---|---|---|
| SSID / password | `SP-FILEPUSH` / `playground1` | `code_server.py:19-20` |
| Port | `8266` | `code_server.py:21` |
| AP channel | `1` — an idle ESP-NOW radio sits here, so the wand never changes channel to join | `code_server.py:22` |
| AP power save | `ap.config(pm=0)` | `code_server.py:65` |
| Header | `size(4B big-endian) | sha256(32B) | name_len(1B) | name` | `code_server.py:174-177` |
| Dest name | `jumpin.py` | `code_server.py:DEFAULT_DEST` |
| Chunk / yield | `512` / `sleep_ms(20)` | `code_server.py:23-24` |
| Ack | client writes `OK` / `NO`, 2 bytes, after promote | `code_server.py:187-188` |
| Card text | exactly `getcode`, `jumpin` | `card_writer.py`, plain NDEF text |

Changing any row breaks the wand silently. T3 touches this file — it adds an
abort path and a counter, and changes nothing in the table.

## Frozen interfaces

Tasks are parallel because these signatures are fixed up front. Write against
them; do not negotiate them mid-task.

```python
# buttons.py (new, T5)
B1_PIN = 11          # G11 "Key1" — scan / write / confirm
B2_PIN = 12          # G12 "Key2" — scroll
class Buttons:
    def __init__(self, b1_pin=B1_PIN, b2_pin=B2_PIN): ...
    def update(self): ...                 # call once per loop; samples both pins
    def b1_down(self) -> bool: ...        # level, debounced
    def b1_held_ms(self) -> int: ...      # 0 when up
    def b2_pressed(self) -> bool: ...     # rising-edge, one-shot per press
    def available(self) -> bool: ...      # False if Pin construction failed

# reset_log.py (new, T2)
PATH = '/flash/resetlog.txt'
MAX_LINES = 40
def record(note=""): ...                  # append one line at boot; never raises
def last(n=5) -> list: ...                # newest-first
def cause_name(c) -> str: ...             # 'BROWNOUT'/'WDT'/'PWRON'/'SOFT'/'DEEPSLEEP'/'?<n>'

# code_server.py (T3) — additions only
AP_SETTLE_MS = 300                        # same value the wand uses post-cycle
class CodeServer:
    def poll(self, on_event=None, should_abort=None): ...
        # on_event('serving') fires BEFORE the blocking serve, making the
        # currently-unreachable 'serving' branch reachable.
        # should_abort() is sampled between chunks; True -> close, return 'abort'.
    @property
    def pickups(self) -> int: ...         # completed successful serves this session

# bbox_ui.py (T4) — additions only; existing paint_* keep their signatures
def paint_tag_list(self, entries, cursor, written): ...   # written: dict name->count
def paint_serve(self, ssid, pickups=0): ...
def paint_mode_change(self, to_mode): ...
def paint_no_pickup_hint(self): ...       # shown in WRITE: "pickup off — DONE + B1"
```

## Mode machine (T6, lead)

```
BOOT ─ reset_log.record() ─ UI ─ WS1850S init (antenna OFF) ─ buttons ─ hello
  └─ game on flash?  no → IDLE          yes → WRITE        (AP stays DOWN)

WRITE   AP off. NFC field on only while B1 down.
        TAG_LIST = ["getcode", "jumpin", DONE]
        B2 press                → cursor++ (wraps)
        B1 press on DONE        → SERVE
        B1 down elsewhere       → field on, poll; card seen:
            text == entry       → ALREADY_OK (beep, no write)
            blank               → WRITING
            other text          → OVERWRITE prompt at B1_PROMPT_MS (500)
                                  still held at B1_CONFIRM_MS (1500) → WRITING
                                  released before                    → cancel
        B1 up                   → antenna_off()

SERVE   NFC antenna off, no I2C polling at all. AP up.
        code.poll(on_event=…, should_abort=b1_held >= SERVE_EXIT_MS(1000))
        abort or hold → disarm(), AP_SETTLE_MS, → WRITE

any     app push → RECEIVING (AP down first if in SERVE) → WRITE
```

Constants land in `bbox_server.py`: `B1_PROMPT_MS=500`, `B1_CONFIRM_MS=1500`,
`SERVE_EXIT_MS=1000`, `TAG_LIST=("getcode", "jumpin")`.

`_try_arm()` loses its AP responsibility: a game on flash means *ready to write
tags*, not *broadcasting*. Off-USB operation still works — it starts in `WRITE`.

## Tasks

### T1 — AP-cycle probe (subagent, no dependencies)

New `BBoxFirmware/probe_ap_cycle.py`, modeled on the existing `probe_stick.py`
(same `_result("key", value, ok)` RESULT-line convention). Standalone; run from
the REPL, prints to serial **and** paints pass/fail on the LCD, because the Box
is normally observed only by its screen.

Per cycle, N=10: `_start_ap()` → bind/listen on 8266 → close → `ap.active(False)`
→ `sleep_ms(AP_SETTLE_MS)` → assert `ap.active()` went False → next. Record for
each cycle whether the AP re-activated, whether the socket bound, and elapsed
ms. Final line: `RESULT ap_cycle=<n_ok>/10`.

Reuse `code_server._start_ap()` rather than re-implementing AP setup — the
channel/pm settings are part of the frozen contract.

**Acceptance:** runs standalone on a StickS3 with no other firmware active;
never leaves the AP up on exit; a failure at cycle k reports k rather than
throwing.

**This task gates T6's mode-switch mechanism.** 10/10 → in-place cycling as
specced. Any failure → T6 instead writes a mode flag to flash and
`machine.reset()`s into the new mode (the wand's proven bracket), and the plan's
UX cost is a >20 s boot per switch.

### T2 — reset_log.py (subagent, no dependencies)

New `BBoxFirmware/reset_log.py` implementing the frozen interface. `record()` is
called once at boot from `run()`; it reads `machine.reset_cause()`, maps it via
`cause_name()`, appends `<epoch-ish ticks> <cause> <note>`, and trims the file
to `MAX_LINES`. Must never raise — a full or read-only filesystem degrades to a
printed warning.

Why it exists: the board's USB is native CDC, so a reset drops the port and any
panic message goes into a port the host already lost. Reset cause has to be read
on the *next* boot. This is discriminating test 1 in `known_issue.md`.

**Acceptance:** import + `record()` + `last()` round-trips on device; file stays
≤ MAX_LINES over 50 calls; a deliberately bad PATH prints and returns cleanly.

### T3 — code_server.py (subagent, no dependencies)

Additions only, to the interface above:
- `poll(on_event=None, should_abort=None)`. Fire `on_event('serving')` before
  `_serve_client()`; sample `should_abort()` inside the chunk loop next to the
  existing `sleep_ms(YIELD_MS)`; on abort close the client and return `'abort'`.
- `pickups` counter, incremented on a successful serve.
- `AP_SETTLE_MS = 300` and a `sleep_ms(AP_SETTLE_MS)` at the end of `disarm()`
  after `ap.active(False)`.

**Do not change** anything in the frozen-contract table: not the header layout,
not the ack, not chunking, not the AP config sequence in `_start_ap()`.

Note on abort semantics for the docstring: an aborted transfer is safe on the
wand — it sees a short read / hash mismatch, removes its `.part`, does not
promote, and retries within its budget.

**Acceptance:** existing call site `self.code.poll()` still works with no
arguments (both new params default to `None`); `python3 -c "import ast; ..."`
parses; no import of anything not already imported.

### T4 — bbox_ui.py (subagent, no dependencies)

Add the four screens in the frozen interface. Follow the file's existing
conventions exactly: `_draw_lines()` / `_draw_centered()`, only DejaVu sizes
from `_DEJAVU_NAMES` (9/12/18/24/40 — 14 is not valid), every M5 call already
wrapped, `setTextSize()` never touched outside `begin()`.

- `paint_tag_list(entries, cursor, written)` — the scrollable list; mark the
  cursor row, show `written[name]` counts, render the `DONE` row distinctly.
  240×135 landscape fits ~4 rows at size 12; truncate rather than overflow.
- `paint_serve(ssid, pickups)` — SSID, pickup count, and the exit affordance
  ("hold B1 to write tags").
- `paint_mode_change(to_mode)` — transient screen so a mode switch is not a
  blank pause.
- `paint_no_pickup_hint()` — the WRITE-mode line telling the teacher wands
  cannot pick up code right now (see evaluation item 3).

Extend `demo()` with the new screens so they can be eyeballed without the
server. **Acceptance:** `demo()` cycles all screens on hardware; no new
top-level imports.

### T5 — buttons.py (subagent, no dependencies)

New `BBoxFirmware/buttons.py` implementing the frozen interface: both pins
`Pin.IN, Pin.PULL_UP`, active-low, ~20 ms debounce, `b1_held_ms()` measured from
the debounced press edge with `time.ticks_diff`, `b2_pressed()` a one-shot
rising edge cleared on read. `available()` returns False if `Pin` construction
throws, and every accessor then degrades safely (`b1_down()` False,
`b2_pressed()` False).

This supersedes the ad-hoc `_nfc_trigger` Pin in `bbox_server.py` — T6 deletes
that and uses this. Do not edit `bbox_server.py` yourself.

**Acceptance:** parses; a bench script pressing each key prints the expected
edges and hold durations; no dependency on `M5`.

### T6 — bbox_server.py mode machine (lead, after T2–T5)

The integration task, taken by the lead because it touches every interlock in
the file: `_try_arm()`'s meaning, the `_poll_nfc()` failure/re-init counter
(`NFC_REINIT_AFTER`), the debounce (`_last_seen_uid`), the JSON event surface,
and the boot ordering that `known_issue.md` documents.

Specific points beyond the state diagram:
- In `SERVE`, `_poll_nfc()` returns immediately without any I2C — not merely
  with the antenna off. H2 (SoftI2C stall) is unresolved; no reason to touch the
  bus while the radio is up.
- Replace `self._nfc_trigger` with `Buttons`; keep the fail-open behavior
  (`available()` False ⇒ treat B1 as held, so a box with dead side keys still
  writes cards).
- `hello` currently reports `"nfc": true` unconditionally even when
  `_init_nfc()` raised (defect logged in `known_issue.md`); report the real
  result. The app needs nothing else — connected/not is the whole app-side
  contract this round.
- Call `reset_log.record()` early in `run()`, before the boot grace.
- Mode is *not* exposed as a new JSON event type in Phase A.

### T7 — manifest.js + README (subagent, no dependencies)

`manifest.js`: add `buttons.py` and `reset_log.py` to `BOX_FILES` (leave
`probe_ap_cycle.py` out — it is a bench tool, not firmware). README: replace the
hardware-table button row with B1=G11 / B2=G12 and their gestures, document the
three modes and the mutual-exclusion invariant, and state plainly that the box
no longer serves code until a teacher selects DONE + B1. Describe current
behavior only — no history, no claims about power results that have not been
measured.

### T8 — guardrail audit (lead, last)

`git diff --stat HEAD -- Bag3/Code/BroadcastBox/MockWand/` must be empty. Diff
`code_server.py` against the frozen-contract table row by row. Confirm
`TAG_LIST` contains only strings in the wand's `ALL_COMMANDS`
(`getcode` ∈ `BROADCAST`, `jumpin` ∈ `GAME_TAGS`).

## Verification (hardware, in order)

Serial etiquette from `REBOOT_PULL_PLAN.md` applies: ask before opening any
port, and the wand is the only board with serial access.

1. **T1 probe alone.** 10/10 → proceed with in-place cycling. Otherwise switch
   T6 to reboot-on-mode-change before going further.
2. **Screens.** `bbox_ui.demo()` — all new screens legible at 240×135.
3. **WRITE mode, 10 min on USB.** Box armed, B1 tapped occasionally to write.
   Then read `reset_log.last()`. Any reset with `BROWNOUT`/`PWRON` here is H1
   surviving the mode split; `WDT` is H2.
4. **SERVE mode, 10 min on USB.** Same reading. A reset in one mode but not the
   other is the measurement that unplugging the reader could not produce.
5. **Round trip.** Write `getcode` + `jumpin` cards in WRITE → DONE + B1 →
   SERVE → real wand taps `getcode` → wand reboots, pulls on a cold radio,
   reboots into the game. This is the end-to-end proof the wand path is intact.
6. **Exit under load.** Hold B1 during a transfer; box returns to WRITE, wand
   retries within budget and succeeds on the next attempt.
7. **Repeat cycle.** WRITE → SERVE → WRITE → SERVE without a reboot, then a wand
   pull on the second SERVE. This is the case T1 predicts; confirm the
   prediction on the real path.

## Out of scope this round

Named games and `/flash/games/`, the `GET <name>` protocol, `getcode:<name>`
card text, wand dynamic dispatch, any ChatApp change beyond nothing, and the
`SERVE` idle timeout. All of it waits for Phase A hardware time.
