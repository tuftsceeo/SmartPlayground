---
name: bag3-hardware-protocol
description: Rules for touching physical Bag3 prototypes over USB (Broadcast Box, Broadcast Dial, wands, M5 boards, CrowPanel). Load BEFORE opening a serial port, running mpremote, flashing, deploying/copying firmware, capturing a serial log, or asking the user to test a device.
---

# Bag3 hardware protocol

Full rules and measurements: `Bag3/Code/HARDWARE_PROTOCOL.md` (the source of truth; read it
for anything not covered here). Paths below are relative to the repo root. Shell is zsh.

## Before touching a port

1. **Ask the user which board is on which port.** Never infer a board from a port name. Ports
   show up as `/dev/cu.usbmodem*`, and CH340 boards like the CrowPanel as `/dev/cu.usbserial-*`.
2. **Get an explicit yes before opening one.** One process at a time: ChatBroadcast holds the Box's
   port over WebSerial, and another session may be using a port. Check with
   `lsof /dev/cu.usbmodemXXXX`, and don't kill a process you didn't start.

## Deploy

**M5/UIFlow boards (Box, Dial, Stamp):** reset, copy everything in one `resume` call to
`:/flash/...`, then reset again (from `HARDWARE_PROTOCOL.md`):

```bash
python3 -m mpremote connect $PORT reset
python3 -m mpremote connect $PORT resume \
  fs cp bbox_server.py :/flash/bbox_server.py + \
  fs cp bbox_ui.py :/flash/bbox_ui.py
python3 -m mpremote connect $PORT reset
```

To list the files: `git diff --name-only <deployed-commit>..HEAD -- <firmware dir>`. Copy right
after the reset; copying into the running program takes 80 s or more per call.

**Wand: routine updates use the reset-then-one-copy steps above, not `tools/deploy.py`.**
`HARDWARE_PROTOCOL.md` reserves `deploy.py` for a very stale device or a board freshly flashed
with blank firmware ONLY: it is slow (over 4 min unfinished on the Dial; it stalled on Windows too)
and it stops at a `Go? [y/N]` prompt that a background run cannot answer.

The wand must not get the source `main.py`. Compile it on the computer, copy the `.mpy`, and
leave the one-line `/main.py` that imports `wand_main` in place:

    python -m mpy_cross -o wand_main.mpy main.py          # mpy-cross==1.28.0.post2
    python -m mpremote connect $PORT reset
    python -m mpremote connect $PORT resume fs cp wand_main.mpy :/wand_main.mpy + fs cp lib/x.py :/lib/x.py
    python -m mpremote connect $PORT reset

On Windows: `python`, not `python3` (the `python3` there is the Store placeholder); ports are
`COMn`; there is no `lsof`, so ask the user what else has the port open.

**Time-limit every port command.** Give each `mpremote` call a timeout sized to the
operation, and check background runs regularly instead of waiting on them. When a
call runs out, find out why before acting: check what holds the port, whether the
board is still on USB, and what state it is in. Tell the user what you found, and ask
before any physical step. Don't retry the same command blind.

## Non-negotiables

- `resume` on every `mpremote` call (`ls`, `exec`, `cp`). Without it, M5 boards drop off USB
  (`OSError: [Errno 6] Device not configured`). Bring code up with a plain `reset` (no `resume`).
- `exec`/`fs` stop the running program, even with `resume`. To observe or drive a live board,
  use the background capture below or newline-delimited JSON written to the port, never `exec`.
- You can't see the screen or press buttons. Put the action item first, give numbered physical
  steps, say you're waiting, then STOP until the user says start/ready/go. Report what the log
  shows, not that something "works". Say whether evidence came from faked input or a real card
  or button.

## Watching a running board

```bash
python3 Bag3/Code/tools/serial_monitor.py /dev/cu.usbmodemXXXX 900 > run.log
grep -vE "^\[ *[0-9.]+s\] (0000|GC:|stack:|MEM|MEMFRAG| No\. of)" run.log
```

Run the capture in the background. If the port drops mid-log, `pgrep -f serial_monitor` before
calling it a reset: your own capture still holding the port looks the same.

## Gotchas

- The protocol doc says `tools/serial_monitor.py`. The real path is
  `Bag3/Code/tools/serial_monitor.py`.
- `mpremote` is `python3 -m mpremote` (no binary on PATH).
- Bash array idioms can fail silently in zsh. Print a constructed command before firing it.
- Device-specific commands are in the device READMEs listed at the end of `HARDWARE_PROTOCOL.md`.
  The wand's is `Bag3/Code/Wand Module/README.md`.
