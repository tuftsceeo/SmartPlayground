# Radar Station -- LD2450 mmWave exploratory prototype

Stationary sensing component: a Seeed XIAO ESP32-C6 reading one Hi-Link HLK-LD2450 24GHz mmWave
radar over UART, exposing student presence / position / speed / direction / count as JSON over
USB serial for a browser-based viewer. Built for Bag3 as an internal exploratory demo -- see the
top-level plan (`i-m-looking-to-make-shimmering-wand.md`) for full context, research, and
rationale.

**Status: Gate A (protocol bring-up) passed on the bench, with caveats.** The board boots cleanly,
opens the UART, and parses live LD2450 frames with zero drops/resyncs over a full minute. Two bugs
found during bring-up are fixed (see "Bring-up findings" below). **Not yet validated:** the test
subject was a person rocking in a desk chair a couple feet away, not an actual walker, and the
board isn't mounted yet -- so frame-rate/range/dropout numbers are bug-check evidence only, and
`SIGN_X`/`SIGN_Y` in `config.py` are still unconfirmed placeholders. Gate B (real walking tests,
sign-convention check, web app) is next.

## Priority order (see the plan for full detail)

1. **Single-sensor driver + hardware bring-up** -- `ld2450.py`, `tracker.py`, `events.py`,
   `config.py`, `radar_test.py`. In scope, built.
2. **Web Serial viewer** -- `json_link.py` (vendored), `radar_server.py`, `main.py`, `webapp/`. In
   scope, built.
3. Dual-sensor feasibility research -- complete, findings recorded in the plan; no code here.
4. Dual-sensor implementation -- **out of scope**, future stage, not started.

## Wiring

- LD2450 5V/GND -> board 5V/GND. LD2450 RX <- board GPIO16 (D6), LD2450 TX -> board GPIO17 (D7),
  via `UART(1, tx=16, rx=17, baudrate=256000)` -- see `config.py`.
- **Confirmed on this unit:** LD2450 TX idle voltage was measured safe for the C6's 3.3V GPIOs
  before wiring it in.
- Watch out: the XIAO ESP32-C3 and ESP32-C6 boards are visually identical and easy to mix up on a
  bench -- if `config.py`'s pins throw `ValueError: invalid pin`, check the boot banner
  (`sys.implementation`) before assuming the wiring is wrong.
- The C6's native USB runs the REPL/JSON link over USB-CDC, independent of the LD2450's UART, so
  claiming GPIO16/17 (the SoC's default UART0 pins) as a separate `machine.UART` doesn't disturb it.

## Protocol (LD2450 <-> station)

Report frame, streamed continuously at 10Hz, no request needed:

```
AA FF 03 00 | T1[8] | T2[8] | T3[8] | 55 CC        (30 bytes)
```

Each target: `x[2] y[2] speed[2] resolution[2]`, little-endian, **sign-magnitude** (not two's
complement) for x/y/speed -- MSB is a sign flag over a 15-bit magnitude. x/y in mm, speed in cm/s
(radial/line-of-sight only). An all-zero target block means that slot is empty.

Command frame (config only): `FD FC FB FA | len[2] | cmd_word[2] | value[...] | 04 03 02 01`.

**Sign convention is unverified** -- run `radar_test.sign_check()` per the plan's Gate A step 5 and
adjust `SIGN_X`/`SIGN_Y` in `config.py` if left/right or toward/away come out backwards. (Gate A's
first pass only rocked a chair in place, which confirmed the parse/print path but not the actual
signs -- redo with a real walk.)

## Protocol (station <-> browser)

NDJSON over USB serial, one JSON object per line. Commands: `hello`, `info`, `stream {on}`,
`raw {on}`, `mode {value: "multi"|"single"}`, `repl`, `reboot`. Streamed while `stream` is on:
`targets` (raw per-sensor detections, only when `raw` is also on), `tracks` (stable tracked
objects), `events` (derived presence/zone/speed signals) -- see the plan's "Wire protocol" section
for exact shapes.

## Running

On-device: flash `main.py`, `json_link.py`, `ld2450.py`, `tracker.py`, `events.py`,
`radar_server.py`, `config.py` with `mpremote`. For bring-up before any of that is trusted, use
`radar_test.py`'s `hexdump()` / `frame_stats()` / `sign_check()` functions interactively from the
REPL.

Web app: `cd webapp && python3 -m http.server`, open `http://localhost:8000` in Chrome/Edge (Web
Serial needs a secure context; localhost qualifies). Connect, and the plan view, events panel, and
serial monitor come up live. Record a session to JSONL with the Record button; replay one with no
hardware attached via "Replay JSONL".

## Bring-up findings (Gate A)

Bugs found on-device and fixed:

- `ld2450.py`'s `poll()` used `del buf[:n]` (bytearray slice deletion) to trim the parse buffer.
  This MicroPython build's `bytearray` does not support slice deletion at all
  (`TypeError: 'bytearray' object doesn't support item deletion`), which crashed frame parsing
  outright. Fixed to `buf[:] = buf[n:]` slice assignment, which this build does support -- see the
  comment on `poll()`.
- `config.py`'s `UART_TX`/`UART_RX` had drifted out of sync with the actual wiring at one point
  during bring-up (see the git history on this file for the C3/C6 board mix-up that caused this).

With both fixes applied: `hexdump()` shows clean `AA FF 03 00 … 55 CC` framing at the correct
30-byte spacing, and `frame_stats()` ran 60s with `frames_ok=674, frames_dropped=0, resyncs=0`
(~11.2 fps against a nominal 10Hz) -- 256000 baud is clean on this board and the non-blocking
parser holds up over sustained real target data. `sign_check()` printed sane, jitter-only x/y/speed
values with no crashes. **All of the above used a person rocking in a desk chair, not a real
walker, and the board wasn't mounted** -- so this is bug-check evidence that the code path works,
not calibration or performance data. Still needed: a real walking test once someone's available,
with the board mounted in its final orientation, to actually determine `SIGN_X`/`SIGN_Y` and the
practical range/azimuth dropout points (plan Gate A steps 5-7).

## Known limits (see the plan for the reasoning)

- 3-target hardware cap; two people close together can merge into one target.
- The sensor's own `speed` is radial-only -- true ground speed/heading come from the tracker's
  position-delta estimate, not the sensor.
- Track IDs are association-based (nearest-neighbour, gated), not sensor identities -- expect some
  churn under occlusion or crossing paths; `TRACK_GATE_MM`/`TRACK_MAX_MISSES` in `config.py` are
  the knobs, to be tuned from real traces.
- Single sensor only in this codebase. Two-sensor fusion (wide-FOV splay, interference testing) is
  designed in the plan (Priority 3) but deliberately not implemented (Priority 4, future stage).
