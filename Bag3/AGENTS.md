# Bag3/AGENTS.md — Wand module firmware

Hardware is in flux and new boards are on order. Treat any hardware detail as possibly stale.

Before opening a serial port or running `mpremote` against ESP32 hardware (the Wand, Box, Dial,
or any other M5 prototype), read [Code/HARDWARE_PROTOCOL.md](Code/HARDWARE_PROTOCOL.md).

## Current hardware config

`Bag3/Code/lib/hubtype.py` is the live source for pin maps, LED geometry, and I2C addresses — read it
rather than relying on documentation, and ask if the code and the board in front of you disagree.

A 5×5 + PN532 @ 0x24 variant was explored on `origin/claude/pn532-5x5` and not merged.

## Broadcast devices (ChatBroadcast)

| Tree | Device identity | Hardware |
|---|---|---|
| `Code/TeacherTools/BroadcastBox/BBoxFirmware/` | `broadcast_box` | M5 StickS3 + Grove RFID 2 (WS1850S) — fielded prototype |
| `Code/TeacherTools/BroadcastDial/BDialFirmware/` | `broadcast_dial` | M5 Dial 2 (StampS3A) — sibling port; Phase 0 pins still open |
| `Code/Stations/SplatCompanion/` (`Companion/` hub + `ESPNowModem/` modem, two XIAO C6) | `splat_companion` | XIAO ESP32-C6 + PN532 (wand wiring) + MAX17048; BLE to a stock Splat toy, ESP-NOW via a paired EUM modem board over UART (`Code/Experiments/EspnowModem/`); runs on hardware with 4 Splats |

Same serial protocol and wire contract. ChatBroadcast accepts both. Do not silently
reconcile PEER-copied modules between the two trees — fix one copy and say which.

Two more hand-kept sets (paths under `Code/`; fix one copy and say which):

- `espnow_code.py`: `Wand Module/lib/`, `Experiments/EspnowModem/MockWandEUM/lib/` and `Stations/IconDisplay/lib/`.
- `code_sender.py`: `TeacherTools/BroadcastBox/BBoxFirmware/`, `TeacherTools/BroadcastDial/BDialFirmware/` and `Experiments/EspnowModem/host/`.

**Do not add module-scope content to `code_link.py` (Box and Dial).** `bdial_server.py` /
`bbox_server.py` import it before `prewarm()` brings the radio up, and the radio needs one large
contiguous DRAM block that nothing allocated earlier may fragment. A docstring or a format string
added there is allocated at import, ahead of that block, and can make bring-up fail with
`WiFi Out of Memory` at a healthy-looking `gc.mem_free()`. This has cost two sessions.
`code_sender.py` is imported lazily in `CodeLink.arm()`, after the radio is up. Diagnostics belong
in a separate module imported lazily after bring-up. See
[Code/BroadcastCode/docs_and_design/2026-09-23-ap-memory-order.md](Code/BroadcastCode/docs_and_design/2026-09-23-ap-memory-order.md).

## Wand Module

`Code/Wand Module/` is the Mock Wand: the Bag3 wand firmware with `lib/espnow_code.py` for game
pulls from the Broadcast Box and Dial. The earlier Bag3 wand tree is in
`Code/Experiments/Wand Module/`. Built-in games are flat files in `Wand Module/`; a game pulled from
the Box or Dial lands in `/games/<slug>.py` and is discovered at runtime. `utilities/` is
bench-only and never deployed to the device.
