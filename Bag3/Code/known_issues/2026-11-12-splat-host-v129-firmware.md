---
title: Splat host wand holds only 2 Splats on MicroPython v1.29.0
date: 2026-11-12
status: open
devices: [Wand (Mock Wand), ESP32-C6]
components: [MicroPython firmware, BLE, Splat host]
code:
  - Bag3/Code/Wand Module/main.py
  - Bag3/Code/Wand Module/lib/splat_hub.py
  - Bag3/Code/Experiments/SplatHostBench/README.md
open:
  - What in v1.29.0 breaks 4 Splats in the full wand_main boot (bench_diff.py STEP 0 gets 4 of 4 on v1.29.0).
  - Flash COM11 to v1.28.0.
  - 2026-11-11-simple-mode-large-changes.md records the 4-of-4 bench wand as v1.29.0; not re-checked.
keywords: [v1.29.0, v1.28.0, firmware, -519, -521, BLE, Splat host, 4 Splats, ENOMEM]
---

# Splat host wand holds only 2 Splats on MicroPython v1.29.0

## Symptom

With 4 Splats in `pairing.json` and `role.txt` = `splat_host`, a normal boot connects 2. The 3rd and
4th `connect_direct` fail with `-521` (HCI 0x09) or `-519` (HCI 0x07), and Splat writes then fail.

## Results (same `.mpy` libraries, `pairing.json`, `role.txt`)

| Wand | MicroPython | Normal boot |
|---|---|---|
| COM8 | v1.28.0 (2026-04-06) | 4 of 4 |
| COM7 | v1.29.0 (2026-08-24) | 2 of 4 |
| COM7, reflashed | v1.28.0 (2026-04-06), Seeed XIAO build | 4 of 4 (seen on the wand; no log) |
| COM11 | v1.29.0 (2026-08-24) | 2 of 4 |

COM7's battery read about 3 % on both firmwares. On v1.29.0 the bare bench
(`Experiments/SplatHostBench/bench_diff.py` STEP 0: ESP-NOW, BLE, hub modules) still connects
4 of 4. Logs and memory figures: `Experiments/SplatHostBench/README.md`.

## Mitigation

Flash Splat host wands with MicroPython v1.28.0. Check with `import os; os.uname()`.
