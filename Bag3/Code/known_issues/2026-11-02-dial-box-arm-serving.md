---
title: Broadcast Dial and Box still gate code serving behind arm/disarm
date: 2026-11-02
status: open (from code reading, untested on hardware)
devices: [BroadcastDial, BroadcastBox]
components: [BDialFirmware/bdial_server.py, BDialFirmware/code_link.py, BBoxFirmware/bbox_server.py, BBoxFirmware/code_link.py, BBoxFirmware/bbox_ui.py]
code:
  - Bag3/Code/TeacherTools/BroadcastDial/BDialFirmware/bdial_server.py
  - Bag3/Code/TeacherTools/BroadcastDial/BDialFirmware/code_link.py
  - Bag3/Code/TeacherTools/BroadcastBox/BBoxFirmware/bbox_server.py
  - Bag3/Code/TeacherTools/BroadcastBox/BBoxFirmware/code_link.py
  - Bag3/Code/TeacherTools/BroadcastBox/BBoxFirmware/bbox_ui.py
open:
  - Serving is a separate armed state, not "radio on"
  - Dial radio is down on non-NFC screens (results, keyboard)
  - No game on flash means no serving, and no radio on the Box
  - arm/disarm serial handlers and the "armed" info/mode field remain
keywords: [arm, disarm, armed, serve, serving, radio, code_link, no_payload, nohost, SHARE_IN_MENUS, _serve, _menu_share]
related:
  - Bag3/Code/Experiments/CrowPanel5_Display/code_link.py (panel copy with radio_on/radio_off, commit 784d79f)
  - Bag3/Code/docs_and_design/2026-10-20-espnow-serving/RESULTS.md
---

# Broadcast Dial and Box: arm/disarm serving, 2026-11-02

**Intended behaviour:** the ESP-NOW radio and the code server are on by default. They pause only
while an NFC card is being read or written, then resume. Serving is not a mode, and nothing arms or
disarms it.

The CrowPanel5_Display was changed to this (`784d79f`, `218433b`): its `code_link.py` copy has
`radio_on()`/`radio_off()` and no arm state, and ChatBroadcast no longer sends `arm` or `disarm`.
The Dial and Box were not changed. Everything below is from reading the code, not observed.

## Same failure the CrowPanel had
On the CrowPanel, the radio could be on while the code server was not armed. A wand that got
`code_push` then found no host (red WiFi bars, then the white "!"). The Dial and Box share the
`CodeLink.arm()` structure that allowed this, so the same class of failure is possible wherever
their radio state and armed state can differ.

## BroadcastDial (`bdial_server.py`)
- **Radio down off the menus.** `_serve()` disarms whenever `self.st.serving()` is false. Its
  docstring says the radio is down on Read, scans, results and the keyboard. Results and the
  keyboard are not NFC operations.
- **Needs a game.** `_serve()` arms only in `MODE_WRITE`, and `arm()` fails without a resolvable
  active game, so a Dial with no game on flash does not serve.
- **Leftover commands.** `do_arm` (answers `no_payload` with no game) and `do_disarm` (no-op) are
  still in the dispatch table. `info` and `do_arm` report `"armed": self.code.armed`.

## BroadcastBox (`bbox_server.py`)
- **Needs a flag and a game.** `_menu_share()` arms only when `SHARE_IN_MENUS` is set, the Box is
  in `MODE_WRITE`, the NFC field is off, and a game resolves.
- **NFC disarms.** `_nfc_field(True)` disarms, which matches the intended rule. Re-arming then
  waits for `_menu_share()` and its conditions above.
- **Leftover commands.** `do_arm`, `do_disarm`, and `"armed"` in `info`/`mode`, as on the Dial.
- **Wording.** `bbox_ui.py` has `paint_armed()`; it paints the "Hold Near Reader" tag-write
  screen, so the name is internal only.

## Fix direction
Port the CrowPanel change: `code_link.py` with `radio_on()`/`radio_off()` and no arm state; the
radio turns off only around an NFC read or write and comes straight back; drop `do_arm`,
`do_disarm` and the `"armed"` field. The two `code_link.py` copies are maintained separately, so
each needs its own change.
