# Radar Station -- LD2450 mmWave exploratory prototype

Stationary sensing component: an ESP32-S3 (M5Stack: StampS3 / StickS3 / M5Dial 1.1) reading one
Hi-Link HLK-LD2450 24GHz mmWave radar over UART, exposing student presence / position / speed /
direction / count as JSON over USB serial for a browser-based viewer. Built for Bag3 as an
internal exploratory demo -- see the top-level plan
(`i-m-looking-to-make-shimmering-wand.md`) for full context, research, and rationale.

**Status: awaiting Gate A/B hardware bring-up.** Everything here compiles (`python -m py_compile`)
and is designed against the datasheet-derived protocol, but nothing has run against real hardware
yet. Numbers marked "placeholder" in `config.py` need real traces before they mean anything.

## Priority order (see the plan for full detail)

1. **Single-sensor driver + hardware bring-up** -- `ld2450.py`, `tracker.py`, `events.py`,
   `config.py`, `radar_test.py`. In scope, built.
2. **Web Serial viewer** -- `json_link.py` (vendored), `radar_server.py`, `main.py`, `webapp/`. In
   scope, built.
3. Dual-sensor feasibility research -- complete, findings recorded in the plan; no code here.
4. Dual-sensor implementation -- **out of scope**, future stage, not started.

## Wiring

- LD2450 UART -> ESP32-S3 UART1 (pins TBD by Gate A -- see `config.py`'s `UART_TX`/`UART_RX`,
  currently placeholders).
- **Before wiring the LD2450's TX into an S3 GPIO, measure its idle voltage with a meter.** It's
  5V-powered; its UART is reported 3.3V logic but this is unverified for our unit. See Gate A step 2
  in the plan.
- ESP32-S3 native USB runs the REPL/JSON link over USB-CDC, independent of the LD2450's UART.

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
adjust `SIGN_X`/`SIGN_Y` in `config.py` if left/right or toward/away come out backwards.

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

## Known limits (see the plan for the reasoning)

- 3-target hardware cap; two people close together can merge into one target.
- The sensor's own `speed` is radial-only -- true ground speed/heading come from the tracker's
  position-delta estimate, not the sensor.
- Track IDs are association-based (nearest-neighbour, gated), not sensor identities -- expect some
  churn under occlusion or crossing paths; `TRACK_GATE_MM`/`TRACK_MAX_MISSES` in `config.py` are
  the knobs, to be tuned from real traces.
- Single sensor only in this codebase. Two-sensor fusion (wide-FOV splay, interference testing) is
  designed in the plan (Priority 3) but deliberately not implemented (Priority 4, future stage).
