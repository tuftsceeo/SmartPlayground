# Plan: ESP-NOW game serving on Box and Dial, then the rest of Bag3 integration

## Context (handoff primer)
This is the SmartPlayground repo (`tuftsceeo/SmartPlayground`): a research prototype with MicroPython firmware for playground devices plus static web tools. Read `AGENTS.md` first.

**Device-code rules:**
- Nothing allocates before the radio claims its memory.
- Use `memprobe` (`idf_largest`) only to diagnose an out-of-memory failure; it is not a per-change step.
- Every `mpremote` call uses `resume`.
- For device access, follow `Bag3/Code/HARDWARE_PROTOCOL.md`.

Paths below are under `Bag3/Code/BroadcastCode/` unless stated.

**State on 2026-10-20 (after the 10/19 prototype demo):**
- **The active line is `origin/Chat_to_Tap_Doggle`.** It has:
  - wand pairing and lobby-party games, hardware-tested on 2–3 wands (`docs_and_design/2026-10-07-splat-pairing/RESULTS-PartB.md`)
  - ChatBroadcast with party-game generation, the Icons view, NFC catalog push and display-only sends
  - the one-screen Simulator with Splats, virtual peers and headless runs
  - the Music Board Station and Relay Timer
- **`october19demo` is retired.** Its unported fixes are listed in Phase 6.
- **Box and Dial serve today over SoftAP + TCP.**
  - Box/Dial side: `BroadcastBox/BBoxFirmware/` and `BroadcastDial/BDialFirmware/`, files `bbox_server.py`/`bdial_server.py`, `code_server.py`, `serve_guard.py` and `serve_probe.py`. These are PEER copies: change each and say which.
  - Wand side: `MockWand/code_puller.py` and `pull_flag.py`.
  - The card format is `getcode:<slug>@<host>`.
- **Goal:** ESP-NOW **replaces** SoftAP + TCP serving on both the Box and the Dial. They send game files to wands over their own ESP-NOW radio, with no modem.
- **SoftAP and ESP-NOW never run together, in any build or mode.** Phases 2 and 3 remove the AP serving code from each firmware in the same change that adds ESP-NOW serving; no fallback, toggle or dual mode. Phase 5 only deletes the now-unused wand-side and leftover files and docs. This plan supersedes the phase order of `docs_and_design/2026-10-19-espnow-box-dial-plan.md` (read it for detail; its content is folded in below).
- **What already exists:**
  - **Sender protocol:** `EspnowModem/host/code_sender.py`. Receiver-driven windows, sha256, busy/retry and peer cleanup. 11 tests in `EspnowModem/tests/test_code_xfer.py`.
  - **Wand receiver:** `EspnowModem/MockWandEUM/lib/espnow_code.py`, plus the `CODE_VIA_ESPNOW` path in `MockWandEUM/main.py`. It receives, checks, promotes and launches in one boot, without a reset.
  - **Native-radio sender bench:** `tools/devtests/xfer_host.py`. 25/25 transfers up to 36 KB at about 23 KB/s (`2026-09-30-transfer-comparison-results.md`). Driven by `xfer_bench.py`, with files from `make_speed_games.py`.
  - **Dial-over-modem prototype** on branch `origin/claude/esp-now-dial` (`EspnowModem/BDialEUM/`). It has host pinning (`host_id` in `code_req`) and a `pull` serial event. It has never run on hardware.
  - **Power rule** in the server docstrings: the NFC RF field is off whenever the radio is serving. SERVE mode calls `antenna_off()` and stops reader I2C.
- **ChatBroadcast's interface to the Box/Dial** is serial JSON:
  - Files: `ChatBroadcast/js/device/bboxLink.js` and `bboxDeviceLink.js`, with `boxFirmwareInstaller.js` reading each firmware's `manifest.js`.
  - Commands: `identify`, `info`, `arm` (15 s timeout), `disarm`, `repl`, `reboot`, plus the upload/stage commands in `bboxDeviceLink.js`.
  - Device events: an `identity` object, and a `mode` value that includes SERVE.
