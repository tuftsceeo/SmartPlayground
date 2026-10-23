# Plan: Status reports with `kind`, Bag3 M5Paper Remote, Dial "Distribute code"

## Context
The Bag2 M5Paper Remote's Status screen only lists idle Bag2 wands. Replies carry only `battery` and `rssi`, so they have no device type. Every row is labelled `W-xxxx`. Bag3 needs:
1. A copy of the remote whose status replies carry a `kind` field. Replies come from MockWand (idle and in-game) and IconDisplay.
2. A ChatBroadcast "Distribute code" overlay after a send to a BroadcastDial. It scans through the Dial, lets the user pick devices, and has the Dial trigger a staggered pull on each one. Progress shows in the app and on the Dial.

Decisions confirmed by the user:
- **After the pull:** the device pulls and launches, like a getcode card.
- **Devices that reply:** MockWand and IconDisplay.
- **Wand tree:** `Bag3/Code/BroadcastCode/MockWand` only. `Bag3/Code/Wand Module` is not touched.
- **Bag2:** not touched.

Constraints from AGENTS.md:
- Shared libraries are per-tree copies. Each copy edited is named in its commit.
- Import order must leave the radio's memory allocation first. The new Dial diagnostics are not imported ahead of the radio.
- Keep every diff minimal. Existing behaviour stays the same.

## Protocol additions (ESP-NOW, JSON, each under 250 B)
- **`status_report`:** gains `"kind"` with the value `HUB_TYPE`, e.g. `wand` or `icon_display`. An old receiver ignores the extra key.
- **`code_push`** (new): `{"type":"code_push","mac":<target>,"slug":..., "host":<HOST_ID>}`, sent by the Dial. A receiver acts only when `_is_for_me(mac)`, the same filter `find_device` uses.

## Stage 1: Bag3 M5Paper Remote and device replies
- **Copy** `Bag2/Code/M5Paper Remote/` to `Bag3/Code/M5Paper Remote/` unchanged (first commit). The copy keeps its own `espnow_manager.py`, identical to Bag3 `lib/` today.
- **Remote edits** (second commit):
  - `main.py` `_drain_status_reports`: pass `data.get("kind")`.
  - `ui.py` `upsert_status_report(mac, battery, rssi, kind=None)`: store `kind`.
  - `ui.py` `_wand_name` becomes `_device_name(mac, kind)`. The prefix is `W-` for a wand, `D-` for icon_display, `?-` for anything unknown, then the last 4 hex digits.
  - `ui.py`: change "Waiting for wands..." to "Waiting for devices...".
- **`espnow_manager.py` (MockWand and IconDisplay copies only):**
  - `broadcast_status_report` sends `kind`. `set_status_provider(fn, kind=None)` stores it.
  - `poll()` returns `("code_push", data, mac)` when `code_push` is for this device. Otherwise it drops the message.
- **MockWand `main.py`:**
  - `set_status_provider(..., kind=HUB_TYPE)` at :981.
  - In-game replies already work: every game shares the one `enow`, and `poll()` sends any pending report. Stage 1 hardware test confirms this rather than changing code.
- **IconDisplay `main.py`:**
  - Add `enow.set_status_provider(lambda: None, kind=HUB_TYPE)` after radio init, so it replies with battery `None`.
  - Make sure its idle loop calls `enow.poll()`.

**Hardware test 1 (human):**
1. **Tap** Status on the Bag3 remote with an idle MockWand, a MockWand mid-game and an IconDisplay powered on.
2. **Confirm** three rows appear with W/W/D prefixes, battery for the wands and signal bars.
3. **Tap** each row and confirm find-device runs on the matching unit.

## Stage 2: BroadcastDial firmware (`BDialFirmware/`)
- **`code_link.py` `CodeLink.poll`:** when `CodeSender.handle` returns False, return a non-code JSON message (`status_report`) to the server instead of dropping it.
- **New module `fleet.py`,** imported lazily after the radio is up and holding the logic below.
  - `scan()`: broadcast `status_poll` three times at 60 ms. Collect reports for 6 s. Emit `{"type":"status_report",mac,kind,battery,rssi}` for each, then `{"type":"status_done"}`.
  - `find(mac)`: broadcast `find_device` three times.
  - `distribute(slug, macs)`: send `code_push` to one MAC every `STAGGER_MS = 2500`. Never start a new one while the active `CodeSender` sessions are at 3 or more. The cap is half of `MAX_SESSIONS = 6`, to protect the 1024 B rxbuf. Progress counts the existing `pull` results whose MAC is in the set. Emit `{"type":"dist_progress",done,total,mac,ok}`. A MAC with no `pull` result 30 s after its push counts as failed, with `why:"timeout"`.
