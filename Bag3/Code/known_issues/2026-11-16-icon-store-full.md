---
title: Icon display flash fills with icons; a full store breaks pulls
date: 2026-11-16
status: open (read from code, not tested on hardware)
devices: [IconDisplay (XIAO ESP32-C6)]
components: [icon store, ESP-NOW code pull, icon editor link]
code:
  - Bag3/Code/Stations/IconDisplay/lib/espnow_code.py
  - Bag3/Code/Stations/IconDisplay/main.py
  - Bag3/Code/Stations/IconDisplay/icon_store.py
  - Bag3/Code/Stations/IconDisplay/icon_server.py
  - Bag3/Code/Stations/IconDisplay/lib/fsinfo.py
open:
  - Nothing removes a deleted game's icons from icons/; only the editor's delete does.
  - ENOSPC during a pull is not caught (see below).
  - Free space on a real unit not yet read (the boot line exists from 2026-11-16).
keywords: [icons, flash, full, ENOSPC, statvfs, free space, pull, getcode, icon_dir]
---

# Icon display: full icon store

The display carries 250 icons (about 835 KB) and keeps every icon any pulled
game brought; a deleted game's icons stay in `icons/`.

Boot now prints `  Flash free: <free> KB of <total> KB` (`lib/fsinfo.py`, imported
in `_boot()` after `enow.init()`).

## What happens when the flash is full (from the code)

- `espnow_code._fetch()` writes `<dest>.part` with no `OSError` handling, so a
  write failure leaves `receive()` as an exception: the `.part` file stays on
  flash and no `code_done` reaches the host.
- `_espnow_pull_and_launch()` does not catch it; the main loop's
  `[ERR] Main loop:` handler does, and the display returns to idle.
- Game fits, an icon does not: the game is already promoted, but the
  exception skips the remaining icons, `set_last_pulled`, `game_slots.record`
  and the reset, so the game sits in `/games` unrecorded and is not launched.
- Icon editor save (`icon_server.do_save`): caught, replies
  `{"type":"error","code":"io"}`; the `.tmp` file is left behind.

## Fix (2026-11-16, IconDisplay copy only; hardware untested)

`_fetch_safe()` wraps `_fetch()`: a write `OSError` removes `.part`, sends
`code_done` with `ok: false`, and returns `write failed: <err>`. A write
failure in the icon leg stops it, deletes the just-promoted game and restores
its `.bak`; `receive()` returns False, so `main.py` shows the red X and does
not record or launch the game. The wand's `espnow_code.py` is unchanged.
