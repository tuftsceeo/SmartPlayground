---
title: Broadcast code pull, game size and stats
date: 2026-09-30
status: open (2 items)
devices: [BroadcastDial, BroadcastBox, MockWand, IconDisplay]
components: [lib/espnow_code.py, stats_log.py, ChatBroadcast send path]
open:
  - Game size limited by wand compile() check
  - stats.log counts are windowed
keywords: [compile, MemoryError, game size, stats.log]
related:
  - Bag3/Code/BroadcastCode/docs_and_design/2026-10-20-espnow-serving/PLAN.md
aliases: [docs_and_design/2026-09-30-known-issues.md]
---

# Known issues — Broadcast code pull, 2026-09-30

Scope: the wand's `compile()` check in `lib/espnow_code.py` (MockWand, IconDisplay), `stats_log.py` (Dial, Box), and ChatBroadcast's send path.

Sources:

- **pull-speed:** `../BroadcastCode/docs_and_design/2026-09-30-pull-speed-results.md`

## Open

### 1. Game size is limited by the wand's `compile()` check
- **Behavior.** `_compile_check()` reads the whole file and compiles it, which needs a free block about the file's size (41216 B for a 40960 B file). A `MemoryError` is reported as "too large to compile here".
- **Measured** with the same check on the 2026-09-30 WiFi receiver: 20480 B passed 5/5; 40960 B passed 1/5, the other runs failing with `MemoryError` after a complete transfer. Sizes between 20 and 40 KB are untested (pull-speed).
- **Launch.** A pulled game is compiled again when it is launched. That is not measured.
- **No limit at send time.** ChatBroadcast has no file size check.

### 2. `stats.log` counts are windowed
- **Timestamps.** Lines are stamped with per-boot `ticks_ms()`.
- **Window.** The file keeps the newest 200 lines, shared with tag writes. `aggregate()` counts only `ok` lines inside that window.
