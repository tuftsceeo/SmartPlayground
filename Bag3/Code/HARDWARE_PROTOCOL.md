# Hardware protocol — Box, Dial, Wand, and future M5 prototypes

Read this before opening a serial port or flashing anything against this hardware.

**"Verified" in this doc means someone checked device or log state directly, and
says how.** If you verify or correct something here, cite how (log excerpt,
source citation, command and output) so the next agent can judge it instead of
re-deriving it.

## `mpremote`: always use `resume`

**Pass `resume` on every `mpremote` invocation against this hardware, for
every action — `ls`, `exec`, `cp`, all of it. No exceptions.**

```bash
python3 -m mpremote connect $PORT resume fs ls :/flash/
```

Why: `mpremote` defaults to a soft-reset (Ctrl-D) on the first `fs`/`exec`
call of an invocation, before running anything. This is `mpremote`'s own
default behaviour (`main.py`/`transport_serial.py`), not a device quirk.
`resume` skips it.

Verified 2026-09-21, direct testing on both boards:

- **Box / Dial / Stamp (M5, UIFlow-based)**: `fs`/`exec` without `resume`
  reliably de-enumerates the USB CDC port
  (`OSError: [Errno 6] Device not configured`). It happens at the `fs`/`exec`
  call itself; waiting or retrying does not fix it. `resume` on the same
  call works, under 0.3s.
- **Writes on M5/UIFlow boards must target `:/flash/...`.** `fs cp` to `:/`
  root or any other top-level path fails with `Operation not supported by
  device`, with or without `resume` — not a reset symptom. `fs cp` to
  `:/flash/...` and its subdirectories (e.g. `:/flash/games/`) succeeds.

Batched deploy, one invocation, writes under `/flash`, then a plain `reset`
(no `resume`) to bring the new code up — `resume` only avoids the reboot on
the write, it does not restart the program:

```bash
PORT=/dev/cu.usbmodemXXXX   # ask first
python3 -m mpremote connect $PORT resume \
  fs cp bbox_server.py :/flash/bbox_server.py + \
  fs cp bbox_ui.py :/flash/bbox_ui.py
python3 -m mpremote connect $PORT reset
```

`mpremote` is available as `python3 -m mpremote` (no `mpremote` binary on
PATH here).

## Two things `resume` does not fix

- **`exec`/`fs` still stops the running program, `resume` or not, and it does
  not come back on its own.** Ctrl-C is sent to enter raw REPL regardless of
  `resume`; `resume` only skips the reboot that would otherwise follow. The
  board is left sitting at the REPL. Verified 2026-09-21 on the wand: with
  heartbeat JSON confirmed active (post-reset baseline), a single trivial
  `resume exec "print(...)"` silenced it for 15s afterward with no recovery.
  If you need the program running again after a `resume` call, issue a plain
  `reset` (no `resume`) afterward. To observe a running board without
  stopping it, use `tools/serial_monitor.py` or the JSON driver above, not
  `exec`.
- `sys.path` read under `exec` reflects `exec`'s own context, not
  necessarily `main.py`'s. Judge import paths from a real boot log.

## The two hard rules

**1. Ask which board is on which port. Never guess, never infer.**

Boards enumerate as sibling `/dev/cu.usbmodem*` names that change between
sessions. `ls /dev/cu.usbmodem*` tells you two ports exist, not which is
which. Any port name in this doc is an example from a past session, not a
fixture.

**2. Ask before opening a port and wait for an explicit answer.**

ChatBroadcast holds the Box's port over WebSerial whenever it is connected.
One process at a time — this applies to a quick read too. Check nothing else
holds the port first: `lsof /dev/cu.usbmodemXXXX`.

## You cannot see the screen or press the buttons

Every physical observation comes from the user.

- The user reads messages later, not immediately. A background-task
  notification is not user input.
- Give numbered physical steps, state that you're waiting, then STOP. Take
  no hardware-facing tool action until the user says start/ready/go.
- Put the action item first, at the top of the turn.
- Use long capture windows (~15 min).
- Report what the log shows, not that something "works" — only the user can
  confirm the device behaved.
- Tests are short numbered physical steps: which button, what to expect on
  screen, what to report back.

## Driving the boards without a person

Drive from the host whatever can be driven, saving the person for what
actually needs fingers or eyes: reading a real card, writing a card, or
anything judged by the screen, LEDs, or buzzer. State which kind of evidence
you have — a faked input does not exercise the same path as a real one.

For any behaviour reachable by a JSON command, write newline-delimited JSON
straight to the CDC port. Do **not** use `mpremote exec` for this — it stops
the running program (see "Two things `resume` does not fix" above). See the
device READMEs below for the specific commands and host-drivable hooks each
board exposes.

## Verify a constructed command before firing it at hardware

The shell here is `zsh`, not `bash` — bash array idioms can fail silently.
Print the constructed argument list and check it before sending it to a
board.

Use absolute paths — the working directory may not persist between commands
in an agent session.

## Watching a running board

```bash
python3 tools/serial_monitor.py /dev/cu.usbmodemXXXX 900 > run.log
```

Run in the background, tell the user to go, then read `run.log`. Filter
noise — the wand's `memprobe` GC dumps are ~40 lines a boot:

```bash
grep -vE "^\[ *[0-9.]+s\] (0000|GC:|stack:|MEM|MEMFRAG| No\. of)" run.log
```

A dropped port mid-log is usually a board reset — treat it as a finding.
Check first that you are not holding the port yourself: a background capture
or JSON driver still running reads exactly like a reset
(`device reports readiness to read but returned no data`). `pgrep -f` your
own scripts before concluding the hardware did something.

## Instrument before theorizing

Add logging that reports state at the moment of failure, not just that it
failed. Remove or gate the instrumentation once resolved — verbose logging
drowns the signal.

## Device-specific reference

Firmware layout, wire protocol, slug rules, NFC card safety, and logging
conventions are code-tied and belong with the code, not here:

- `BroadcastBox/BBoxFirmware/README.md` — wire contract, card text/safety,
  logging, reset and stats logs, manifest check.
- `BroadcastBox/MockWand/README.md` — wand tree invariants, slug rules,
  direct-USB push.
- `BroadcastDial/README.md` — Dial specifics; shares the Box's wire contract
  and card rules.

## A reasonable session shape

1. Ask which port is which; ask that nothing else holds them.
2. Read the code before changing it. Ask what is actually broken rather than
   auditing for theoretical faults.
3. Make one change at a time. Flash in one batched, `resume`d `mpremote`
   call, then a plain `reset` (no `resume`) to bring the new code up.
4. Drive from the host whatever can be driven; reserve the user's attention
   for cards, buttons, and screens. State which kind of evidence you have.
5. Tell the user the capture is about to start and what physical action to
   take. Stop and wait for start/ready/go.
6. Read the log. Report what it shows.
7. Gate the instrumentation before calling anything done.
8. Offer to commit while the build is known good.
