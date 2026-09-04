# Working with the Box and wand hardware — protocol for an agent session

Read this before opening a serial port or flashing anything in
`Bag3/Code/BroadcastBox/`.

Originally written from a bench session on 2026-09-02; rewritten 2026-09-04
after the multi-game library landed on both devices. Most rules below exist
because ignoring them cost a hardware cycle, and a hardware cycle costs a
reset plus a >20 s boot plus a person's attention.

**Treat every other `.md` in this tree as stale until proven otherwise.**
Verify behaviour from code, or from a log you just captured.

## The two hard rules

**1. Ask which board is on which port. Never guess, never infer.**

The Box (M5Stack StickS3) and the wand (Xiao ESP32-C6) enumerate as sibling
names — `/dev/cu.usbmodem3101` and `/dev/cu.usbmodem1101` in one session,
different numbers in the next. `ls /dev/cu.usbmodem*` tells you two ports
exist, not which is which. Hitting the wrong one at best wastes a trial and
at worst resets a board mid-measurement.

Any port name written in a document, **this one included**, is an example
from a past session, not a fixture.

**2. Ask before opening a port and wait for an explicit answer.**

The user connects to these boards to watch results, and ChatBroadcast holds
the Box's port over WebSerial whenever it is connected. One process at a
time. This applies to "just a quick read" too.

## You cannot see the screen or press the buttons

Every physical observation comes from the user. This shapes how you work:

- **The user is not watching your terminal, and does not always have this
  window open.** They read messages later, in a batch, on their own time.
  Never assume a reply is imminent, and never treat a background-task
  notification (a capture window closing, a timer elapsing) as the user
  having done anything — it is a system event, not their input.
- **Instructions, then STOP, then wait for an explicit "start"/"ready"/"go"
  from the user before touching hardware.** Do not start a capture, open a
  port, run `mpremote`, or take any other hardware-facing action in the same
  turn as the instructions. Give the numbered physical steps, state plainly
  that you are waiting, and take no tool action until the user says to go.
- Put the action item **first**, at the top of the turn, in one line. Do not
  bury it in a longer message — the user may not read past the first line.
- **Use long capture windows** (~15 min) so timing does not matter once
  started.
- **Never report that something works.** You did not see it. Report what the
  log shows and let the user confirm the device behaved. Words like "fixed"
  and "working" belong to them, not you.
- Design tests as short numbered physical steps: which button, what to expect
  on screen, what to report back.

## Driving the boards without a person

Much of the system can be exercised from the host, which saves the user's
attention for the things that genuinely need fingers.

**Can be driven from the host:**

- Any Box behaviour reachable by a JSON command — mode changes, the game
  library, stats. Write newline-delimited JSON straight to the CDC port; do
  **not** use `mpremote exec`, which stops `main.py`. A ~25-line pyserial
  script that opens the port, writes `{"cmd":...}` lines and echoes replies is
  enough, and is what ChatBroadcast does over WebSerial.
- The whole wand pull path, by setting the flag the tap would have set:
  `pull_flag.set_pending('<slug>')` then `machine.reset()`.
- Tag-text parsing, by calling `NfcReader._match_prefixed()` / `is_valid_slug()`
  on-device against synthetic strings.

**Still needs a person:** reading a real card, writing a card (Box WRITE
mode), and anything judged by the screen, the LEDs or the buzzer.

Say which of the two you are doing. A faked tap does not exercise the NDEF
decode path, and reporting it as though it did is the failure mode to avoid.

## mpremote: the traps

| Trap | Consequence | Do instead |
|---|---|---|
| `mpremote ... exec` on a running board | Enters the raw REPL, sends Ctrl-C, **stops `main.py`'s loop**. It does not restart until the next reset. Your "quick check" killed the server. | Use `tools/serial_monitor.py` to observe, or the JSON driver above. Only `exec` when you intend to stop the program — then `reset` afterwards. |
| Several `mpremote` invocations in a row | Each is a reset plus a >20 s boot | Chain with `+` into **one** invocation |
| Opening the port right after a `reset` | The CDC device de-enumerates; `/dev/cu.*` literally disappears for several seconds. Plain `serial.Serial()` fails instantly with `Errno 2`/`Errno 6`. | Wait, or use a monitor that retries on drop |
| Leaving the board at the REPL after an `exec` | Box sits dead with no firmware running; the user sees a frozen screen | Always finish with `reset` |
| `timeout 20 ...` | Not present on macOS | Pass a duration to the tool itself, or use `run_in_background` |
| `sys.path` read under `exec` | Shows `['', '.frozen', '/lib']` — **not** what the firmware runs with, because `exec` bypasses `main.py`, which appends `/games` | Judge import paths from a real boot log, not from `exec` |

Batched deploy, one reset:

```bash
PORT=/dev/cu.usbmodemXXXX   # ask first
python3 -m mpremote connect $PORT \
  fs cp bbox_server.py :/flash/bbox_server.py + \
  fs cp bbox_ui.py :/flash/bbox_ui.py + \
  reset
```

