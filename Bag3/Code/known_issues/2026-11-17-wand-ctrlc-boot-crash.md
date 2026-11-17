---
title: Wand crashes when Ctrl-C lands during boot
date: 2026-11-17
status: open (seen once on hardware 2026-11-17; mechanism unconfirmed)
devices: [Wand (Mock Wand), ESP32-C6]
components: [main.py radio prewarm, main.py _boot(), espnow_manager init, wand_breakin.py]
code:
  - Bag3/Code/Wand Module/main.py
  - Bag3/Code/Wand Module/lib/espnow_manager.py
  - Bag3/Code/tools/wand_breakin.py
open:
  - Find where the Ctrl-C landed. "ESPNow: active" is printed by ESPNowManager.init() inside _boot(), after the GRACE_S countdown, not by the prewarm.
  - Check the 11:08 log for the "# booting -- Ctrl-C within 30s" line; that shows whether the wand ran the current build and whether Ctrl-C was ignored for the whole countdown.
  - Confirm or rule out the prewarm hypothesis (main.py:20-33 catches only Exception).
  - Related - Ctrl-C lockout once stdin fills, see 2026-11-17-wand-ctrlc-stdin-full.md.
keywords: [Ctrl-C, KeyboardInterrupt, Guru Meditation, Load access fault, rst:0xc, panic, prewarm, ESPNow active, wand_breakin, boot, REPL]
---

# Wand crashes when Ctrl-C lands during boot

## Symptom

On 2026-11-17 at 11:08:16 the spare wand (MAC A0:F2:62:85:D6:14, MicroPython v1.28.0) crashed
during boot. `wand_breakin.py` had opened the port (which resets the wand) and was sending Ctrl-C
every 100 ms for up to 35 s. The log shows "ESPNow: active", then straight away a Guru Meditation
Error (Load access fault), then a reboot with rst:0xc (panic reset).

Seen once. Not yet reproduced on purpose.

## Likely mechanism (unconfirmed)

The radio prewarm at `main.py:20-33` (Pin 3/14 antenna select, `WLAN(STA_IF).active(True)`,
`espnow.ESPNow()`, `config(rxbuf=4096)`, `active(True)`) sits in a `try` that catches only
`Exception`. A `KeyboardInterrupt` is not an `Exception`, so a Ctrl-C during bring-up skips the
rest of the block and leaves the radio half-started. A later step could then fault on that state.

This has not been tested. One fact does not fit: the prewarm prints nothing on success.
"ESPNow: active" is printed by `ESPNowManager.init()` (`lib/espnow_manager.py:140`), called from
`_boot()` after the 30 s `GRACE_S` countdown. If the wand ran the current build, the Ctrl-C that
preceded the fault landed in `_boot()` after `enow.init()`, not in the prewarm.

## Workaround

`wand_breakin.py` now sends no Ctrl-C until main.py prints "# booting -- Ctrl-C within",
then one every 200 ms, and stops when the countdown reaches "# 1..." (changed 2026-11-17,
not yet run on hardware).

## Fix

Waiting for the bench test that isolates which boot step stops Ctrl-C. No firmware change yet.
