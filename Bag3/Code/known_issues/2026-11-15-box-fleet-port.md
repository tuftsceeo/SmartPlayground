---
title: Broadcast Box fleet scan, find and distribute (port from the Dial)
date: 2026-11-15
status: scan and distribute pass on hardware 2026-11-16 (USB, arm's length); range, battery and NFC-during-distribute untested
devices: [BroadcastBox]
components: [BBoxFirmware/fleet.py, BBoxFirmware/bbox_server.py, BBoxFirmware/bbox_ui.py, ChatBroadcast/js/app.js]
code:
  - Bag3/Code/TeacherTools/BroadcastBox/BBoxFirmware/fleet.py
  - Bag3/Code/TeacherTools/BroadcastBox/BBoxFirmware/bbox_server.py
  - Bag3/Code/TeacherTools/BroadcastBox/BBoxFirmware/bbox_ui.py
  - Bag3/Code/ChatBroadcast/js/app.js
open:
  - Not run on a Box: find, NFC tap during a distribute
  - Power earmark (below)
  - Range from a Box at TX_POWER_DBM = 8 unmeasured (below)
keywords: [range, tx_power, TX_POWER_DBM, fleet, scan, find, distribute, status_report, code_push, show_progress, Box, broadcast_box, power, reset]
related:
  - Bag3/Code/known_issues/2026-10-23-distribute-code.md
  - Bag3/Code/known_issues/2026-11-02-dial-box-arm-serving.md
  - Bag3/Code/known_issues/2026-09-01-bbox-usb-reboots.md
---

# Box fleet port, 2026-11-15 (stress-test prep S12 step 3)

**Status: off-device tests only. Not run on a Box.**

What changed:
- `BBoxFirmware/fleet.py` is a byte-for-byte copy of `BDialFirmware/fleet.py` (its docstring still
  says "the Dial's radio"). It is imported on the first `fleet.*` command, after the radio is up.
- `bbox_server.py`: `fleet.scan`, `fleet.find`, `fleet.distribute`, `fleet.cancel`, as on the Dial.
  `_serve()` passes non-code messages to the fleet and calls `fleet.step()`. A pull result goes to
  `fleet.on_pull()`. `_nfc_field(True)` cancels a running scan or distribute (`"radio_off"`)
  before the radio goes down. Identity carries `"fleet": 1`.
- `bbox_ui.show_progress(done, total)` writes "Sending 2/5" in the top line of whatever screen is
  up; total 0 restores the list crumb or blanks the line.
- ChatBroadcast shows Distribute for a Box only when its identity has `fleet`
  (`app.js boxWithoutFleet()`), so a Box on older firmware still hides it.
- The Box has no slot picker. ChatBroadcast's distribute overlay sends `replace`; the Box passes
  it through, as the Dial does.

Off-device checks: `BBoxFirmware/tools/test_box_serve.py` (server hooks),
`BDialFirmware/tools/test_fleet.py` (the shared `fleet.py`), `ChatBroadcast/tools/distribute_test.mjs`.

## Power earmark
The 2026-09-01 USB resets were power (user, 2026-11-15). The fleet adds radio traffic (status
polls, unicast `code_push`, up to 3 transfers at once) but never with the NFC field on. **If the
Box resets silently during a scan or distribute, on USB or on battery, stop adding features,
reopen `2026-09-01-bbox-usb-reboots.md` and record the `reset_log.py` lines there.**

## Range at reduced TX power (added 2026-11-16)
`bbox_server.py` sets `TX_POWER_DBM = 8` because full power reset the Box on USB mid-transfer
(PWRON); it stays at 8. That value was chosen for wands held next to the Box. **Scan, find and
distribute range from a Box at 8 dBm is unmeasured**: fleet commands are meant to reach wands across a
room, not at arm's length. The S12 bench block measures it: scan and distribute to two wands at
table distance, then from across the room, and once with the Box on battery.

Also 2026-11-16: `arm` and `disarm` are back in `bbox_server.py` as accepted no-ops (reply ok,
change nothing), as on the Dial; `tools/test_box_serve.py` checks them.

## Hardware, 2026-11-16/17 (unattended, `Bag3/STRESS_TEST_UNATTENDED_2026-11-16.md`)
The log shows, on USB at arm's length with one wand:
- `fleet.scan` 10/10; distribute and slots pass.
- A 60 min soak with scan and distribute alternating every 30 s: scans 59/60, distributes 58/60
  (2 `no_ack`). **No Box reset**; longest heartbeat gap 7 s; `info.mem` flat at 8.164–8.168 MB;
  uptime about 3.3 h by the end.

This Box has a PN532 fitted, so `identify` gives `nfc: false` (the firmware expects a WS1850S).
Range and battery are still unmeasured.
