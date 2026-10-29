---
title: Status scan and Dial "Distribute code" — plan deviations and device differences
date: 2026-10-23
status: open (untested on hardware)
devices: [BroadcastDial, BroadcastBox, MockWand, IconDisplay, M5Paper Remote, Bag2 wands]
components: [BDialFirmware/fleet.py, espnow_manager code_push/status_report, ChatBroadcast distribute overlay, Bag3 M5Paper Remote]
code:
  - Bag3/Code/BroadcastCode/BroadcastDial/BDialFirmware/fleet.py
  - Bag3/Code/BroadcastCode/BroadcastDial/BDialFirmware/bdial_server.py
  - Bag3/Code/BroadcastCode/BroadcastDial/BDialFirmware/code_link.py
  - Bag3/Code/BroadcastCode/BroadcastDial/BDialFirmware/station_ui.py
  - Bag3/Code/BroadcastCode/MockWand/main.py
  - Bag3/Code/BroadcastCode/MockWand/lib/espnow_manager.py
  - Bag3/Code/BroadcastCode/IconDisplay/main.py
  - Bag3/Code/BroadcastCode/IconDisplay/lib/espnow_manager.py
  - Bag3/Code/BroadcastCode/ChatBroadcast/js/distribute.js
  - Bag3/Code/TeacherTools/M5Paper Remote/
open:
  - Nothing here has run on hardware
  - IconDisplay ignores code_push while a game runs
  - IconDisplay has no finddevice game, so Find shows nothing on it
  - IconDisplay is marked updated before its icons arrive
  - No back-hold cancel on the Dial during a distribution
  - Devices that ACK code_push but cannot act on it report "timeout", not a clear error
keywords: [code_push, status_poll, status_report, kind, fleet, distribute, find_device, finddevice, getcode, timeout, no_ack, not_serving, M5Paper]
related:
  - Bag3/Code/BroadcastCode/docs_and_design/2026-10-23-distribute-code-plan.md
  - Bag3/Code/BroadcastCode/BroadcastDial/README.md (Fleet commands)
---

# Status scan and Dial "Distribute code", 2026-10-23

This note covers the flow added in commits `2d0688d`, `c984d1b` and `dc61a1a`:
1. A status reply now carries `kind`.
2. The Dial's `fleet.*` serial commands scan, find and distribute.
3. Devices handle `code_push`.
4. ChatBroadcast has a "Distribute code" overlay.

So far the only checks are `py_compile`, host tests (`BDialFirmware/tools/test_fleet.py`,
`test_dial_station.py`) and app tests (`ChatBroadcast/tools/distribute_test.mjs`, a UI smoke test, and
a headless overlay render against a fake Dial). **None of this has been tested on hardware.**
Every item below is expected from reading the code, not observed.

## Deviations from the plan

1. **No back-hold cancel on the Dial.** The progress ring and its count draw on LVGL's top layer over the
   normal menus, so the Dial stays in a serving mode and the radio stays up. A back-hold just navigates
   the menus. A distribution ends only in these ways:
   - all devices finish
   - the app sends `fleet.cancel`; closing the overlay mid-run sends it
   - the Dial leaves the menus (card scan or write, Read, keyboard, result screen), which cancels with
     `why: "radio_off"`
2. **Moved to Stage 2.** The `code_push` receive side was planned for Stage 1 and was built in Stage 2.
3. **Pull toast now fires.** Adding `pull` to `FORWARDED_EVENTS` (needed for progress) makes the
   per-pull toast in `app.js` fire for the first time. That handler was there before but never ran. A
   distribution now gives one toast per device, and so does every card-tap pull while the app is
   connected.
4. **Broadcast Box not changed.** `bbox_server.py` is the Dial server's peer, but it has no `fleet.*`.
   The app hides "Distribute code" unless `identity.device` is `broadcast_dial`.
5. **IconDisplay reports battery `None`.** Its status provider is `lambda: None`, so the app shows "—"
   and the remote shows unknown battery.

## Device differences

### IconDisplay
- **Ignores `code_push` mid-game.** `code_push` is handled only in the idle loop of `IconDisplay/main.py`.
  `_launch_game` loops do not route it. The Dial gets a MAC-layer ACK, so the row shows "pulling" and
  then fails with `timeout` after 30 s. On a MockWand the same message stops the game and pulls (via
  `_StartGameCapture` → `_pending_push`).
- **Find shows nothing.** `espnow_manager` rewrites `find_device` into `start_game finddevice`, but
  IconDisplay has no `finddevice` game, so it prints "no game 'finddevice' on this display" and stays
  idle. This applies to Find in the app and on the M5Paper Remote.
- **Marked updated too early.** The Dial counts a device as done on its game-file `code_done`.
  `code_sender` does not put icon transfers in `last_result`, so the row reads "Updated" while icons
  are still coming in, and an icon that fails never reaches the app.
