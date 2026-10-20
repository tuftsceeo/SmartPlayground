# Plan: Box and Dial serve game code over ESP-NOW only

Goal: the Broadcast Box and Broadcast Dial send game files to wands over ESP-NOW from their own
radio, with no external modem, and the SoftAP + TCP path (`code_server.py` / `code_puller.py`) is
removed.

## What exists

| Piece | Where | State |
|---|---|---|
| Sender protocol | `EspnowModem/host/code_sender.py` | Receiver-driven windows, sha256, busy/retry, peer cleanup. 11 CPython tests (`EspnowModem/tests/test_code_xfer.py`) |
| Wand receiver | `EspnowModem/MockWandEUM/lib/espnow_code.py` + `main.py` (`CODE_VIA_ESPNOW`) | Receive, check, promote and launch in one boot, no reset. Not in stock `MockWand/` |
| Native-radio sender | `tools/devtests/xfer_host.py` | A C6 wand serving with `code_sender.py` over its own radio: 25/25 to 36 KB, ~23 KB/s (`2026-09-30-transfer-comparison-results.md`) |
| Dial over a modem | `EspnowModem/BDialEUM/`, branch `origin/claude/esp-now-dial` only | Dial radio off, StickS3 modem on UART. Host pinning (`host_id` in `code_req`). Never run on hardware |
| NFC/radio exclusion | `bdial_server.py`, `bbox_server.py` | Invariant: at most one of {WiFi AP, NFC RF field} energized. SERVE = antenna off, no I2C |
| Reset cause log | `reset_log.py` (Box, Dial) | Records `BROWNOUT` and other reset causes across boots |

The modem firmware (`EspnowModem/modem/main.py`) runs `espnow` under UIFlow2 on a StickS3, the
Box's board, so the module is present there. The Dial (StampS3A) is unverified.

## Power rule

The NFC reader's RF field is off whenever the radio transmits. Concretely:

- SERVE mode stays. Entering it calls `antenna_off()`, checks `antenna_is_on()` is False, and stops
  all reader I2C, before the first ESP-NOW send.
- Leaving SERVE stops serving before `antenna_on()`.
- The invariant in both servers' docstrings becomes: at most one of {ESP-NOW serving, NFC RF field}.

This is the current SERVE behaviour with the AP replaced. BDialEUM's always-serving model is not
used, because it leaves the field and the radio on together.

## Phase 0: modem-less spike, no firmware changes

Run as bench scripts over `mpremote resume run`, as `xfer_host.py` is today. One Dial (then one
Box), one MockWandEUM wand, `make_speed_games.py` files at 5, 20, 28, 32 and 36 KB, 5 runs each,
driven by `xfer_bench.py`.

1. **Radio availability.** On the Dial and the Box, after normal boot is interrupted: `import
   espnow`, STA active, `ESPNow().active(True)`. Record `esp32.idf_heap_info` largest block before
   and after.
2. **Sender script.** `tools/devtests/espnow_serve.py`: `code_sender.CodeSender` over a minimal
   native manager (add_peer, send_to, send_raw, remove_peer, poll, broadcast) written against
   `espnow` directly. The MockWand `espnow_manager.py` is not reused as-is: its
   `_configure_antenna()` drives C6 GPIO 3/14.
3. **Antenna off, USB power.** Reader antenna off before the radio starts. Expect the wand-to-wand
   numbers: all pass to 36 KB, ~20+ KB/s.
4. **Antenna on, USB power.** Same runs with the field left on, to see whether the combination
   browns out or corrupts. Read `reset_log.last()` after.
5. **Battery.** Repeat 3 and 4 on battery (Box: StickS3 battery; Dial: its battery if fitted).
6. **Late bring-up.** Start ESP-NOW after the full UI is up (as the firmware would on entering
   SERVE), not first thing on boot, and record whether `active(True)` fails or the largest block
   shrinks. This decides whether the radio must be claimed at boot and kept.

Gate to phase 1: steps 3 and 6 pass on both boards with no `BROWNOUT` in the reset log. Step 4's
result decides whether the power rule can be relaxed later; the plan assumes it cannot.

## Phase 1: Dial firmware

1. `BDialFirmware/code_link.py`: a CodeSender plus native manager, modelled on BDialEUM's
   `code_link.py` without the modem retry logic. `service()` is called from the main loop only in
   SERVE.
2. Port host pinning (`host_id` in `code_req`, ignore other ids) from
   `origin/claude/esp-now-dial`'s `code_sender.py` and `espnow_code.py`.
3. `bdial_server.py`: SERVE enters antenna-off, then serving; exit is the reverse. Remove
   `code_server`, `serve_guard`, `serve_probe` and `prewarm_ap()` imports and calls. Radio bring-up
   order follows phase 0 step 6.
4. Serial contract: `mode` SERVE stays; `ssid` is always null; `arm`/`disarm` keep their meaning
   (enter/leave SERVE). Add the `pull` event from BDialEUM. Check ChatBroadcast
   (`js/device/bboxDeviceLink.js`) for any use of `ssid`.
5. `manifest.js`: drop the removed files so ChatBroadcast's installer matches.
6. Hardware test: phase 0's runs through the real menu (DONE + ACT into SERVE, getcode card on the
   wand), then 2 and 4 wands at once against `MAX_SESSIONS`.

## Phase 2: Box firmware

Same changes in `BBoxFirmware/` (PEER copies; change each, say which). Box `serve_guard` floor and
`SOCK_REPLY_TIMEOUT_S` go with the AP code. Same hardware test, including battery.

## Phase 3: stock wand

Port the receive path from `MockWandEUM` into `MockWand/`: `lib/espnow_code.py`, the getcode
handler calling it instead of `pull_flag.set_pending()` + reset, and `REMOTE_GETCODE` off by
default. `MockWand/lib/espnow_manager.py` stays (native, C6 antenna switch). The card format
`getcode:<slug>@<host>` does not change.

## Phase 4: other pullers

| Device | Today | Needed |
|---|---|---|
| Icon Display | `code_puller.py`, game plus an icons leg (`ROLE_FILES`) | `code_sender` has no icons leg; add it, plus a receiver |
| Splat Companion | `code_puller.py`, `_splat` files | ESP-NOW goes through its C6 modem (`SplatCompanion/ESPNowModem/`); receiver runs over that link |

The Box and Dial cannot drop the AP until these move, or they lose the ability to serve them.

## Phase 5: remove the WiFi path

After phases 1–4 pass on hardware: delete `code_server.py`, `serve_guard.py`, `serve_probe.py`,
`code_puller.py`, `pull_flag.py`, `pull_probe.py` from every tree; update `../../known_issues/2026-09-30-known-issues.md`
(items 1–12 that are WiFi-only close), the Box and Dial READMEs, and `HARDWARE_PROTOCOL.md` where it
mentions SERVE/AP.

## Open questions

- Does UIFlow2 on the Dial (StampS3A) ship `espnow`? Phase 0 step 1.
- Must the radio be claimed at boot and held, or can SERVE start it? Phase 0 step 6.
- Is the antenna-off rule needed for ESP-NOW's lower duty cycle? Phase 0 steps 4–5.
- Channel: wands and senders use the STA default (channel 1). Fix it explicitly in both, or leave?
- Throughput with several wands from one S3 sender is unmeasured; the 6-session cap comes from the
  modem design.