`mpremote` is available as `python3 -m mpremote` (there is no `mpremote`
binary on PATH here).

## Verify a constructed command before firing it at hardware

**The shell here is `zsh`, not `bash`.** Bash array idioms fail *quietly*.
`unset 'ARGS[${#ARGS[@]}-1]'` did not remove the element it was meant to and
left an empty string in the middle of the argument list — producing a command
that copied 14 of 15 files and then errored, which cost an extra reset.

Print a constructed argument list and read it before sending it to a board.
It is free; a hardware cycle is not.

**Use absolute paths.** The working directory is not guaranteed to persist
between commands in an agent session; a relative path that worked a moment
ago can resolve somewhere else and fail *after* the board has already been
reset, losing the log you meant to capture.

## Watching a running board

```bash
python3 tools/serial_monitor.py /dev/cu.usbmodemXXXX 900 > run.log
```

Run it in the background, tell the user to go, then read `run.log`. Filter
the noise when reading — the wand's `memprobe` GC dumps are ~40 lines a boot:

```bash
grep -vE "^\[ *[0-9.]+s\] (0000|GC:|stack:|MEM|MEMFRAG| No\. of)" run.log
```

A dropped port mid-log is usually a board reset, and that is itself a finding.
But check first that **you** are not holding it: a background capture or JSON
driver still running presents as
`device reports readiness to read but returned no data (device disconnected or
multiple access on port?)`, which reads exactly like a reset. `pgrep -f` your
own scripts before concluding the hardware did something.

## Instrument before theorizing

The reader bug ("only the first scan per boot works") was found by adding
prints, not by reading code. Two rounds of plausible hypotheses went nowhere;
one round of logging showed the mechanism outright.

When a symptom is unexplained, add logging that reports **state at the moment
of failure** — not just "it failed". The line that solved it was
`reselect FAILED (crypto=True ant=True)`: the two register bits, printed next
to the failure.

Then remove or gate the instrumentation. Verbose logging drowns the signal.

## Logging conventions in this firmware

`bbox_server.py`, `card_writer.py` and `bbox_ui.py` each carry a module-level
`VERBOSE = False`.

- `_log()` prints only when `reset_log.LOG_ENABLED` is true; `_dbg()` only when
  the module's own `VERBOSE` is true. **Both are currently off**, so card
  detect/write tracing is silent by default. Turn `LOG_ENABLED` on in
  `reset_log.py` when you need that trace, and turn it back off before
  finishing.
- **Failures are never gated.** Every abort prints its reason, every exception
  prints, every write outcome prints. The standing requirement is zero silent
  failures.
- Serial output is `print()` to USB CDC. It is not stored and is discarded if
  no host is listening.

## Persistent logs on the Box

Two separate flash logs, with different switches — do not conflate them.

`reset_log.py` → `/flash/resetlog.txt` (40 lines). Records the reset cause,
because the board's native-CDC USB drops the port on reset and any panic goes
into a port the host has already lost — the cause can only be read on the
*next* boot. `note_mode()` persists the mode to `/flash/lastmode.txt`, so each
line names the mode before the reset:

```
2906 HARD was:SERVE
```

**Gated by `reset_log.LOG_ENABLED`, which is `False`.** An empty reset log is
the expected state, not evidence of a clean run.

`stats_log.py` → `/flash/stats.log` (200 lines) plus `/flash/stats_since.txt`.
Product data, **never gated** — it must keep accruing with debug logging off.

```
<ticks> pull <slug> ok|fail
<ticks> tag  <label> ok
```

`aggregate()` returns `{pulls:{slug:n}, writes:{label:n}, since:<ticks>}`.
Written from `code_server.poll()` (every completed serve, attributed to the
**requested** slug) and from the card-write success branch in `bbox_server.py`.

The Box screen reads this at boot via `_load_stats()` and then counts in
memory, so the WRITE tag list and the SERVE "pickups" line show **cumulative
totals across all boots**, not a session tally. `stats.reset` zeroes both the
log and the in-memory counters.

Read either with one batched `exec`, then `reset`:

```bash
python3 -m mpremote connect $PORT exec "
import reset_log
for l in reset_log.last(8): print(l)
" && python3 -m mpremote connect $PORT reset
```

Causes seen so far: `PWRON` (power cycle — including a bumped cable or the
reset button, which is easy to hit while handling the board) and `HARD` (an
`mpremote reset`). A `BROWNOUT` or `WDT` would be a real finding; neither has
appeared. **A reset seen during hands-on testing is not by itself evidence of
a fault** — read the cause before treating it as one.

## The wand tree is no longer frozen

`MockWand/main.py`, `code_puller.py` and `pull_flag.py` were frozen for a long
period after a 4/4 field test. That freeze ended when the multi-game library
landed; all three now carry slug-aware changes, along with
`lib/nfc_reader.py` and a new `lib/game_store.py`.

What is still load-bearing, and must survive any future edit:

