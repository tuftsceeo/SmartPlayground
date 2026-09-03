# Working with the Box and wand hardware — protocol for an agent session

Read this before opening a serial port or flashing anything in
`Bag3/Code/BroadcastBox/`.

Written from a bench session on 2026-09-02. Most of the rules below exist
because ignoring them cost a hardware cycle, and a hardware cycle costs a
reset plus a >20 s boot plus a person's attention.

This consolidates the etiquette sections previously scattered in
`REBOOT_PULL_PLAN.md` and `design/phase-a-handoff.md`. Where those disagree
with this, this is newer.

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

- **Say when it is time to act, then wait.** The user is not watching your
  terminal. Starting a capture and describing the test in the same message
  means the window expires while they read it. Signal clearly, give numbered
  steps, and stop until they reply.
- **Use long capture windows** (~15 min) so timing does not matter.
- **Never report that something works.** You did not see it. Report what the
  log shows and let the user confirm the device behaved. Words like "fixed"
  and "working" belong to them, not you.
- Design tests as short numbered physical steps: which button, what to expect
  on screen, what to report back.

## mpremote: the traps

| Trap | Consequence | Do instead |
|---|---|---|
| `mpremote ... exec` on a running board | Enters the raw REPL, sends Ctrl-C, **stops `main.py`'s loop**. It does not restart until the next reset. Your "quick check" killed the server. | Use `tools/serial_monitor.py` to observe. Only `exec` when you intend to stop the program — then `reset` afterwards. |
| Several `mpremote` invocations in a row | Each is a reset plus a >20 s boot | Chain with `+` into **one** invocation (see below) |
| Opening the port right after a `reset` | The CDC device de-enumerates; `/dev/cu.*` literally disappears for several seconds. Plain `serial.Serial()` fails instantly with `Errno 2`/`Errno 6`. | Wait, or use a monitor that retries on drop |
| Leaving the board at the REPL after an `exec` | Box sits dead with no firmware running; the user sees a frozen screen | Always finish with `reset` |
| `timeout 20 ...` | Not present on macOS | Pass a duration to the tool itself, or use `run_in_background` |

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
that copied 14 of 15 files and then errored, which cost an extra reset to
repair.

Print a constructed argument list and read it before sending it to a board.
It is free; a hardware cycle is not.

```bash
for a in "${ARGS[@]}"; do echo "[$a]"; done
```

## Watching a running board

```bash
python3 tools/serial_monitor.py /dev/cu.usbmodemXXXX 900 > run.log
```

Run it in the background, tell the user to go, then read `run.log`. Filter
the noise when reading:

```bash
grep -v "font DejaVu\|heartbeat\|monitor:" run.log
```

A dropped port mid-log is not a tool failure — it means **the board reset**.
That is itself a finding; note when it happened relative to what the user was
doing.

## Instrument before theorizing

The reader bug this session ("only the first scan per boot works") was found
by adding prints, not by reading code. Two rounds of plausible hypotheses
went nowhere; one round of logging showed the mechanism outright.

When a symptom is unexplained, add logging that reports **state at the
moment of failure** — not just "it failed". The line that solved it was
`reselect FAILED (crypto=True ant=True)`: the two register bits, printed next
to the failure. Guessing which of them was wrong would have taken far longer
than printing both.

Then remove or gate the instrumentation. Verbose logging drowns the signal —
per-font-selection tracing alone was ~4 lines per screen repaint and buried
everything else.

## Logging conventions in this firmware

`bbox_server.py`, `card_writer.py` and `bbox_ui.py` each carry a module-level
`VERBOSE = False`.

- `_log()` always prints. `_dbg()` prints only when `VERBOSE`.
- **Failures are never gated.** Every abort prints its reason, every exception
  prints, every write outcome prints. The user's standing requirement is zero
  silent failures — if something did not work, the log must say so and say
  why.
- Serial output is `print()` to USB CDC. It is not stored and is discarded if
  no host is listening. It does not consume memory; the concern is signal, not
  space.

## Why reset causes are logged to flash

The board's USB is native CDC, so a reset drops the port and any panic
message goes into a port the host has already lost. The cause can only be
read on the *next* boot.

`reset_log.record()` runs as the first statement of `run()` and appends to
`/flash/resetlog.txt` (capped at 40 lines). `note_mode()` persists the current
mode to `/flash/lastmode.txt` on every change, so each line names the mode the
box was in *before* the reset:

```
2906 HARD was:SERVE
```

Read it with one batched `exec`, then `reset`:

```bash
python3 -m mpremote connect $PORT exec "
import reset_log
for l in reset_log.last(8): print(l)
" && python3 -m mpremote connect $PORT reset
```

Causes seen so far: `PWRON` (power cycle — including someone bumping the
cable or pressing the reset button), `HARD` (an `mpremote reset`). A
`BROWNOUT` or `WDT` would be a real finding; neither has appeared.

## Do not touch the wand tree

These four files are hardware-validated (4/4 field test, commits `cfed7a4`
and `c6f0716`) and frozen:

```
MockWand/main.py
MockWand/code_puller.py
MockWand/pull_flag.py
MockWand/lib/espnow_manager.py
```

Read them; do not edit them. The ordering they encode — pull-flag check as
`main()`'s first statement, no ESP-NOW in the pull path, `machine.reset()`
between radio modes — took three days to establish. `git diff --stat <round
base> -- Bag3/Code/BroadcastBox/MockWand/` must come back empty. Diff against
the round's base commit, not `May_2026`; the whole tree is new relative to the
main branch.

## The Box's wire contract is frozen

SSID `SP-FILEPUSH`, password `playground1`, port 8266, channel 1, 512-byte
chunks with a 20 ms yield, dest `jumpin.py`, header
`size(4B BE) | sha256(32B) | name_len(1B) | name`, 2-byte `OK`/`NO` ack.
Card text exactly `getcode` and `jumpin`.

Changing any of it breaks the wand silently. Full table in
`BBoxFirmware/README.md`.

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
required before every re-select. This was the cause of the
one-scan-per-boot symptom.

## Before you touch the Box at all

`BBoxFirmware/manifest.js` lists what ChatBroadcast's installer pushes. Every
module reachable from `main.py` must be in it — a missing one is an
`ImportError` at boot and a `fatal` JSON, which looks like a bricked box to a
teacher. Two modules were missing for most of this session's work.

Check it mechanically rather than by eye: walk the import graph from
`main.py` and compare against `BOX_FILES`.

## A reasonable session shape

1. Ask which port is which; ask that nothing else holds them.
2. Read the code before changing it. Ask what is actually broken rather than
   auditing for theoretical faults — several things flagged from reading
   turned out not to matter on real hardware, and the real bug was not among
   them.
3. Make one change at a time. Flash in one batched `mpremote` call.
4. Start a long passive capture, **then** tell the user to go, then wait.
5. Read the log. Report what it shows, not what you hope it shows.
6. Gate the instrumentation before calling anything done.
7. Offer to commit while the build is known good.