- **Resets after a good pull.** `machine.reset()` runs on success. The display drops off the radio for
  a few seconds, so a scan straight after a distribution can miss it.
- **No rxbuf set.** IconDisplay's `espnow_manager` leaves the default rxbuf (MockWand uses 4096). A
  status reply or `code_push` arriving during its own pull has not been tested.

### MockWand
- **Game must poll.** `code_push` only reaches the wand inside a game if that game calls `enow.poll()`
  through the `_StartGameCapture` wrapper. A game that blocks without polling, for example in a long
  animation or sound, misses it and times out.
- **Interrupts play.** A pushed wand ends the current game and launches the new one right away. Nothing
  asks first.
- **Repeated pushes.** Only one push is held. A second `code_push` that arrives before the idle loop runs
  overwrites the first; the latest slug and host win. A `code_push` that arrives *during*
  `espnow_code.receive` is consumed by the receiver and dropped.
- **Always answers polls.** When there is no battery gauge it registers `lambda: None` so it still
  answers polls. Before this change such a wand did not reply.

### Wands and devices without the change
- **No `kind` from other trees.** These copies do not send `kind` and do not handle `code_push`:
  - Bag2 wands
  - `Bag3/Code/Wand Module`
  - `Bag3/Code/lib`
  - Music Board Station
  - SplatCompanion
  - EspnowModem
  - the `Simulator/vendor/` copies, which now differ from MockWand and IconDisplay
- **Bag2 devices on the same channel.** They answer `status_poll` without `kind`, and appear as `?-xxxx`
  with kind "Unknown". If one is selected, it ACKs `code_push`, ignores it, and times out.
- **No reply at all.** Devices with no status provider (Music Board, SplatCompanion) never appear in
  the list.

### BroadcastDial
- **Radio must be up.** `fleet.*` needs the radio up: WRITE mode (a game on flash) on a menu screen.
  Otherwise the command answers `error not_serving`. After a send the Dial reboots. The app waits up to
  30 s for the link to come back and then scans; if the Dial is not on a menu screen yet, the scan
  fails and the user has to press Rescan.
- **One radio message per loop.** `CodeLink.poll` handles one radio message per main-loop pass, and the
  rxbuf is 1024 B. Status replies are spread over 16 slots (400 ms + (last MAC byte % 16) × 180 ms).
  Two devices whose MACs share a slot reply at the same moment. Each sends twice, 120 ms apart, which
  covers most collisions. With many devices, replies can still be lost from the rxbuf.
- **Scan window.** It is fixed at 6 s, and replies after it are dropped. A wand mid-pull or in a
  non-polling game may answer late or not at all.
- **Pacing.** One push every 2.5 s, at most 3 pushed devices unfinished at once. Pulls triggered by card
  taps share `MAX_SESSIONS = 6` with these and are not counted against the 3, so heavy card use during
  a distribution can bring "busy" offers. The wand retries a busy offer by itself, but every retry
  counts against the 30 s timeout.
- **30 s timeout.** It is measured from the push, not from the start of the transfer. A large game, a
  busy retry or a slow link can be a real success that is reported as `timeout`; the device still gets
  the game.
- **`no_ack` vs `timeout`.** `no_ack` means the device was out of range or off. `timeout` covers
  everything else: no handler, a game that ignored the push, a failed pull with no `code_done`. A
  failed `code_done` reports its own `why`.
- **Slug.** The app sends the base slug, and the Dial checks it against `_index`. A game with no wand
  file (for example icon-only) may not be in `_index`, which gives `unknown_slug`. Each device pulls
  its own role file (`<slug>.py` for a wand, `<slug>_icon.py` for an IconDisplay). A role whose file
  is missing fails on that device.
- **Progress label.** It sits at y=60 on the top layer and can cover list text below the centre.

### RSSI meaning
- **Who measures it.** `rssi` in `status_report` is how strongly the device heard the poller (Dial or
  remote), measured by the device. The Dial and the remote do not measure it themselves. If the device
  has no `peers_table` entry for the poller, the value is null.

### M5Paper Remote (Bag3)
- **Only two kinds.** `KIND_PREFIX` covers `wand` and `icon_display`. Any other `HUB_TYPE` shows `?-`.
- **Doesn't reply.** The remote never registers a provider, so it does not answer polls itself.
- **Bag2 copy.** `Bag2/Code/M5Paper Remote` is unchanged and ignores `kind`, labelling every row `W-`.

### ChatBroadcast
- **Reconnect.** The overlay attaches its listeners to `app.device` when it scans. If a reconnect
  replaces the link object mid-distribution, progress stops updating until the next Rescan. The Dial
  keeps going regardless.
- **Closing mid-run.** Closing the overlay sends `fleet.cancel`. Devices already pulling still finish
  and still launch the game, but the Dial reports them as `cancelled`.
