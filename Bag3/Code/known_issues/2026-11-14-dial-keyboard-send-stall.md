---
title: Dial distribute fails just after the keyboard is built (D2); TypeError lines after a soft reset (D3)
date: 2026-11-14
status: open (draft from one log; S11 steps 2-4 will test it)
devices: [BroadcastDial]
components: [BDialFirmware/bdial_server.py, BDialFirmware/station_ui.py, BDialFirmware/code_link.py, m5ui port.py]
code:
  - Bag3/Code/TeacherTools/BroadcastDial/BDialFirmware/bdial_server.py
  - Bag3/Code/TeacherTools/BroadcastDial/BDialFirmware/station_ui.py
  - Bag3/Code/TeacherTools/BroadcastDial/BDialFirmware/code_link.py
open:
  - D2 cause not confirmed (screen work vs memory)
  - D3 source unknown
  - S11 hands-on block not yet run
keywords: [keyboard, distribute, schedule queue full, code_req, ENX offer, timeout, send_fail, soft reset, TypeError, LVGL, S11]
related:
  - Bag3/STRESS_TEST_FINDINGS_2026-11-14.md (D2, D3, S11 step 1)
  - Bag3/STRESS_TEST_PREP_PLAN.md (S11)
---

# Dial: distribute fails just after the keyboard is built, 2026-11-14

Draft from one hands-on session (ChatBroadcast, Dial, two wands). Not yet reproduced.

## D2: what was seen
- With the keyboard open, a distribute to two wands failed for both. The Dial sent both pushes
  (`why: pushed`), but neither wand's request arrived (no `[ENX] offer`). Both timed out after 30 s.
- The Dial printed `RuntimeError: schedule queue full` from its screen timer.
- The failure came about 14 s after the keyboard was first built. Free memory dropped from about
  53 KB to 27 KB at the build.
- After a USB reconnect, with no restart and the keyboard still open (about 160 s after the
  build), the same send worked. One wand needed retries (`send_fail=2`).

## D2: what the code suggests (not confirmed)
- The main loop takes **one** ESP-NOW message per pass (`code_link.poll`), from a 1024-byte
  receive buffer.
- The keyboard's rim labels are rotated and drawn through an LVGL layer, so building and
  repainting the page is slow. m5ui runs the LVGL handler through `micropython.schedule` from a
  timer. "schedule queue full" means those handlers are not keeping up.
- Best guess: right after the build, LVGL work holds up the main loop, so wand requests queue
  up and some are lost. Low free memory (GC pauses) may add to it.

## D2: test (S11 steps 2-3)
Restart the Dial, open the keyboard and send at once; send while turning the dial; send again
2 minutes later. Record free memory and "schedule queue full" for each. If only the first fails:
hold a distribute until the keyboard build finishes, or don't schedule a screen update while one
is pending. If memory is the cause, report the numbers and stop.

## D3: what was seen
Right after the soft reset that ends a raw-REPL game upload, about 20 lines of
`TypeError: '' object isn't callable` and `'bool' object isn't callable` came before the
program's first output, then USB dropped. Source unknown. S11 step 4 captures these lines.
A game sent over the JSON link (S5 step 4, `game_upload.py`) does no soft reset, so it should not
trigger D3; the raw-REPL fallback still can.
