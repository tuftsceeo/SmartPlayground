# Handoff: Splat host memory (Bag3 wand, 4 Splats)

Branch `wand-splat-update` (commits e534aef, 3cb1c88; not pushed). Read first:
`README.md` (this folder), `../../known_issues/2026-11-12-splat-host-v129-firmware.md`,
`../../known_issues/2026-09-30-known-issues.md` #1, `../../HARDWARE_PROTOCOL.md`.

## Problem

The Bag3 wand (`Bag3/Code/Wand Module/`) as a Splat host connects 4 of 4 Splats on
MicroPython v1.28.0 and 2 of 4 on v1.29.0 (2026-08-24). BLE connections, ESP-NOW and the
Python heap's growth all draw from the ESP32-C6 IDF main data region (about 371 KB).
Each connection needs about 4–6 KB.

| Bench (COM11, v1.29.0) | IDF main free/largest before connecting | Result |
|---|---|---|
| STEP 0: ESP-NOW, BLE, connect | about 190 KB | 4 of 4 |
| STEP 3: all wand imports and objects, then connect | 6648 / 6528 | 1 of 4, -519 then -521 |

Logs: `step3_com11.log`, `step3_noboot_COM11.log`. On v1.28.0 STEP 3 had about 13 KB
before connecting, and about 1.5 KB after 4 connected.

## Hypothesis being tested

If the Splats connect right after BLE starts and before the heavy imports, the
connections get their memory while it is free, and v1.29.0 holds 4. Not yet shown.

`bench_step5.py` (new, not committed) does this: it connects for up to 30 s, does STEP 2's
imports and objects (including `bytearray(110000)`), polls for 20 s, then prints `RESULT`.

**First run is invalid.** `step5_com11.log`: the board had not been reset, and `MEM start`
showed 6432 IDF free and gcf 139104, against about 279 K and 328 K clean. 1 of 4 connected.

## Next steps

1. Power-cycle all 4 Splats. They sleep after pairing and keep a stale "paired" state.
   Switch off other wands nearby.
2. Hard-reset COM11, then run within the stub `main.py`'s 5 s grace. Confirm `MEM start`
   shows about 279 K IDF free, or discard the run:
   `python -m mpremote connect COM11 reset`, then
   `timeout 90 python -m mpremote connect COM11 resume run bench_step5.py`
   (run in the background and tee to `step5_com11.log`).
3. If it holds 4: move the same order into `Wand Module/main.py`. For a wand with
   `/pairing.json`, build `SplatHub` and connect before the imports at lines 43–75, and
   let `splatpair.SplatPairing` take that `hub=` instead of building its own (line 902).
   Wands without `/pairing.json` boot unchanged.
4. Then measure what play needs, which has not been measured:
   - the Python heap's largest free block with 4 Splats connected;
   - a `compile()` of a 10 KB game in that state;
   - an ESP-NOW code pull with 4 connected.

   Known data: compiling needs a free block about the file's size, and 40 KB fails 4 of
   5 runs. The ChatBroadcast prompt asks for game files under about 10 KB, and the app
   refuses a wand file over 32 KB.

## Boards

| Port | Firmware | State |
|---|---|---|
| COM11 | v1.29.0 | normal wand, `/benchmpy` libs, `role.txt`, `pairing.json` |
| COM8 | v1.28.0 | normal wand (4 of 4) |
| COM7 | v1.28.0 (Seeed XIAO build) | normal wand (4 of 4) |

COM9 and COM10 are not wands. Splat MACs are in the benches' `MACS`.

## Rules from the user

- Run port work in the background with a fixed experiment length.
- Upload only the files needed. Don't wipe boards.
- Never run the old `main.py` that blocks serial.
- Commit only when asked. Never push.
- Be token-efficient.
- Don't touch Bag2.

## Lasting fixes if the reorder is not enough

- Freeze the libraries into a custom firmware build.
- Fix the heap size at boot.
- Ship games as `.mpy`.