- **The pull-flag check is `main()`'s first statement.** A pull must happen
  before `ESPNowManager` is ever constructed.
- **No ESP-NOW in the pull path.** A WiFi join only succeeds on a radio
  ESP-NOW has never touched this boot (measured 3/3 failures otherwise).
- **`machine.reset()` between radio modes.** The tap queues the pull and
  resets; the pull succeeds and resets again.
- **The attempt budget is spent before each attempt** (`pull_flag.bump()`), so
  a crash mid-pull cannot boot-loop.

On-device layout: `/lib` for libraries, flash root for `main.py` and the
built-in games, `/games/<slug>.py` for pulled games. `/games` is appended to
`sys.path` by `main.py`. Pulled games must never land in the root — the root
precedes `/games` on the path and would shadow the new copy with a stale one.

## The Box ↔ wand wire contract

SSID `SP-FILEPUSH`, password `playground1`, port 8266, channel 1, 512-byte
chunks with a 20 ms yield.

**The wand speaks first** (changed 2026-09-04; it used to be server-push):

```
wand -> box :  1 byte len | <len> bytes UTF-8 slug     (len 0 = "serve active")
box  -> wand:  size(4B BE) | sha256(32B) | name_len(1B) | name
box  -> wand:  file body, 512B chunks
wand -> box :  2-byte ack, b'OK' or b'NO'
```

A `size` of **0** is an explicit refusal — the Box has no such game. The wand
treats it as terminal, clears its flag and does not spend a retry.

Destination name is `<slug>.py`, saved to `/games/<slug>.py` on the wand.
Card text is `getcode:<slug>` (pull that game) and a bare `<slug>` (play the
local copy), plus `DONE` as a Box-UI sentinel that never reaches a card.

The protocol is **hand-duplicated** in `BBoxFirmware/code_server.py` and
`MockWand/code_puller.py` — different devices, no shared module. Both carry a
`PEER:` comment. Change them in the same commit or the wand breaks silently.

## Slugs are module names

A slug is the filename on both devices *and* a MicroPython module name, since
`_load_play()` does `__import__(slug)`. It must be a legal identifier:
lowercase, leading letter, `[a-z0-9_]`, max 16 chars. **Hyphens are invalid** —
they were the original format and any surviving hyphenated game must be
renamed on flash along with its `index.json` key.

Three places enforce this and must agree:

- `ChatBroadcast/js/gameName.js` — `slugify()` / `isValidSlug()`, plus the
  reserved list (Python keywords, module names, wand built-in game tags).
- `MockWand/lib/nfc_reader.py` — `is_valid_slug()`, what a card may say.
- `MockWand/lib/game_store.py` — what is allowed on flash.

## NFC card safety

Two things protect the cards. Do not "simplify" either away:

- Classic writes only ever address `sector*4 + {0,1,2}` for sectors 1–15.
  Sector trailers (`sector*4 + 3`) hold the keys and access bits; writing one
  with the wrong value locks the sector permanently. Sector 0 (the UID) is
  excluded too.
- NTAG writes start at page 4 and stop after 36 pages, staying below the
  NTAG21x config and password pages.

A *failed* authentication does not modify a card — it only wedges the reader.

Also: any MIFARE auth latches the reader's `MFCrypto1On` bit, and while it is
set the reader cannot answer a plain `REQA`, so detection silently finds
nothing. Toggling the antenna does **not** clear it. `stop_crypto1()` is
required before every re-select. This caused the one-scan-per-boot symptom.

Cards carry **plain NDEF text**, not the 4-byte opcode scheme in `opcodes.py`.
That scheme is still used for ESP-NOW game names; `MockWand/lib/nfc_reader.py`
does not consult it. `card_writer.py` keeps a hand-copied `_decode_ndef_text`
mirroring the wand's — keep the two in sync.

## Before you touch the Box at all

`BBoxFirmware/manifest.js` lists what ChatBroadcast's installer pushes. Every
module reachable from `main.py` must be in it — a missing one is an
`ImportError` at boot and a `fatal` JSON, which looks like a bricked box to a
teacher.

Check it mechanically: walk the import graph from `main.py` and compare
against `BOX_FILES`. Note that `boot.py` is deliberately absent, and game
files are pushed separately to `/flash/games/<slug>.py` by
`boxFirmwareInstaller.js`.

## A reasonable session shape

1. Ask which port is which; ask that nothing else holds them.
2. Read the code before changing it. Ask what is actually broken rather than
   auditing for theoretical faults — several things flagged from reading
   turned out not to matter on real hardware, and the real bug was not among
   them.
3. Make one change at a time. Flash in one batched `mpremote` call.
4. Drive from the host whatever can be driven; reserve the user's attention
   for cards, buttons and screens. Say which kind of evidence you have.
5. Tell the user the capture is about to start and what physical action to
   take, **stop, and wait for them to say start/ready/go.**
6. Read the log. Report what it shows, not what you hope it shows.
7. Gate the instrumentation before calling anything done.
8. Offer to commit while the build is known good.
