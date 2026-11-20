---
title: Find Me ends a running game; device list varies wildly with many controllers
date: 2026-11-18
status: open (no change made)
devices: [MockWand, BroadcastDial, BroadcastBox]
components: [espnow_manager find_device / status_poll, fleet.py scan, ChatBroadcast distribute overlay]
code:
  - Bag3/Code/Wand Module/lib/espnow_manager.py
  - Bag3/Code/TeacherTools/BroadcastDial/BDialFirmware/fleet.py
  - Live_Page/ChatBroadcast/js/distribute.js
open:
  - Find Me force-switches the target into the finddevice game, ending whatever is running (confirmed from the code; reported in the room)
  - Device list returned 12, 2, then 5 devices on refresh with 8 controllers in the room (reported); cause not confirmed
keywords: [find_device, finddevice, Find Me, status_poll, status_report, scan, roulette, stress test, multiple controllers, _schedule_status_reply, slot]
related:
  - Bag3/Code/docs_and_design/2026-11-18-stress-test-debrief.md
  - Bag3/Code/known_issues/2026-10-23-distribute-code.md
---

# Find Me and the device list under load, 2026-11-18

Stress test setup: 8 teacher controllers, more than 15 wands and stations in one room. The
full debrief and the ideas are in `docs_and_design/2026-11-18-stress-test-debrief.md`.

## Find Me ends a running game

**Reported.** Someone used Find Me to look for their own wand, and it ended a game in play.

**From the code (confirmed).**
- **Find Me launches a game.** `espnow_manager` rewrites `find_device` into
  `start_game {"name": "finddevice"}` (`Wand Module/lib/espnow_manager.py:451-460`), and that
  force-switches whatever is running.
- **The app sends it without asking.** `fleet.find` goes out from the app's card button
  (`distribute.js:472`) with no check first.
- **The app could not warn anyway.** `status_report` carries the installed slots (`g`) but
  not the running game.

## Device list varies (12 / 2 / 5)

**Reported.** Repeated refreshes listed very different numbers of devices. Card-tap pulls
still worked.

**Bench-measured, same afternoon (one Dial, 17 devices).**
- **Push-back confirmed.** The first point below is the cause.
  - A device answers only if its reply wait is shorter than the gap between polls.
  - With scans at random times, mean gap 1.3 s, each 6 s list held 3–17 devices (median
    12).
  - One quiet controller got 17/17 in 57 of 60 scans.
- **Only 4 slots in use.** MACs come in blocks of 4, so `last byte % 16` only yields slots
  0, 4, 8 and 12.
- **Find stutter.** A single Find starts `finddevice` 3 times, because each of the Dial's 3
  copies interrupts the last.

- **Three controllers (T1).**
  - Scanning at random, each about every 8 s: lists of 8–17.
  - Scanning within the same 0.5 s: always 17, because replies are broadcast and shared.
- **Find traffic (T2).** With about 0.45 Finds/s room-wide, lists ran 6–17 and *every*
  device was listed less often. This was not isolated from the room state; see the
  debrief's control run.
- **Find control.**
  - Finds sent to a MAC nobody has did no harm.
  - Real Finds took devices in every slot out of the list, worst 8–20 s *after* the Find
    (31% missing vs 11%).
  - So it is the wand's reaction to Find that does the damage, not the radio traffic.
- **Box dropout.** The Box dropped off USB during the real-Finds part and stayed silent
  afterwards. Cause not known.
- **Directed sends held up (T2).** 12/12 succeeded under scans and Finds.
  - Exception: the first quiet send. All 3 concurrent pull sessions stalled and were dropped
    after 15 s idle.
  - Cause not known.

Details are in the debrief's "Bench results".

**From the code** (the hypotheses before the bench test).
- **Each poll pushes the reply back.**
  - Each `status_poll` resets the device's single pending reply
    (`_schedule_status_reply`, `espnow_manager.py:267-273`).
  - The reply is due at 400 ms + (last MAC byte % 16) × 180 ms after the most recent poll.
  - With 8 controllers polling (3 sends each per scan), a late-slot device can be pushed back
    repeatedly and miss every 6 s window (`fleet.py:25`).
  - A poll between a device's two copies also cancels the second copy.
- **Slot collisions.** 15+ devices in 16 MAC-derived slots collide, and the second copy, 120
  ms later, collides with the same partner.
- **Controller drops replies.** The rxbuf and one-message-per-loop limits are already recorded
  in `2026-10-23-distribute-code.md`.
- **Lists show the whole room.** `fleet.on_msg` (`fleet.py:104`) accepts any
  `status_report` in its window, including replies to other controllers' polls. So the list
  is the room, not one teacher's devices.