- **`bdial_server.py`:**
  - New commands `fleet.scan`, `fleet.find {mac}` and `fleet.distribute {slug, macs}`. Each needs the radio armed, so the Dial must be in WRITE mode and `serving()`. Otherwise it returns `{"type":"error","code":"not_serving"}`.
  - While a scan or distribution runs, do not disarm the radio, the same way an active session holds it.
- **`station_ui.py`:** add `show_progress(done, total)`. It reuses `_arc()` with `SERVE_FG` (teal, not the `INK_3` used by the back-hold ring) on the top layer, plus a centred `"3 of 6 updated"` label. It clears when `done == total` or on cancel.
- **`station.py`:** a mode or hold for distribution, so the progress screen stays up and back-hold still cancels it.

**Hardware test 2 (human, Dial over serial from a terminal or the app's console):**
1. **Send** `{"cmd":"fleet.scan","id":1}` and confirm `status_report` lines with `kind`, then `status_done`.
2. **Send** `fleet.find` and confirm the target lights.
3. **Send** `fleet.distribute` to 3 or more devices and confirm the pulls are staggered, the devices launch the game, and the teal ring and "N of M" count on the Dial.
4. **Hold** back during a distribution and confirm it cancels.

## Stage 3: ChatBroadcast app (`ChatBroadcast/`)
- **`js/device/bboxDeviceLink.js` `FORWARDED_EVENTS`:** add `pull`, `status_report`, `status_done` and `dist_progress`. Adding `pull` also fixes the existing unforwarded `pull` handler at `app.js:799`.
- **`bboxDeviceLink.js`:** add methods `fleetScan()`, `fleetFind(mac)` and `fleetDistribute(slug, macs)` using the existing `cmd/id` request helper.
- **`index.html`:** add `#distribute-overlay` (`overlay-view` > `overlay-card overlay-card-send`). It contains:
  - a device table with columns Select, Name, Kind, Battery, Signal, Find and a status column showing pending, pulling, done or failed
  - Rescan, Select all/none, and a Distribute button that stays hidden until at least one device is selected
- **`css/app.css`:** add a small checkbox style matched to the existing button colours. The app has no checkbox CSS today.
- **New `js/distribute.js`:**
  - Opens the overlay and starts a scan. Rows are upserted on `status_report`. Rescan clears the list.
  - Find runs `fleetFind`.
  - Distribute runs `fleetDistribute`. Rows update on `dist_progress` and `pull`, with an "N of M updated" bar.
- **`app.js`:** in `showSendSuccess()`, show a "Distribute code" button only when `identity.device === "broadcast_dial"`. The button waits for the link to come back `live` after the reboot, then opens the overlay with the slug just sent. The 5 s auto-close stays, unless the user clicks the button first.
- **Tests:**
  - Extend `tools/pull_event_test.mjs` style tests with a fake-link test for the distribute state machine.
  - Run `node tools/chat_ui_smoke.mjs` for an overlay smoke test.

**Hardware test 3 (human, full process):**
1. **Generate** a game in ChatBroadcast and send it to the Dial.
2. **Click** "Distribute code" and confirm the list shows wands and IconDisplay.
3. **Tap** Find on one device, then Rescan.
4. **Select** a subset and click Distribute.
5. **Watch** the app rows and the Dial ring advance, and confirm unselected devices are untouched.

## Verification per stage
- **Static check:** run `python -m py_compile` on every edited `.py`.
- **App tests:** run `node tools/*_test.mjs` from `ChatBroadcast/`.
- **Hardware:** a human runs the checklist above, and each stage gets its own commit and push to `ccr-92e6a0fc-79s37a` before testing.

## Risks to check during implementation
- **Radio during distribution:** the 10/20–21 "radio on while NFC idle" work is already in this branch (`9f518e9` serves from the WRITE menus, `c566a21` merges the Dial into one state, and both are ancestors of HEAD). `_serve()` (`bdial_server.py:676`) disarms whenever `Station.serving()` is false, so the new distribution screen must be added to `SERVE_MODES` (`station.py:105`). Otherwise the radio drops while the progress ring is up.
- **IconDisplay buffer:** IconDisplay sets no rxbuf, so a status reply during its own pull is untested.
- **Known issue 2026-09-29:** large or multi-file games can fail on the Dial before distribution. That is out of scope.
