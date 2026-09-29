# Splat Companion bring-up results, 2026-09-29

Branch `claude/bag3-companion-onboarding-review-nrv66u`. Hub and modem are both XIAO ESP32-C6 on plain MicroPython, with one Splat (`AB:42:00:00:62:2F`) and one Bag3 MockWand. No repo code was edited. Only the user can confirm what LEDs and Splats did, so every visual result below is marked as user-reported.

## Bench stages 1-4 (`Companion/bench/`)

| Stage | Result | Evidence |
|---|---|---|
| Modem flash and boot line | Boot line **not observed** | The monitor attached after the reset. The board's `main.py` is byte-identical to `ESPNowModem/main.py` (`UART_TX = 16`, `UART_RX = 17`). The modem MAC in stage 1 shows it running. |
| 1 Modem link | PASS | `PASS: 10/10 broadcasts accepted by the modem`, modem MAC `A0:F2:62:85:A9:9C`. Stats through tx #30: `modem_crc_err` 0, `host_crc_err` 0, `host_timeouts` 0. |
| 2 LED ring | PASS (user-reported) | Script reached `DONE` with no errors. User said "leds look good". |
| 3 BLE Splat | PASS | `PASS: 1 Splat(s) ready`, `presses per unit [19], write failures 0`. Runs 1 and 2 recorded 0 presses because nobody pressed. Run 1 needed a connect retry (`attempt 1 not ready after 20000 ms`, `cancel connect failed: [Errno 120] EALREADY`). |
| 4 NFC | PASS (user's call) | I2C scan `['0x24']`, `PN532 firmware 1.6 (IC 0x32)`. Only `stop` and `getcode:apple_button@5094` decoded. No `splatwhack` command was seen, and 5 of 9 reads returned None. |

## Full hub firmware boot

All expected boot lines were present: `[hubtype] splat_companion (12 LEDs)`, PN532 firmware line, `ESPNow(EUM): active`, `Splats configured: 1`, the identity JSON, and `Companion: Splat 0 (...) ready` (5.7 s to 21.6 s after boot).

- `[WARN] Battery:` with a caught `OSError: [Errno 19] ENODEV` in `lib/max17048.py`. It appears on every boot. The MAX17048 does not answer on I2C. Boot still completes.

## jumpin: wand and Splat echo

Paper remote sent `jumpin` and `stop`. Hub and wand logs were captured separately.

| Check | Expected | Seen |
|---|---|---|
| Hub start | `ESP-NOW start_game: jumpin`, `game_start` | PASS |
| Hub stop | `exit on stop`, `game_end` | PASS |
| Wand presses on hub | `wand pressed` | Matched the wand's `Button pressed!` 1:1 in every window |
| Splat presses on wand | `Splat pressed` | Matched the hub's `Splat pressed` 1:1 in every window |
| Press after stop | nothing logged | Nothing logged after either stop |

Press counts exceeded the requested 3 in some windows (5 wand and 6 Splat in the first run), so the user pressed more than asked. User reported "it looks good" for the blinks and for the Splat staying dark after stop. The delay in each direction was not given, and cross-board log timestamps use separate monitor clocks, so latency can't be derived from the logs.

## Findings

1. **`set_last_pulled('splatwhack')` cannot launch a built-in game.** `game_store.take_last_pulled()` only returns a slug if `game_store.exists(slug)` finds `/games/<slug>.py`. `splatwhack` lives at `/`, so the queued name is read, deleted and discarded. The `/games` copy used to work around it was removed afterwards.
2. **Wand restarts `jumpin` right after each start.** It logs `Stop detected` and `game_end` about 0.2 s after `game_start`, then starts again. Seen at 106.5 s and 131.3 s in the session logs. Cause not investigated.
3. **`Reset via broadcast` and repeated stops.** After each stop the wand logged `Reset via broadcast` and the hub logged `Companion: stop from 5C:01:3B:0D:BE:94`. The last stop was repeated 3 times, which looks like the remote resending it.
4. **MAX17048 battery gauge not answering** (see the boot section above).
5. **`bench/4_nfc.py` gives no feedback on a successful card read**, so hold time can't be judged by hand.

## Not run

Full-firmware `splatwhack` game, `DEBUG_PROBE` idle capture (`max_step_gap_ms`, `host_idf_largest`, and so on), and the Splat power-cycle reconnect test. The modem boot line was never seen live.

## Session notes

- `/dev/cu.usbmodem1101` was briefly holding modem firmware. The user swapped the USB cables to fix it. Confirm which physical board is which before the next session.
- Thonny once held the hub port during the jumpin run and was closed by the user.
