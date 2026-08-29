# AGENTS.md

Non-production research prototype: MicroPython firmware for playground devices (ESP32-C6, ESP32-S3,
M5Stack) plus static web tools. Small team, weekly iteration.

## Device code (MicroPython)

- **Cannot be imported off-device** — `machine`, `espnow`, `neopixel`, and `ubluetooth` do not exist.
  `python -m py_compile <file>` is the only static check available.
- Shipped style, across all targets: f-strings are used throughout — don't "fix" them. No type
  annotations, and no `typing` / `dataclasses` / `pathlib` / `logging`.
- **Interruptible loops**: any loop doing serial I/O needs a small unconditional sleep every
  iteration — a busy loop can starve Ctrl-C and force a reflash to recover.

## Branches

- `main` is stale. Ask which branch to work from, or check `origin/HEAD` — the integration branch
  changes.
- Don't push directly to the default branch; it's protected.
- Don't add production gating, release process, or verification requirements unless asked.

## Bags

A Bag is a hardware+software generation, not a version. Bag1 and Bag2 are fielded; Bag3 is in
progress. Cross-generation compatibility is not a goal.

- `Bag1/` is fielded and not under active development — ask before editing.
- `Bag2/Code/Wand Module/` and `Bag3/Code/Wand Module/` are independent copies. Divergence is
  expected. Never apply a change to both silently; say which tree you touched.

## Shared libraries are duplicated by hand

`espnow_manager.py`, `game_tags.py`, `ssd1306.py`, and `ws1850s.py` are our own libraries, kept as
separate per-tree copies rather than imported across directories. Fixing one fixes only that copy.
If you find a copy that has diverged from its Bag's version, flag it rather than silently
reconciling.

Game tags are consumed in four places, with nothing enforcing consistency: each Bag's
`lib/game_tags.py`, `Live_Page/WebApp2/hubCode2/game_tags.py`,
`Live_Page/WebApp2/js/utils/commands.json`, and `Live_Page/wand_icons.html`.

## Dead trees

`old_stuff/` and `WebAppDocs/` are dead, and will dominate a naive grep.

## "hub" means two things

In `Live_Page/`, the teacher-facing ESP32 that bridges USB serial to ESP-NOW. In the Bag trees, any
playground component (`hubtype.txt` → `HUB_CONFIG`).
