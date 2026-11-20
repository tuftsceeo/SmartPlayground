# MiniSplatCompanion

A one-to-one gateway between **one Splat** (BLE) and the playground (ESP-NOW), on one
XIAO ESP32-C6 with a battery and 3 NeoPixels. It behaves like a very small wand: it pulls
games from the Broadcast Box/Dial, runs them with the Wand's game contract, and hands each
game the Splat as its `splats` argument.

**Status: written and `py_compile`d only. Never run on hardware.** Nothing here was
flashed or tested on a board.

## What it is (and isn't)

- **Selective fork of `Wand Module/`, not a trim of it.** `main.py` is new and slim; `lib/`
  is byte copies of Wand libs (below). `Wand Module/` and this tree are independent —
  divergence is expected, and a change to one is not applied to the other.
- **Not** `Stations/SplatCompanion/` (the historical 4-Splat station with an ESP-NOW modem
  board) and **not** the Bag2 Splat Companion.
- Experiment: not a classroom device and not for teachers.

## Files

| Path | What |
|---|---|
| `main.py` | Boot (radio prewarm, ESP-NOW, MAX17048, Splat), idle loop, game launch, ESP-NOW code pull, status pixels, JSON `identity`/`heartbeat`/`game_*`/`pull`/`error` lines |
| `mini_splat.py` | `MiniSplat` (one `SplatHub`/`SplatGroup`, optional pinned MAC) and `GameSplats` (the `splats` game argument; same shape as the Wand's) |
| `stubs.py` | `NullNfc`, `NullBuzzer`, `NullAccel` handed to games in place of missing hardware |
| `jumpin.py` | Test game, `SPLATS_LOCAL = 1`. One Splat: random color + animal sound on press |
| `hubtype.txt` / `lib/hubtype.py` | `splat_mini`: 3 LEDs on GPIO20, I2C 22/23 at 400 kHz. Own file, not a copy |
| `lib/*.py` | Byte copies from `Wand Module/lib/` (except as noted) |

`lib/` copies: `espnow_manager`, `espnow_code`, `game_store`, `game_slots`, `splat_hub`,
`splat_link`, `splat_api`, `ble_splat`, `max17048`, `memprobe`, `stdin_drain`, `leds`,
`brightness`, `signals`, `battery`, `nfc_reader`, `pn532`.

- **`lib/espnow_manager.py` is no longer a byte copy**: line 39 `EXTERNAL_ANTENNA = True` →
  `False`. This board uses the onboard antenna (AGENTS.md default); the Wand's u.FL is not
  fitted here. `main.py`'s prewarm sets GPIO14 = 0 to match. That is the only difference.
- `lib/splat_api.py` is the source of truth for `ChatBroadcast/tools/sync_splat_actions.py`.
  Do not edit this copy; edit the Wand's and re-sync.
- `nfc_reader.py` / `pn532.py` are carried only because `game_store.py` imports from
  `nfc_reader`. `memprobe.py` and `signals.py` are copied but nothing in `main.py` calls them.

## Behaviour

- **Boot:** prewarm ESP-NOW (onboard antenna), then BLE, **before any other import**; then
  `ESPNowManager.init()`, MAX17048 (optional), then the Splat link. BLE-first fails with
  `WiFi Out of Memory` (see `known_issues/2026-11-12-splat-host-v129-firmware.md`).
- **Splat link:** first Splat advertising by name, or the one in `/splat_mac.txt`
  (`AB:42:00:00:7E:B6`, optional). Reconnects by address if dropped. Discovery scanning is
  paused while a game runs (it starved ESP-NOW on the C6).
- **Status pixels:** 0 ESP-NOW (dim green up, amber down) · 1 Splat (blue linked, amber
  blinking while searching) · 2 battery color (blinks at ≤10 %).
- **Idle:** answers ESP-NOW `stop`, `start_game` (by name), `battery`, `code_push`.
  A Splat press at idle flashes white.
- **Code pull:** a Dial/Box `code_push` triggers `espnow_code.receive()`, then the game
  launches. There is no NFC, so no `getcode` card. The pull path is the Wand's.
- **Games:** wand contract `play(nfc, leds, buz, accel, i2c, enow, batt, net)`, tolerating
  6/7-arg games. `nfc`, `buz`, `accel` are stubs. `SPLATS_LOCAL = 1` games get the Splat in
  the 8th argument and are refused (amber flashes) if it is not connected.
- **Not supported:** lobby/host games (`SPLAT_HOST`, `SPLATS_MIN`, `PLAYERS_MIN`) and
  `SPLATS_LOCAL = 2`. They are refused with an `error` line, not run.

## Pull hub and status kind

`BBoxFirmware`/`BDialFirmware` `code_sender.py` `ROLE_FILES` only serve hub `wand` (or `""`)
and `icon_display`; any other hub type is refused. So this device **requests as `"wand"`**
(`PULL_HUB`) and reports `kind="wand"` in `status_poll` (`STATUS_KIND`), while
`hubtype.txt` and the `identity` line say `splat_mini`. Consequences:

- The Box/Dial and ChatBroadcast see it as a wand. A game generated for the wand contract
  works; one that needs the 5×5 matrix will draw on 3 pixels (shapes are bounds-checked).
- ChatBroadcast's direct-USB push probably refuses it (hub ≠ `wand`). Not tried.
- Whether `status_poll` with a spoofed kind confuses the Dial's device list is unknown;
  see `known_issues/2026-10-23-distribute-code.md` (`status_poll` `kind`).

## Assumed, not confirmed

You did not confirm these; they are defaults taken from the Bag2 board and the Wand:

- **Battery = MAX17048 on I2C 22/23.** You expected an ADC divider; the Bag2 board used a
  MAX17048, so that is what this reads. If the board has a divider instead, boot prints
  `[WARN] Battery` and the device runs with no battery reporting (`status_poll` gives `None`).
- **NeoPixels on GPIO20, 3 of them.**
- **Onboard antenna** (GPIO14 = 0).

## Known issues that apply (cited, not worked)

- `known_issues/2026-11-12-splat-host-v129-firmware.md` — Splat BLE needs MicroPython
  **v1.28.0**, not v1.29.
- `known_issues/2026-11-17-splat-host-push-dropped.md` — pushes to a Splat-hosting device can
  be dropped. This tree does not try to fix it.
- `known_issues/2026-10-23-distribute-code.md` — pull/`status_poll` behaviour.
- `known_issues/2026-11-17-wand-ctrlc-stdin-full.md` — why `stdin_drain` is called every loop.

## Open risks (unverified)

- A discovery scan runs at high duty cycle while no Splat is found; on the C6 that can starve
  ESP-NOW (the Wand hit this). Nothing throttles it here before the first connect.
- One radio shares BLE and ESP-NOW. The coex bench held 1–2 Splats with broadcast loss of
  roughly 2–15 %; this is a 1-Splat build, untested here.
- `code_push` arriving mid-game ends the game and pulls; not exercised.

## Deploy

Read `Bag3/Code/HARDWARE_PROTOCOL.md` first. Use `mpremote ... resume` for every call.
Needs MicroPython **v1.28.0** for the C6. Copy `main.py`, `jumpin.py`, `stubs.py`,
`mini_splat.py`, `hubtype.txt` to the root and `lib/` to `/lib`. `main.py` runs on boot
(no `boot.py`); a 2 s Ctrl-C window opens at boot, and `stdin_drain` keeps Ctrl-C
working in the main loop.
# MiniSplatCompanion

A one-to-one gateway between **one Splat** (BLE) and the playground (ESP-NOW), on one
XIAO ESP32-C6 with a battery and 3 NeoPixels. It behaves like a very small wand: it pulls
games from the Broadcast Box/Dial, runs them with the Wand's game contract, and hands each
game the Splat as its `splats` argument.

**Status: written and `py_compile`d only. Never run on hardware.** Nothing here was
flashed or tested on a board.

## What it is (and isn't)

- **Selective fork of `Wand Module/`, not a trim of it.** `main.py` is new and slim; `lib/`
  is byte copies of Wand libs (below). `Wand Module/` and this tree are independent —
  divergence is expected, and a change to one is not applied to the other.
- **Not** `Stations/SplatCompanion/` (the historical 4-Splat station with an ESP-NOW modem
  board) and **not** the Bag2 Splat Companion.
- Experiment: not a classroom device and not for teachers.

## Files

| Path | What |
|---|---|
| `main.py` | Boot (radio prewarm, ESP-NOW, MAX17048, Splat), idle loop, game launch, ESP-NOW code pull, status pixels, JSON `identity`/`heartbeat`/`game_*`/`pull`/`error` lines |
| `mini_splat.py` | `MiniSplat` (one `SplatHub`/`SplatGroup`, optional pinned MAC) and `GameSplats` (the `splats` game argument; same shape as the Wand's) |
| `stubs.py` | `NullNfc`, `NullBuzzer`, `NullAccel` handed to games in place of missing hardware |
| `jumpin.py` | Test game, `SPLATS_LOCAL = 1`. One Splat: random color + animal sound on press |
| `hubtype.txt` / `lib/hubtype.py` | `splat_mini`: 3 LEDs on GPIO20, I2C 22/23 at 400 kHz. Own file, not a copy |
| `lib/*.py` | Byte copies from `Wand Module/lib/` (except as noted) |

`lib/` copies: `espnow_manager`, `espnow_code`, `game_store`, `game_slots`, `splat_hub`,
`splat_link`, `splat_api`, `ble_splat`, `max17048`, `memprobe`, `stdin_drain`, `leds`,
`brightness`, `signals`, `battery`, `nfc_reader`, `pn532`.

- **`lib/espnow_manager.py` is no longer a byte copy**: line 39 `EXTERNAL_ANTENNA = True` →
  `False`. This board uses the onboard antenna (AGENTS.md default); the Wand's u.FL is not
  fitted here. `main.py`'s prewarm sets GPIO14 = 0 to match. That is the only difference.
- `lib/splat_api.py` is the source of truth for `ChatBroadcast/tools/sync_splat_actions.py`.
  Do not edit this copy; edit the Wand's and re-sync.
- `nfc_reader.py` / `pn532.py` are carried only because `game_store.py` imports from
  `nfc_reader`. `memprobe.py` and `signals.py` are copied but nothing in `main.py` calls them.

## Behaviour

- **Boot:** prewarm ESP-NOW (onboard antenna), then BLE, **before any other import**; then
  `ESPNowManager.init()`, MAX17048 (optional), then the Splat link. BLE-first fails with
  `WiFi Out of Memory` (see `known_issues/2026-11-12-splat-host-v129-firmware.md`).
- **Splat link:** first Splat advertising by name, or the one in `/splat_mac.txt`
  (`AB:42:00:00:7E:B6`, optional). Reconnects by address if dropped. Discovery scanning is
  paused while a game runs (it starved ESP-NOW on the C6).
- **Status pixels:** 0 ESP-NOW (dim green up, amber down) · 1 Splat (blue linked, amber
  blinking while searching) · 2 battery color (blinks at ≤10 %).
- **Idle:** answers ESP-NOW `stop`, `start_game` (by name), `battery`, `code_push`.
  A Splat press at idle flashes white.
- **Code pull:** a Dial/Box `code_push` triggers `espnow_code.receive()`, then the game
  launches. There is no NFC, so no `getcode` card. The pull path is the Wand's.
- **Games:** wand contract `play(nfc, leds, buz, accel, i2c, enow, batt, net)`, tolerating
  6/7-arg games. `nfc`, `buz`, `accel` are stubs. `SPLATS_LOCAL = 1` games get the Splat in
  the 8th argument and are refused (amber flashes) if it is not connected.
- **Not supported:** lobby/host games (`SPLAT_HOST`, `SPLATS_MIN`, `PLAYERS_MIN`) and
  `SPLATS_LOCAL = 2`. They are refused with an `error` line, not run.

## Pull hub and status kind

`BBoxFirmware`/`BDialFirmware` `code_sender.py` `ROLE_FILES` only serve hub `wand` (or `""`)
and `icon_display`; any other hub type is refused. So this device **requests as `"wand"`**
(`PULL_HUB`) and reports `kind="wand"` in `status_poll` (`STATUS_KIND`), while
`hubtype.txt` and the `identity` line say `splat_mini`. Consequences:

- The Box/Dial and ChatBroadcast see it as a wand. A game generated for the wand contract
  works; one that needs the 5×5 matrix will draw on 3 pixels (shapes are bounds-checked).
- ChatBroadcast's direct-USB push probably refuses it (hub ≠ `wand`). Not tried.
- Whether `status_poll` with a spoofed kind confuses the Dial's device list is unknown;
  see `known_issues/2026-10-23-distribute-code.md` (`status_poll` `kind`).

## Assumed, not confirmed

You did not confirm these; they are defaults taken from the Bag2 board and the Wand:

- **Battery = MAX17048 on I2C 22/23.** You expected an ADC divider; the Bag2 board used a
  MAX17048, so that is what this reads. If the board has a divider instead, boot prints
  `[WARN] Battery` and the device runs with no battery reporting (`status_poll` gives `None`).
- **NeoPixels on GPIO20, 3 of them.**
- **Onboard antenna** (GPIO14 = 0). Unconfirmed: Bag2's `espnow_manager.py` selects external
  (GPIO3 = 0, GPIO14 = 1) for its Splat Companion, but that does not show a u.FL antenna is
  fitted. Whether this enclosure carries one is not known; see "Antenna range test".

## Known issues that apply (cited, not worked)

- `known_issues/2026-11-12-splat-host-v129-firmware.md` — Splat BLE needs MicroPython
  **v1.28.0**, not v1.29.
- `known_issues/2026-11-17-splat-host-push-dropped.md` — pushes to a Splat-hosting device can
  be dropped. This tree does not try to fix it.
- `known_issues/2026-10-23-distribute-code.md` — pull/`status_poll` behaviour.
- `known_issues/2026-11-17-wand-ctrlc-stdin-full.md` — why `stdin_drain` is called every loop.

## Open risks (unverified)

- A discovery scan runs at high duty cycle while no Splat is found; on the C6 that can starve
  ESP-NOW (the Wand hit this). Nothing throttles it here before the first connect.
- One radio shares BLE and ESP-NOW. The coex bench held 1–2 Splats with broadcast loss of
  roughly 2–15 %; this is a 1-Splat build, untested here.
- `code_push` arriving mid-game ends the game and pulls; not exercised.

## Antenna range test

Run at bring-up, only if a u.FL antenna is physically fitted to the board.

1. **Inspect** the board for a u.FL connector and antenna. If none is fitted, keep the default
   and skip this test.
2. **Record** ESP-NOW reception at a fixed distance and orientation with `EXTERNAL_ANTENNA = False`
   (`lib/espnow_manager.py`, line 39).
3. **Set** `EXTERNAL_ANTENNA = True`, redeploy, and repeat at the same distance and orientation.
4. **Keep** the setting with the better reception and note it here.

## Deploy

Read `Bag3/Code/HARDWARE_PROTOCOL.md` first. Use `mpremote ... resume` for every call.
Needs MicroPython **v1.28.0** for the C6. Copy `main.py`, `jumpin.py`, `stubs.py`,
`mini_splat.py`, `hubtype.txt` to the root and `lib/` to `/lib`. `main.py` runs on boot
(no `boot.py`); a 2 s Ctrl-C window opens at boot, and `stdin_drain` keeps Ctrl-C
working in the main loop.
