# CrowPanel5 teacher tool: implementation plan

## Context

`Bag3/Code/Experiments/CrowPanel5 Display/` runs the design system gallery and screen 1 (home) of the
"CrowPanel Teacher Tool" design (https://claude.ai/artifact/LiR5xAGC7LecrJh7BFb3iQ) on the Elecrow
CrowPanel 5.0" V3 with lvgl_micropython. This plan covers building every screen of that design with a
working back end taken mostly from the Broadcast Dial firmware
(`TeacherTools/BroadcastDial/BDialFirmware/`).

The design has two pages. "Design 1" is the default layout. "Resized Design" becomes an optional
"zoom in" mode, and its shorter copy is used in both. The mock is a layout proposal; behaviour comes
from the Dial, the Mock Wand and WebApp2, and from the decisions below.

**After approval, the only step is to copy this document to
`Bag3/Code/Experiments/CrowPanel5 Display/IMPLEMENTATION_PLAN.md` for review.** No firmware or
device files change in this session.

### Decisions (user, 2026-10-29)

| Topic | Decision |
|---|---|
| ChatBroadcast attached | Design's peripheral mode: the computer takes over; the panel mirrors and writes cards on request. Built on the current Broadcast Dial: ESP-NOW always on, no reboots (see "Linked mode"). |
| Wand state | The panel keeps its own records, modelled on the first WebApp hub's roster. No wand protocol change. |
| Send code vs Start | Keep wand behaviour: `code_push` stops the wand's game and launches the pushed one. Keep the design's Start button and its label. Minimal diff: integrate working parts, don't reword. |
| NFC reader | The wands' reader (PN532, `Wand Module/lib/pn532.py`) for now. PN5180 comes after proof of concept. |
| Order | First and early: prove screen + NFC + ESP-NOW run together with no out-of-memory and no brownout. Then the screens as designed. Then the PN5180. |

## 1. Screen inventory

Screens are numbered as in the design. "Targets" means the MAC list of the current chat: everyone,
a saved group, a picked set, or one device. Copy follows the Resized page; on-screen text is ASCII
(`·` becomes " - ", `→` the `back`/arrow icon or ">", `…` "...", `✓` the `tick_16` icon). Changing
text sits in fixed slots and scrolls rather than truncating.

### 1 - Playground chat (home) — `home.py` (built, fixed sample data)

- **Purpose:** the teacher's main view. Pick who you're talking to, see what was sent and who answered,
  start or stop games.
- **Reached from:** boot; Back from 2, 4, 5, 6; leaving linked mode.
- **Leads to:** 2 (See list, New group), 3 (Start a game), 4 (via 3's Send code), 5 (Cards), 6 (tap a
  single-device chat row).
- **Data:** chat list (Everyone, saved groups, devices needing attention such as low battery); header
  title and "N answered - X min ago"; the chat log for the selected chat (system notes such as "New
  game: X", roll-call summary with ready / low battery / stations chips, sent-command bubbles with
  "on N of M - time", "W-xxxx didn't answer" with Try again); link pill; "Radio on"; panel battery.
- **Actions → back end:**
  | Action | Back end |
  |---|---|
  | Tap a chat row | Select targets (roster, groups) |
  | Roll call | Status poll to targets, roster update, summary bubble |
  | Look for devices (radar, Design 1 only) | Same as Roll call (see Open questions) |
  | Find (header, Design 1 only) | See Open questions |
  | Cards | Open 5 |
  | Start a game / Send code | Open 3 |
  | Stop | `stop` to targets |
  | See list | Open 2 |
  | Try again | Resend that bubble's command to that MAC |
  | New group | Open 2 in pick-for-group mode |

### 2 - Who gets it? (find + status)

- **Purpose:** pick devices, see each one's battery and signal, make one blink.
- **Reached from:** 1 (See list, New group). **Leads to:** 1 with the picked set as the chat ("Chat with
  N"), or Back.
- **Data:** roster tiles: name or W-xxxx, tag (last 4 MAC digits or STN), battery %, signal word,
  "Not heard"; filter All / Wands / Stations; "N picked".
- **Actions:** tap toggles pick (local); hold → find that MAC; Roll call → status poll; Save group →
  groups store (needs a name, so the on-screen keyboard); Chat with N → set targets, back to 1.

### 3 - Pick a game (start / send code) — bottom sheet over 1

- **Purpose:** choose a game and start it on the targets, or send its code first.
- **Reached from:** 1 (Start a game, Send code), 6 (Start game, Send code). **Leads to:** 4 (Send code),
  back to the caller (Start, Not yet).
- **Data:** "To: <chat> - N devices"; game tiles with name, colour and "on N of M" / "Playing now" /
  "New" from the panel's records; filter tabs (Design 1: On wands / New / All; Resized: Ready / New);
  "<game> needs its code first."
- **Actions:** Start → `start_game {name}` to targets; Send code → 4; Not yet → close.

### 4 - Sending code to wands

- **Purpose:** push a game's code to the targets and follow each one.
- **Reached from:** 3, 6. **Leads to:** 1 (Back, Start).
- **Data:** "Send code: <game>" bubble; "N of M wands have it" with bar; per-device row Has it /
  Sending / Waiting / No answer; "Keep wands near the panel"; header "Radio busy - games paused".
- **Actions:** Pause → hold the queue (in-flight pushes finish); Retry W-xxxx → push to that MAC;
  Start <game> → `start_game` to the devices that have it (they are already running it, because
  `code_push` launches the game; the button is kept as designed).

### 5 - Write game cards (NFC)

- **Purpose:** write a game's cards in sequence, helper cards, custom text, or read a card.
- **Reached from:** 1 (Cards). **Leads to:** 1 (Back, Done).
- **Data:** tabs Game / Helper / My own / Read; card list with done / now / todo; "Card N: <label>";
  instruction; progress slot (Ready / Writing N%); fixed NFC target (x 528, y 150, 240x180) in
  waiting / writing / done; left and bottom edge bars; "Radio paused while writing".
- **Card text comes from the Dial, not the mock:** Code `getcode:<slug>@<HOST_ID>`, Play `<slug>`,
  then the game's `.tags.json`; Helper is `stop`, `battery`; My own is free text, at most 54 bytes.
- **Actions:** card detected → write (or "already set") → next; Skip → next; Done → back; Read → show
  text, tap to copy it to the next card; My own → keyboard.

### 6 - One device (direct chat)

- **Purpose:** everything about one device: find it, rename it, start, stop or send code to it alone.
- **Reached from:** 1 (device chat row), 2 (tap through, see Open questions). **Leads to:** 1, 3, 4.
- **Data:** name, tag, kind, "heard X ago" or the last game the panel sent; chat log for this MAC;
  battery, signal; Rename.
- **Actions:** Find it / Find it again → find to this MAC; Rename → keyboard, nickname store;
  Start game / Send code → 3 / 4 with this one MAC; Stop → `stop` to this MAC.

### 7 - Plugged in: link to ChatBroadcast? · 8 - Linked: mirroring · 9 - Linked: computer asks for a card

See "Linked mode" in section 3. Summary:

- **7** shows when host traffic arrives (the panel cannot sense a USB host through the CH340). Link
  → linked mode; Just charge → ignore the host until unplugged or reset.
- **8** shows "Happening now", a recent feed, a device list with states, and Stop all. Every row is
  driven by host events.
- **9** shows the card the computer asked for, with the NFC target and progress, and reports the
  result back.

### NFC tap target (shared component)

Fixed position and size on every card screen (5 and 9), states waiting / writing / done. Built once as
a component and reparented, so it never moves.

## 2. Back-end map

Status: **reuse** (as is), **adapt** (change needed), **new** (doesn't exist).

| Action | Today | Status |
|---|---|---|
| Radio up / down | `code_link.NativeManager.init/shutdown`, `prewarm()` | reuse |
| Serve code to wands that tap a `getcode` card | `CodeLink.poll` + `code_sender.CodeSender` (lazy). ESP-NOW is always on except while NFC is in use, so serving is not a mode | reuse, if the panel keeps a `/flash` directory (see Paths) |
| Roll call (status poll) | `fleet.Fleet.scan`, `on_msg` | adapt: reports go to the host only; add a roster callback, keep the 6 s window |
| Roster: last heard, battery, signal, last sent, ACKs | `Live_Page/WebApp/hubCode/main.py` `recent_devices` keyed by MAC, `last_seen` refreshed on any message heard, unknown values kept as `None` and earlier good values kept, stale after 60 s, dropped after 120 s | new: `roster.py` on that pattern, plus the panel's last-sent command and radio ACK per MAC |
| Find one device | `fleet.Fleet.find` (broadcast + `mac`, 3x) | reuse message; optionally unicast for an ACK |
| Send code to a MAC list | `fleet.Fleet.distribute/step/_push/on_pull/cancel` | adapt: progress to the UI as well as the host; add pause; stop reading `mgr._peers` |
| Start a game on a MAC list | none (wand accepts unicast `{"type":"start_game","name"}`, `espnow_manager.send_start_game`) | new: shared targets send |
| Stop a MAC list | none (wand accepts unicast `{"type":"stop"}` and broadcast `["stop"]`) | new: shared targets send |
| Start / stop everyone | M5Paper and WebApp2 hub broadcast twice | new on the panel: broadcast path of the same send |
| Game library on flash | `BdialServer._boot_scan_games`, `_load_index`, `_read_tags`, `_rebuild_entries` | adapt: lift out of `BdialServer` into a library module |
| Built-in wand game list | none on the Dial (`Wand Module/lib/game_tags.py`) | new: a fifth hand-kept copy (see Risks) |
| Card write sequence | `station.Station.go_allnext/_scan`, `card_writer.write_text/existing_text` | adapt: Station is dial-driven; `card_writer` is built on the WS1850S API |
| PN532 card access | `Wand Module/lib/pn532.py` (read/write blocks and pages, `machine.I2C`) | adapt: needs field on/off and the touch bus's `i2c` driver |
| Read and copy a card | `station._read`, `card_writer.existing_text` | adapt |
| Custom text | `text_entry.py` + Dial rim keyboard | replace with `lv.keyboard`; keep the 54-byte limit and word bank (`BdialServer.words`) |
| Radio / NFC exclusivity | `BdialServer._serve`, `station._set_field`, `host.radio_off()` | adapt |
| Groups, nicknames | ChatBroadcast nicknames in browser localStorage | new: JSON on the panel |
| Stats | `stats_log.record_pull/record_tag/aggregate` | reuse (paths) |
| Serial link | `json_link.JsonLink` (stdin/stdout, works on the UART REPL) | reuse |
| Host commands | `BdialServer.dispatch` table | adapt (plus linked-mode commands) |
| Beeps | `station_ui.beep_*` (M5 speaker) | new: later, needs a speaker (I2S pins 18/42/17) |
| Reset log | `reset_log.py` | reuse |

## 3. Architecture

### Layers

- **Radio and storage (no `lvgl` import):** `code_link.py`, `code_sender.py` (lazy), `fleet.py`
  (adapted: scan, find, distribute, plus `send(msg, macs)` for start/stop), `roster.py` (new),
  `library.py` (games on flash, lifted from `bdial_server.py`), `store.py` (groups, nicknames),
  `stats_log.py`, `reset_log.py`, `json_link.py`, NFC (`pn532.py` port + `card_writer` adapter).
- **Controller:** `panel_server.py`, the analogue of `bdial_server.py`. Owns the main loop, radio/NFC
  exclusivity, the host link, and every action. The UI calls controller methods; the controller pushes
  plain-dict models to screens.
- **UI:** `display_lvgl.py`, `ds_tokens.py`, `ui_kit.py` (the helpers now private in `home.py`:
  `_box`, `_text`, `_icon`, `_button`, `_pill`, `_row`, `_avatar`), one module per screen, and
  `nfc_target.py`.

### Screens

- Built on first show and cached, as `home.show()` does now; switched with `lv.screen_load`.
- Every changing value is a label or bar created at build time and updated with `set_text` / value
  setters. Lists use a fixed pool of row widgets (12 device tiles, 8 game tiles, 8 progress rows)
  that are shown, hidden and refilled, never created per update.
- The game sheet (3) is a panel on `lv.layer_top()` over the home screen with a dim backdrop.
- LVGL event callbacks only append an action to the controller's queue. Radio sends (some block with
  `sleep_ms`) run from the main loop, so touch stays responsive.
- Zoom mode is a second set of cached screens built from the same modules with a size preset, built
  only when chosen.

### Main loop

`link.pump()`, controller step (radio poll, fleet step, NFC step), apply dirty models to the visible
screen, `time.sleep_ms(1)`. LVGL runs from `task_handler`.

### Host

Standalone by default: everything in screens 1-6 works with no computer. Linked (peripheral) mode
runs over `json_link` on UART0 when ChatBroadcast connects; see below.

### Memory order on boot

The rule stands: nothing may allocate before the radio claims its block. On this board the picture
differs from the Dial:

- The GC heap is in PSRAM (`mem_free` about 8.3 MB), so Python objects don't fragment internal DRAM.
- `CONFIG_SPIRAM_TRY_ALLOCATE_WIFI_LWIP` is off: WiFi buffers come from internal DRAM. So do the RGB
  bounce buffers (2 x 10 lines x 800 x 2 B = 32,000 B, DMA-capable), the I2C/touch drivers and
  possibly parts of LVGL.
- `display_lvgl.py` already says "Import only after radio bring-up".

Order in `main.py`:
1. Import only `gc`, `time`, `machine`, `board` (constants) and `code_link` (no module-scope content).
2. `prewarm()`, then bring the radio up.
3. `display_lvgl.init()` (RGB bus, bounce buffers, GT911).
4. `fs_driver` registration (must follow `display_lvgl.init()`), then the home screen and icons.
5. NFC reader init on the shared I2C bus.
6. Lazily: `code_sender` (on the first code request), `fleet`, and any heap-probe module.

Milestone 0 measures whether this holds (largest free internal block, not `mem_free`).

### Paths

lvgl_micropython mounts the filesystem at `/`. The Dial and ChatBroadcast use `/flash/games/`,
`/flash/active.txt`, `/flash/stats.log`, and ChatBroadcast's installer writes to `/flash/games/`.
Creating a `/flash` directory on the panel keeps every one of those paths, and `code_sender`,
`stats_log` and the installer, unchanged.

### Linked mode

Built on the current Broadcast Dial. Linked is a view, not a device mode: ESP-NOW stays on except
during an NFC read or write, the panel keeps doing everything in screens 1-6, and nothing reboots.

- **Protocol:** the Dial's command table (`identify`, `info`, `games.*`, `stats.*`, `fleet.*`, via
  `json_link`), plus:
  - `card.write {text, label}`, replying `card_written {uid, text}` or `write_failed` (the event
    ChatBroadcast's `updateTagChecklist` already consumes);
  - `games.rescan`, so installing a game needs no reset;
  - `unlink`, sent by ChatBroadcast on disconnect.
- **Screen 7:** shown on the first host command. Link shows 8; Just charge answers `identify` only.
- **Screen 8:**
  - "Happening now": the `fleet.*` distribute progress the host started, or the last start.
  - Recent feed: the panel's log of sends and roll calls.
  - Device list: the roster.
  - Stop all: broadcast stop.
- **Screen 9:** opened by `card.write`, with the NFC target. The result goes to the host and the
  panel returns to 8.
- **ChatBroadcast changes:**
  - accept the panel's identity in `bboxDeviceLink.js` `EXPECTED_DEVICES` and the Distribute gating;
  - after a game install, send `games.rescan` instead of a soft reset;
  - a Write button per tag-checklist row sends `card.write`; `card_written` ticks the row;
  - send `unlink` on disconnect.

## 4. Gaps and risks

| Risk | Detail | Plan |
|---|---|---|
| NFC on the touch bus | The wands' PN532 is at 0x24. `board.py` records that 0x24 answers on the GT911/PCA9557 bus (GPIO19/20). That bus is opened by lvgl_micropython's `i2c.I2C.Bus`; `pn532.py` expects `machine.I2C`, and two drivers cannot share the pins. PN532 transactions are long; touch reads every 10 ms. | M0: port `pn532.py` to `i2c.I2C.Device` (or confirm another bus), run touch and NFC together |
| NFC write path | `card_writer` wraps the WS1850S API (`antenna_on/off`, `detect_tag`). `pn532.py` has block/page read and write but no field control. | Adapter in M7 |
| PN5180 | Not wired. `Experiments/Capsule PN5180/lib/pn5180.py` is a drop-in for `pn532.py`; open issues in `known_issues/2026-10-28-capsule-pn5180.md` (corrupted replies, writes not run on hardware). Pins not chosen. | Last milestone |
| Brownout | Backlight is always fully on (no PWM), plus RGB, WiFi TX and the NFC field, on USB power. The Box's resets under radio load were power (`known_issues/2026-09-01-bbox-usb-reboots.md`). | M0 logs `reset_cause` and runs worst case |
| Internal DRAM | Radio needs one contiguous internal block; bounce buffers and drivers compete. | M0 logs `esp32.idf_heap_info(esp32.HEAP_DATA)` largest block across 50 radio off/on cycles with the UI live |
| Image drift | The RGB DMA and WiFi share PSRAM bandwidth; drift was fixed for redraw load only. | M0 checks by eye under radio load |
| Fonts | Built in: Montserrat 12/14/16. Design 1 is drawn with those (approved home). Zoom mode needs 18-34 px. `lv.binfont_create` is bound in this build, so `.bin` fonts can load from the filesystem through `fs_driver` with no firmware change. Making them needs `lv_font_conv` (npm), a tool install the user must approve. | Zoom milestone; ASCII range only |
| Flash: app | `micropython.bin` 2,898,304 B in a 2,899,968 B factory partition (1,664 B free). No firmware feature can be added without repartitioning (full erase). | Avoid firmware changes |
| Flash: files | FAT VFS 1,228,800 B for code, icons, fonts, games, logs. Today: Dial back-end modules about 118 KB, icons 120 KB on disk. | Budget table at M1; `.mpy` if needed |
| PSRAM | 768 KB frame buffer(s), cached screens, decoded PNGs. | Log `gc.mem_free()` per screen built |
| Touch dead after soft reset | Known issue: `machine.reset()` / `mpremote reset` kill the touch bus; EN reset is fine. ChatBroadcast's game install ends with a Ctrl-D soft reset (`replController.softReset`), and `reboot` calls `machine.reset()`. Ctrl-D's effect on this board is untested. | Panel rescans games on a host command instead of resetting; host can pulse RTS (`serialAdapter.setSignals`) |
| CH340 port open | Opening the port may pulse EN/IO0 through the auto-reset circuit, rebooting the panel on every connect. | Check in the linked-mode milestone |
| Game list copies | Built-in wand games would be a fifth hand-kept copy of game tags, beside the four in AGENTS.md. | Flag in AGENTS.md when added |
| Clock and battery | The design shows "9:41" and "Panel 82%". No known RTC or battery gauge on this board. | Open questions |

## 5. Build order

Each milestone ends with something the user checks by eye on the board.

| # | Milestone | Done looks like |
|---|---|---|
| M0 | **Coexistence stress test.** Bench script: radio up first, then display and home screen, then PN532 on the shared bus. Loop: status poll every 2 s and count replies; NFC detect with the field on; a moving bar on screen; touch live. Every 10 s print `gc.mem_free`, largest internal free block, counts; log `reset_cause` at boot. Also 50 radio off/on cycles (as around an NFC write) with the UI up. | 30 min with wands answering, a card read on every tap, touch responsive, no drift, no reset, no `WiFi Out of Memory`. Worst case (card held, radio sending, finger on screen) passes. |
| M1 | UI kit and screen framework: helpers out of `home.py`, screen cache, back navigation, fixed-slot models, NFC target component. Flash budget table. | Home looks unchanged; Cards, Start a game, Send code and See list open placeholder screens and come back. |
| M2 | Roster + Roll call + screen 2. | Roll call fills tiles with real battery and signal; filters work; holding a tile makes that wand blink. |
| M3 | Targets send: start/stop to a MAC list (unicast with ACK) or everyone (broadcast twice). Stop on 1 and 6. | Stop with Everyone stops all wands; with 2 picked, only those 2 stop; bubble shows "N of M". |
| M4 | Screen 3 + game library (built-in + flash games). | Starting Freeze Dance on 2 picked wands starts only those. |
| M5 | Screen 4: distribute with UI progress, Pause, Retry, Start. | A flash game reaches 2 wands; rows go Waiting, Sending, Has it; wands launch it. |
| M6 | Screen 6, groups and nicknames, on-screen keyboard. | A rename and a saved group survive an EN reset; the group targets only its members. |
| M7 | Screen 5 with PN532: write sequence, Helper, My own, Read; radio paused while writing. | A written `getcode` card makes a wand pull from the panel; Read shows a card's text. |
| M8 | Linked mode (screens 7-9) and the ChatBroadcast changes. | Connecting ChatBroadcast shows 7. Link shows 8. Installing a game leaves touch working and the game in the list. Write on a checklist row opens 9; the written card ticks the row. The panel never reboots, and wands keep answering roll call throughout. Distribute progress shows on 8. Disconnecting returns to 1. |
| M9 | Zoom mode (binfonts) and sounds (if a speaker is fitted). | Zoom toggle shows the Resized layouts; write beeps. |
| M10 | PN5180 in place of PN532. | Cards 1-9 behave as with the PN532 through the screen. |

## 6. Open questions (recommended default in brackets)

Places where the design and existing behaviour disagree, or the design shows something nothing
provides. Each has a default so the build can proceed.

1. **PN532 wiring.** `board.py` notes that 0x24 (the PN532's address) answers on the touch bus. Is the
   reader on GPIO19/20, sharing the bus with the GT911? [Assume yes; M0 confirms with a scan.]
2. **Header Find and the radar button (Design 1 only).** The Resized page drops both; Find on a group
   has no Dial equivalent (find is one MAC). [Follow the Resized page: find lives on screen 2 (hold) and
   screen 6.]
3. **Pause on screen 4.** The Dial has cancel, not pause. [Pause holds the queue; in-flight pushes
   finish; Back cancels the rest, as `fleet.cancel` does.]
4. **Games filter tabs.** Design 1 has On wands / New / All; Resized has Ready / New. "On wands" can only
   mean "the panel sent it there". [Resized tabs: Ready = built-in games plus flash games the panel has
   sent to every target; New = flash games not yet sent.]
5. **Game colours** on tiles have no source. [Fixed colour per game from a small table in the library
   module; flash games get one from their slug.]
6. **Groups and nicknames.** ChatBroadcast keeps nicknames per browser in localStorage; the panel will
   keep its own. [Panel only; no sync. In linked mode the host can send names later.]
7. **Wall-clock times** ("9:41"). No RTC is known on this board. [Relative times ("2 min ago") from
   ticks; when linked, take the time from the host.]
8. **Panel battery** ("Panel 82%"). Source unknown. [Leave the slot empty until a gauge is confirmed.]
9. **Just charge** (screen 7). [Ignore host commands until unplugged or EN reset; answer `identity`
   only.]
10. **Device rows in the chat list.** Design 1 lists Icon Display and Sunny as chats. [A device gets a
    row once it has a nickname or a warning (low battery, not heard); tapping it opens screen 6.]
11. **"Blinking and buzzing" / "Blinked and buzzed"** on screen 6. Find has no reply; the panel knows only
    that it sent it, or got a radio ACK if sent unicast. [Send find unicast for the ACK; keep the
    designed text.]
12. **"Not heard - 6 min".** Bag3 wands send `status_report` only when polled. [Roster refreshes on roll call
    and on any message heard (`code_req`, `code_done`); no background polling. "Not heard" = missed the
    last roll call.]
13. **Panel identity to ChatBroadcast.** Reporting `broadcast_dial` needs no app change, but the app
    would then treat the panel as a Dial everywhere. [A new identity, `crowpanel`, added to
    `EXPECTED_DEVICES` and the Distribute gating.]
14. **Leaving linked mode.** The host sends nothing periodically, and the CH340 can't sense an unplug.
    [`unlink` from ChatBroadcast on disconnect; an EN reset also returns to standalone.]

## Verification

Per milestone, the user checks the "done" column on the board. Host-drivable parts (roll call, sends,
linked-mode commands) are driven over JSON on the UART; `python -m py_compile` on every module.
Hardware rules: `/dev/cu.usbserial-310`, `mpremote ... resume`, `lsof` first, EN resets only.
