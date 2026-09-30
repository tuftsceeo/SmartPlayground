# Game transfer: WiFi vs ESP-NOW vs NFC-DEP — 2026-09-30

One wand (wand B) received the same files over all three transports, from its idle loop to
`game_start`. One session, 5 runs per size per mode.

## Setup

| Item | Value |
|---|---|
| Wand B (receiver) | MockWand, ESP32-C6. WiFi: stock `MockWand/` (`DEBUG_PULL = True`). ESP-NOW and NFC-DEP: `EspnowModem/MockWandEUM/` |
| WiFi sender | Broadcast Dial, host_id `5094`, stock `BDialFirmware`, armed with the JSON `arm` command |
| ESP-NOW sender | Wand A (MockWand) running `EspnowModem/host/code_sender.py` over its own radio, no modem |
| NFC-DEP sender | Wand A as DEP target; PN532 faces touching. 400 kHz I2C, 424 kbps, 240-byte chunks |
| Files | `make_speed_games.py`: `speed05/20/28/32/36/40`, exactly 5–40 KB |
| Driver | `tools/devtests/xfer_bench.py`, wand A side `tools/devtests/xfer_host.py` |
| Trigger | WiFi: `pull_flag.set_pending()` + `machine.reset()` typed at the REPL (what a getcode tap writes). ESP-NOW / NFC-DEP: the `REMOTE_GETCODE` broadcast from wand A (`"via":"nfc"` for NFC-DEP) |

Every line was stamped on the host clock (ms). `total_s` runs from the trigger (WiFi: reset sent;
wand-to-wand: wand B's `# getcode via`) to wand B's `{"type": "game_start"}`. Raw logs are local
only (`tools/devtests/out/xfer/`), not committed.

## Results

Trigger → `game_start`, median of 5 [min–max]. All 5 passed unless noted.

| Size | ESP-NOW | NFC-DEP | WiFi |
|---|---|---|---|
| 5 KB | 3.10 [3.06–3.28] | 7.03 [7.01–7.84] | 31.46 [30.00–33.12] |
| 20 KB | 3.50 [3.34–6.13] | 16.25 [15.52–19.43] | 30.93 [26.32–34.60] |
| 28 KB | 4.30 [3.79–4.34] | 21.99 [21.87–23.76] | 31.02 [29.97–35.32] |
| 32 KB | 4.23 [3.93–6.75] | 24.03 [23.98–24.46] | 33.86 [32.25–36.63] |
| 36 KB | 4.79 [4.43–5.06] | 27.04 [25.86–29.66] | 31.87 [29.13–35.60] |
| 40 KB | 0/5 | 0/5 | 1/5 (32.15) |

Body time (first to last byte), median, ms:

| Size | ESP-NOW | NFC-DEP | WiFi |
|---|---|---|---|
| 5 KB | 279 | 3300 | 1148 |
| 20 KB | 906 | 12989 | 2146 |
| 28 KB | 1239 | 18146 | 2975 |
| 32 KB | 1384 | 20708 | 3441 |
| 36 KB | 1565 | 23275 | 3692 |
| Rate at 36 KB | 23.0 KB/s | 1.5 KB/s | 9.8 KB/s |

Fixed time outside the body, median:

| Step | ESP-NOW | NFC-DEP | WiFi |
|---|---|---|---|
| Trigger → receiving | 0.6–0.7 s | 1.0–1.2 s | 12.6–14.9 s (reboot ~6 s, join ~7 s) |
| Promoted → `game_start` | 1.25–1.31 s | 1.27–1.32 s | 13.3–14.6 s (reset + full boot) |

## 40 KB

- **All three modes fail at `compile()`, after a complete transfer.** Every body arrived in full.
  - ESP-NOW and NFC-DEP: `too large to compile here (40960 B source, ~184–194 KB gc free): memory allocation failed, allocating 40192 bytes`.
  - WiFi: `does not compile: memory allocation failed, allocating 40448 bytes` in 4 of 5 runs. 1 run passed.
- **The wand kept its previous game every time.**
- **Largest free internal block before compile:** 40,960 B in every ESP-NOW and NFC-DEP run.
- **The per-game limit is therefore between 36 and 40 KB on this wand, for every transport.**

## NFC-DEP first attempt

The first NFC-DEP run passed 2 of 5 transfers at 5 KB, then stopped:
- **What wand B did:** logged the "stop" broadcast before each trigger, but never `# getcode via nfc`.
- **What wand A did:** waited 60 s as a DEP target each time, then gave up.
- **Change:** wand A's delay before becoming a target went from 300 ms to 1500 ms (`TARGET_DELAY_MS`), and its target wait was capped at 10 s.
- **After the change:** all 30 runs completed with the expected results.

The likely cause, not confirmed, is that wand B's idle card poll found wand A as a card and never
handled the trigger.

## Differences from earlier reports

- **WiFi end to end is ~31 s, not the ~16 s estimated in `2026-09-30-pull-speed-results.md`.**
  The second boot, from `pull OK` to `game_start`, took 13–15 s.
- **WiFi 5 KB body time was 1148 ms here, 841 ms on 09-30.** Same Dial.
- **ESP-NOW body rate is ~23 KB/s, against ~10 KB/s in `2026-09-26-eum-bench-results.md`.** That
  bench sent through a UART modem; here wand A sent over its own radio.

## Not covered

- **Dial as ESP-NOW sender:** not tested. `BDialEUM` needs a modem and has not run on hardware.
- **Real games:** only comment-padded speed files were sent, which compile cheaply.
- **Sizes between 36 and 40 KB.**
- **More than one wand receiving at once.**
- **Distance and lift tests for NFC-DEP:** wands touching throughout.
- **NFC-DEP verify time rose by ~120 ms per run** within each size (e.g. 971 → 1491 ms at 5 KB).
  Not investigated.