- **Display-only games** (only `<slug>_icon.py`) are not enrolled or served by the current firmware. Commit c354802 on `october19demo` fixed that for the SoftAP code and is not ported. The rule is rebuilt in the new sender.

**Power history: fixed by the modal rule, keep it fixed (Box especially):**
- **The problem (2026-09-01).** The Box rebooted silently every ~30 s–2 min on USB (battery charging) and was stable on battery alone.
  - In the firmware of that time, the SoftAP and the NFC reader's RF field were both live from boot whenever a game was on flash.
  - Silent resets with the USB port dropping pointed to a brownout on a current-limited USB supply. A competing hypothesis was charge current against WiFi TX spikes.
  - Sources: `Bag3/Code/known_issues/2026-09-01-bbox-usb-reboots.md` and `docs_and_design/old/2026-09-01-wifi-handoff-diagnosis.md`.
- **The fix (2026-09-02, a406712 / 42dd9d4).** The Box became modal: at most one of {radio, NFC RF field} is on at any instant. The field is up only on the scanning screen, and SERVE turns the reader off. The Dial follows the same rule.
  - Verified on USB on 2026-09-02: 200+ s of steady heartbeats, no `BROWNOUT` (`BroadcastBox/README.md`, "Verified vs open").
- **What this plan must keep:**
  - ESP-NOW serving inherits the modal rule unchanged. SERVE does antenna-off, then radio. Leaving SERVE stops the radio, then turns the antenna on.
  - Nothing in the new code may bring the reader field up while ESP-NOW is serving.
  - Regression check only: Phase 1 step 3 and Phase 5 run on USB while charging, and read `reset_log.last()` afterwards.

**Branch:** `chat_app_espnow`, created from `origin/Chat_to_Tap_Doggle`. All commits and pushes go there (`git push -u origin chat_app_espnow`).

---

## Phase 1: S3 radio feasibility check, no firmware changes (hardware, ≤ 30 min)
**Already measured, not repeated:** ESP-NOW transfer speed from a **C6** sender (`xfer_host.py`): 25/25 transfers, ~23 KB/s. The Dial was measured only as a **WiFi** sender, and `2026-09-30-transfer-comparison-results.md:83` records "Dial as ESP-NOW sender: not tested".

**Still unknown, and this check answers it:** whether the **S3** Box and Dial can run ESP-NOW from their own radio next to their UI, NFC reader and display. That covers the `espnow` module in UIFlow2, the memory left after the UI is up, and brownout with the antenna on. Speed runs are reduced to one 36 KB sanity transfer per board.

**Prepare offline:**
- Write `tools/devtests/espnow_serve.py`: `code_sender.CodeSender` over a minimal native manager (`add_peer`, `send_to`, `send_raw`, `remove_peer`, `poll`, `broadcast`) written directly against `espnow`.
  - Do not reuse MockWand's `espnow_manager.py`: it drives the C6 antenna pins.
  - Test it with CPython fakes next to `test_code_xfer.py`.
- Write the bench prompt.

**Bench, run over `mpremote resume run`** with one Dial, one Box and one MockWandEUM wand. One 36 KB file, one run per condition:
1. Does `import espnow` work on the Dial (StampS3A) and the Box, and does `ESPNow().active(True)` succeed?
2. Antenna off, USB power: transfer runs.
3. Regression check, USB connected (charging): transfer runs in SERVE, then read `reset_log.last()`. Expect no BROWNOUT, as with the modal SoftAP firmware.
4. Late bring-up: start ESP-NOW after the full UI is up, and record whether it fails or the largest block shrinks.

**Gate:** steps 2 and 4 pass on both boards with no BROWNOUT. Step 4 decides whether the radio is claimed at boot.

## Phase 2: Dial firmware serves over ESP-NOW
1. `BDialFirmware/code_link.py`: a CodeSender plus native manager, modelled on BDialEUM's `code_link.py` without the modem logic. `service()` runs from the main loop only in SERVE.
2. Port host pinning (`host_id` in `code_req`) from `origin/claude/esp-now-dial` into the sender and `MockWandEUM/lib/espnow_code.py`.
3. **Role-aware files:** serve `<slug>.py` to wands and `<slug>_icon.py` (plus its icons) to displays. A slug with only `_icon.py` is enrolled in the game list (c354802's rule).
4. **`bdial_server.py`:** SERVE does antenna-off, then serving; exit is the reverse. Remove the `code_server`, `serve_guard`, `serve_probe` and `prewarm_ap` imports and calls. Radio bring-up order follows Phase 1 step 4.
5. **Serial contract:**
   - `mode` SERVE stays, `ssid` is always null, and `arm`/`disarm` enter and leave SERVE.
   - Add `pull` events: `{type:"pull", slug, role, wand, ok, ms}`.
   - Document the contract in the Dial README.
6. **`manifest.js`:** drop the removed files and add the new ones.
7. **Offline checks:** `py_compile`, the `tools/devtests/wire_test_dial.py`/`wire_contract.py` updates, and the sender tests.

### Phase 2 notes (2026-10-20)
- **Done on the Dial:** steps 1, 2, 4, 5 (README), 6 and 7 (`tools/devtests/test_dial_code_link.py`), plus serving from the WRITE menus (`SHARE_IN_MENUS`): the radio is up whenever the reader field is off. Results in RESULTS.md.
- **Step 3 needs a protocol extension (approved 2026-10-20).** `code_sender` sends one file per `code_req`, and the Icon Display needs `<slug>_icon.py` plus every file in `games/<slug>_icons/`. The design:
  - The display sends `code_req` with `hub:"icon_display"`.
  - The offer for `<slug>_icon.py` carries an `icons` list of file names.
  - The display then sends one `code_req` per icon, with `slug:"<slug>"`, `hub:"icon_display"` and `file:"<name>"`.
  - The sender resolves that to `games/<slug>_icons/<name>`. Names containing `/` or `..` are refused.
  - A failed icon does not fail the game, as in `code_server`'s icon leg.
- **Step 3 implemented (offline tests pass, hardware not run).** `code_sender.ROLE_FILES` maps `icon_display` to `<slug>_icon.py` with icons, in the Box, Dial and host copies. Icon names are paged: a full list would not fit one 250 B ESP-NOW frame, so the offer carries `icons_n` plus a trimmed `icons` list, the receiver asks `list_from:k` for the rest, and the sender replies `code_icons`. Each icon is then one `code_req` with `file`.
- **Protocol references to update when step 3 lands.** Each holds a copy or description of the message set:
  - `EspnowModem/host/code_sender.py` and the Dial copy
  - `EspnowModem/MockWandEUM/lib/espnow_code.py` (PEER header)
  - `BroadcastDial/README.md` "Serving over ESP-NOW"
  - `EspnowModem/README.md`
  - `HARDWARE_PROTOCOL.md` "Reserved Box/Dial staging suffixes", which cites `code_server.ROLE_FILES`
  - `Stations/IconDisplay/README.md`

## Phase 3: Box firmware (same change)
Repeat Phase 2 in `BBoxFirmware/`. The Box's `serve_guard` floor and `SOCK_REPLY_TIMEOUT_S` go with the AP code. Use `wire_test.py` for the offline check.

## Phase 4: Wand receive path and ChatBroadcast interface
1. **Stock MockWand:**
   - Port `lib/espnow_code.py` from MockWandEUM.
   - The getcode handler calls it instead of `pull_flag.set_pending()` + reset.
   - `MockWand/lib/espnow_manager.py` stays. The card format is unchanged.
   - `main.py` gets a thin hook only (it is precompiled by `tools/deploy.py`).
2. **ChatBroadcast** (`js/device/bboxLink.js`, `bboxDeviceLink.js`, `app.js`):
   - Remove any `ssid`/AP wording.
   - Show live `pull` events (which wand got which game, OK or failed).
   - Allow display-only sends.
   - Stop treating the Box/Dial as an AP host in help text and `knowledge/` files.
   - Update the node tests and `chat_ui_smoke.mjs`.
3. **Icon Display receiver:**
   - Today `IconDisplay/code_puller.py` uses `ROLE_FILES` with an icons leg.
   - Add an ESP-NOW receiver with the icons leg, matching step 3 of Phase 2.
   - Implemented (offline tests pass, hardware not run): `IconDisplay/lib/espnow_code.py` and `_espnow_pull` in `IconDisplay/main.py` (`CODE_VIA_ESPNOW`), with paged icon names as in the Phase 2 notes. The `pull` event carries the real slug and role.

## Phase 5: Hardware session (≤ 60 min) and SoftAP removal
1. **Bench run, through the real menus:**
   - Dial and Box SERVE.
   - getcode cards on 1, then 3, wands at once.
   - A display-only game pulled by the display.
   - A ChatBroadcast send, then a card tap, then play.
   - Battery runs on the Box.
2. **After it passes,** delete from every Bag3 tree:
   - `code_server.py`, `serve_guard.py`, `serve_probe.py`, `code_puller.py`, `pull_flag.py` and `pull_probe.py`
   - the WiFi-only items in `../../known_issues/2026-09-30-known-issues.md`
   - the AP sections in the READMEs and `HARDWARE_PROTOCOL.md`
   - SoftAP/`code_server` references found on 2026-10-20 (`grep -rlE "code_req|SP-FILEPUSH|SoftAP|code_puller" --include='*.md'`):
     - `BroadcastBox/README.md`, `BroadcastCode/README.md`
     - `MockWand/README.md`, `IconDisplay/README.md`, `EspnowModem/README.md`, `EspnowModem/MockWandEUM/README.md`
     - `SplatCompanion/Companion/README.md` and `HARDWARE_TEST.md`
     - `BDialFirmware/tools/BENCH_TEST_PLAN.md`
     - `docs_and_design/DEVICE_ONBOARDING_SURFACES.md`, `PHASE6_HANDOFF.md`
     - `TeacherTools/NFC Station/docs/plan.md`
     - `Bag3/AGENTS.md` (its `code_server.py`/`code_puller.py` memory rule now applies to `code_link.py`)
     - ChatBroadcast `knowledge/` files

   The Splat Companion is retired and needs no receiver.

## Phase 6: Later work (not started until Phase 5 is done)
- **Port from `october19demo`:**
  - The IconDisplay and wand runtime-error red X (63cd669; the 1.6 part of 8f58496).
  - The NFC Station party-game and `unpair` tags.
  - `elepant` → `elephant` (5f8d399).
  - `tools/sync_game_tags.py` (de3c579).
  - The AGENTS.md list of drift checks.
- **Splat two-color code:** shown as a steady split (LEDs 0–6 identity, 7–13 second color; mask `0x3FFF`) instead of flashing. The code is in `MockWand/lib/splatpair.py` `glow()`, mirrored in the Simulator.
- **Game templates design doc** (`docs_and_design/2026-10-20-game-templates/DESIGN.md`). Two independent axes:
  - **Players:**
    - Single (`play()`).
    - Multi-role in one file, chosen by role card, with the other roles waiting on the leader role's broadcasts (the `freeze_dance.py` pattern, no lobby).
    - Equal roles, where every wand taps the same card.
  - **Splats:** none, or the wand's own paired Splats.
  - **Plus:** pairing UX icons, and moving partytest, splattag and relaycolor off the lobby.
- **Implement the templates** after the design is approved: Simulator and ChatBroadcast follow.

## Verification
- **Each phase:**
  - `py_compile` on touched device files and `tools/devtests/compile_check.sh`.
  - `EspnowModem/tests/test_code_xfer.py` and `wire_test*.py`.
  - The ChatBroadcast node tests (`chat_request_test.mjs`, `chat_ui_smoke.mjs`, `nfc_station_link_test.mjs`, `splat_game_check_test.mjs`) and the devtests (`chatbroadcast_flow.mjs`, `role_state.mjs`).
  - Simulator `python3 -m pytest -q`.
- **Hardware:** Phase 1 and Phase 5 sessions, with results in `docs_and_design/2026-10-20-espnow-serving/RESULTS.md`.
