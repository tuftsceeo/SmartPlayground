# Bag3 integration plan: wands, Splats, icon displays, NFC tags, ChatBroadcast, Simulator

## Status (2026-10-19, branch `october19demo`)

**Implemented, offline checks passing:** Phase 0; Phase 1 items 1.1–1.10 (1.8 dropped) and 1.11; Phase 2 A1–A7, including the solo games `soloecho` and `solotest` and the party games; Phase 4 items 4.1–4.5; Phase 5 items 5.1–5.2; Phase 6 items 6.1–6.3.

**Simulator, paused 2026-10-19:** 5.1–5.5 merged (bus, clock, real espnow_manager over the bus, `<sim-room>` panel registry, capabilities, display panel with `icon_host.py`, `tools/room_smoke.mjs` passing). 5.6/5.7 (Splats, virtual peers, `net` in the wand) are partial and uncommitted: saved as `w2f-simulator-splats-wip.patch` in this folder (apply with `git apply` from the repo root; untested, the Splat panel was not started). Not started: 5.8 headless mode + `tools/sim_run.mjs` (the `prompt_eval.mjs` simulation check is a stub until it exists), 5.9 ChatBroadcast preview mounting `<sim-room>` and the `game-icons-changed` reload, 5.10 remaining tests. Hardware session H4 waits on 5.9; H1–H3 do not.

**Known pre-existing devtest failures:** `boot_display.py`, `usb_link.py`, `nfc_display.py` (stub `code_puller` lacks `DEBUG_PULL`). `test_splat_companion.py` fails `test_copies_match` (Companion vs EUM `espnow_manager.py`). A8 (MockWand README "Splat games") is done.

**Awaiting hardware** (see "Hardware needs per task" below): gates G1 and G2; sessions 3.2, 3.3b, 3.4, 3.5 and 3.6; device confirmation of 1.1, 1.3/A2.4, 1.5, 1.6, 1.9, Phase 2 (including each `main.py` hook's `idf_largest` change), the 4.1 firmware side, 4.3 and 4.4.

## Context

A survey of `wands_with_splats` (HEAD `a60e471`) found that each device works on its own, and one wand-plus-display game (goalrace) has been played. Five gaps block the full system:
- There is no link from a wand to a Splat on the wand itself.
- ChatBroadcast assumes one wand.
- The Simulator runs one wand only.
- The display's card reader has never read a tag.
- Several small breakages and drifted copies.

An independent review (2026-10-19) checked this plan against the repo. Its corrections are folded in below and marked **[rev]**.

### Decisions

| Area | Decision |
|---|---|
| Wand↔Splat | **Direct pairing.** The Splat Companion is retired: marked legacy, not deleted. **Fallback:** if the gates fail, use `BroadcastCode/EspnowModem/` (EUM, ESP-NOW on a second board over UART; `MockWandEUM/` already exists). **[rev]** |
| Bag3 wand | **MockWand** (`BroadcastCode/MockWand/`). `Wand Module/` is legacy. |
| ChatBroadcast | Display-only send, wand-side Splat actions, party-game generation, NFC Station catalog push. Per-role wand files are deferred: SPEC §6 runs one `play()` on every wand, and `net.is_leader` picks the role. |
| Simulator | **One screen.** The wand is always shown. A Splat panel and a display panel appear only when the wand game uses them. Other party wands are **scripted virtual peers** on a virtual ESP-NOW bus. The display panel **runs the display's Python when the game has a display file**. |
| Icon editing | **A separate Icons view** in the ChatBroadcast workspace, independent of the Simulator. |
| Solo Splat games | **A path with no lobby** (decided 2026-10-19). A game that declares `SPLATS_LOCAL = n` runs on one wand with its own paired Splats. It gets no ESP-NOW traffic, no find wait and no button start. |

### What follows from these decisions
- **Splat-only games go away.** Splats are reachable only through a wand.
- **One Splat API for solo and party games.** A solo game declares `SPLATS_LOCAL`; a party game declares `SPLATS_MIN`, and a game can't declare both. Both kinds receive a `net` object with the same members. In a solo game:
  - `net` is a `SoloNet`: `is_leader` is `True` and `wands` holds only this wand.
  - `net.splat(i)` addresses the local Splats, and `poll()` services them.
  - `send()` raises, since there are no other wands.
  - Only `press`/`release` and `splat_lost`/`splat_back` events occur.

  A solo game can later become a party game by changing one constant.
- **`splat_api.py`'s source of truth moves to `MockWand/lib/`.**
- **Gates run before the pairing code is written.** Two unexplained board results (board `3101` found no Splat; board `1101` has slow sends) and memory under full load are tested with bench scripts first. **[rev]**
- **Device code obeys the memory-order rule.** Any change to `MockWand/main.py`, `IconDisplay/main.py`, `bbox_server.py`/`bdial_server.py` or `code_server.py` is a thin hook; the logic goes in lazily imported modules. Each such change records `memprobe`'s pre-ESP-NOW `idf_largest` before and after. **[rev]**

Paths are relative to `Bag3/Code/` unless stated.

### Branch
- **Create `october19demo`** from `origin/wands_with_splats` at `30bec5c`. That head is two commits past the survey's `a60e471`; both commits add `docs_and_design/2026-10-16-codeless-pairing/CONCEPT.md`, a pre-implementation concept.
- **All work, every subagent worktree merge, and every push go to `october19demo`** (`git push -u origin october19demo`).
- **Nothing is pushed to `wands_with_splats`.**

**The codeless-pairing concept is not in this plan's scope.** It reuses the SPEC §2 Splat-card pairing and the `SoloNet` path that Phase 2 builds, so nothing here blocks it.

---

## Phase 0: Record the decisions (docs only, main session)

1. **`AGENTS.md`:**
   - MockWand is the Bag3 wand; `Wand Module/` is legacy.
   - The Splat action source of truth moves to `BroadcastCode/MockWand/lib/splat_api.py`.
   - The Companion is retired; EUM is the documented fallback.
   - Device-code changes record the pre-radio `idf_largest` change. This is a project rule, written as one line alongside the existing memory-order rule.
2. **Add legacy banners** to `Wand Module/readme.md` and `BroadcastCode/SplatCompanion/README.md`.
3. **Edit** `BroadcastCode/docs_and_design/2026-10-07-splat-pairing/PLAN.md` and `SPEC.md`:
   - Remove the Companion and `Wand Module` items from PLAN Part C.
   - Remove "Companions are unaware of pairings" and the PEER-copy note from SPEC §10.
   - Add a "Decisions 2026-10-14/19" section.
   - Add the SPEC fixes from Phase 2 (`pw_find` reply, party cleanup).
   - Add a new SPEC §6 subsection, "Solo Splat games": `SPLATS_LOCAL`, the `SoloNet` members and events, the start check, and the rule that a game can't declare both `SPLATS_LOCAL` and `SPLATS_MIN`.
4. **Copy** this plan to `BroadcastCode/docs_and_design/2026-10-14-integration/PLAN.md`; status is tracked there.

## Phase 1: Small fixes (no hardware needed to write them)

| # | Fix | Files |
|---|---|---|
| 1.1 | **Firmware-installer imports:** `import("../../../BroadcastBox/BBoxFirmware/manifest.js")`, called with the page-relative base `"../BroadcastBox/BBoxFirmware/"` (`manifest.js:24` resolves `fetch` against the page) **[rev]**. Dial: `../../../BroadcastDial/BDialFirmware/manifest.js` with base `"../BroadcastDial/BDialFirmware/"`. Fix the stale comment at :12. | `ChatBroadcast/js/device/boxFirmwareInstaller.js:12-19` |
| 1.2 | **Simulator sync:** set `GAMES_SRC` to `BroadcastCode/MockWand`. Rewrite the `MANIFEST.json` paths (a third wrong path) and re-vendor `jumpin.py`. `--check` passes. | `Simulator/tools/sync_sources.py:29`, `vendor/MANIFEST.json` |
| 1.3 | **NFC Station tags:** add `splatecho`. Leave `MockWandEUM` as is: it has no `splatecho` module. | `Stations/NFC Station/game_tags.py:35` |
| 1.4 | **Reserved names:** reserve the display's built-in names (`scoreboard`, `goalrace` from `display_tags.GAME_TAGS`) and `unpair`. | `ChatBroadcast/js/gameName.js:32-47` |
| 1.5 | **Display game errors:** wrap `play_func(...)` at `main.py:296` **[rev line]** so a runtime error prints the traceback, emits an error JSON line, flashes a red `SHAPE_X` (reuse `_game_load_failed`, :264-281), unloads the game and returns to idle. Keep it to a few lines in `main.py`. | `BroadcastCode/IconDisplay/main.py` |
| 1.6 | **Wand game errors:** route runtime errors from `_start_play` (`main.py:501-509`) through `_game_load_failed`: red X, beeps, `{"type":"error"}`. Party cleanup belongs to `party.py` (A6), not here. | `BroadcastCode/MockWand/main.py` |
| 1.7 | **Stale devtest:** point its checks at `getSystemBlocks()` (`app.js:222`) and at `buildRequest.js:71-74` `sessionText`. | `BroadcastCode/tools/devtests/chatbroadcast_flow.mjs:184-195` |
| ~~1.8~~ | **Dropped [rev]:** the station's `json_link.py:101-108` already returns `{"type":"error","code":"cmd_failed",…}`. | — |
| 1.9 | **Rename `elepant` → `elephant`:** rename the icon and its PNG, regenerate `defaultIcons.js`, update `gallery.html:98`. | `IconDisplay/icons/`, `Stations/Icon Display Station/` |
| 1.10 | **Station icon copy:** add `--station` to `sync_icons.py`, which copies or checks the station's `icons/` (22 icons missing). | `ChatBroadcast/tools/sync_icons.py` |
| 1.11 | **Stale `BroadcastBox/…` paths** in Bag3 docs and comments. Skip `docs_and_design/old/` and `Live_Page/`. Runs last. | docs and comments |

## Phase 2: Wand pairing and party games (existing PLAN Part A, changed)

Follow `PLAN.md` A1–A8 and its "Rules for Part A". **Starts only after gates G1 and G2 (Phase 3) pass.** Changes to that plan:

**A1: libraries**
- Copy `splat_hub.py`, `splat_link.py`, `splat_api.py` and `ble_splat.py` into `MockWand/lib/`. These copies become canonical.
- Repoint `sync_splat_actions.py:31` **[rev line]** `SOURCE` at `MockWand/lib/splat_api.py`.
- The copy check covers `Bag3/Code/lib/ble_splat.py` against MockWand.

**A2: cards**
- Add `unpair` to `NFC Station/game_tags.py`.
- **New, A2.4: getting a Splat's MAC.** Web Bluetooth hides MACs, so teachers need another way to learn which MAC to write on a `splat-<MAC>` card. **[rev]**
  - A `scan_splats` JSON command lists nearby Splat MACs over serial. It reuses `scan_splats.py`, imported lazily.
  - The NFC Station's text entry writes `splat-<MAC>`.

**A3:** keep `MAX_SPLATS = 2`. Gate G2 sets the final value.

**A4/A5: boot and idle-loop changes.** Hooks only in `main.py`. The logic lives in `lib/pairing.py` and a new `lib/pair_idle.py`, imported after `enow.init()`. Record the `idf_largest` change.

**A6: SPEC fixes [rev]**
- The leader answers `pw_find` with a direct unicast `pw_lobby`. `pw_find` listens for 500 ms, but the lobby broadcasts every 1 s, and broadcasts lose 2–15% with BLE running.
- Lobby broadcast and heartbeat timing are module constants.
- `party.py` wraps the game in `try`/`finally`. The leader sends `pw_end`, a follower sends `pw_leave`, and local Splats are turned off. This runs on error, on stop, and on return.
- `MockWand/tests/fakes.py` holds the fake bus and fake `SplatLink`. It is written against the Splat API that A1 copies in.

**A6 new: solo path (`SoloNet`).**
- `party.py` (or a separate `lib/solo.py`, imported lazily) provides `SoloNet`, with the members listed under Decisions.
- `main.py` reads `SPLATS_LOCAL` after `_load_play()`. If the game declares both `SPLATS_LOCAL` and `SPLATS_MIN`, the load fails through `_game_load_failed`.
- **Start check:** at least `SPLATS_LOCAL` Splats must be paired and READY. Otherwise the wand shows amber error feedback and beeps, and the game does not start.
- `play()` receives `net=SoloNet(...)`. `finally` turns off the local Splats.
- **CPython tests:** not enough Splats, a Splat dropping during play, `send()` raising, the conflicting-constants load failure, and the cleanup on error.

**A6 new: protocol transcripts.**
- `test_party.py` writes recorded `pw_*` message sequences to `MockWand/tests/transcripts/*.json`.
- The Simulator's virtual peers (5.6) are tested against the same transcripts, so the two implementations stay in step.

**A7: games**
- Port `splatecho` as a solo game with `SPLATS_LOCAL = 1`.
- Add `solotest.py`: each button press cycles the local Splat through the identity palette.
- Keep the original `MockWand/splatecho.py` until the port is play-tested.

**Done when** `compile_check.sh`, the CPython tests, `boot_wand_pairing.py` and `test_party.py` pass.

**Optional:** also run `test_party.py` under the MicroPython unix port, if one can be built, to catch CPython-only code. **[rev]**

## Phase 3: Hardware gates and sessions

Run under `HARDWARE_PROTOCOL.md`: ask for ports, use `resume` on every `mpremote` call, and give numbered physical steps. Results go in `RESULTS-PartB.md` and `RESULTS-integration.md`.

| # | Session | When | If it fails |
|---|---|---|---|
| **G1** (was 3.1) | Board `3101` Splat scan after a power cycle | **Now, before Phase 2** | Fall back to EUM, or restrict to boards that pass |
| **G2** (was 3.3) | **Full-load bench, run now as a bench script** by extending `bench_wand_ble.py` **[rev]**. It loads `main.py`'s imports, ESP-NOW, the NFC reader, the LED matrix, BLE and 2 Splats, then **compiles a 32 KB game** with the Splat libraries loaded (`compile()` needs about 40 KB contiguous). Then 3 and 4 Splats, and a 15-minute soak. | **Now, before Phase 2** | Fall back to EUM. The result sets `MAX_SPLATS`. |
| 3.2 | Boards `1101` vs `3101`: firmware, `/lib` hashes, antenna pins, cable | Now | Not a gate; it sets expected latency |
| 3.4 | Display card read (`getcode`, `goalrace`) | Now | Display games start only by pull or `start_game` |
| 3.5 | Box (StickS3) wand round trip, plus the Dial's `BENCH_TEST_PLAN.md` | Now | The Dial is the only staging device |
| 3.3b | Full-load memory with the real pairing code (confirms G2) | After A4 | Back to the bench: compare against G2 |
| 3.6 | PLAN Part B (B1–B5), plus solo games (`splatecho`, `solotest`: start check, Splat dropout), plus Splat battery life with the idle glow on **[rev]** | After Phase 2 | Per PLAN |

## Phase 4: ChatBroadcast (`BroadcastCode/ChatBroadcast/`)

### 4.1 Display-only games
**App side:**
- Accept any game where at least one role has code. Change the wand-code checks in `updatePreview` (defined at `app.js:1806`), `startSendFlow` (:2075), `onSaveGame` (:1256) and `confirmSend` (:2219).
- The primary file is the first role that has code. Pass `role` to `uploadPayload`.
- Derive tags and hardware requirements from that role's code (:2093, :2254, :2280).
- The direct-to-wand install refuses a game with no wand file.
- Display-file size limit: start at 32,000 B in `upload.js` `validateGameCode`; set the final value after session 3.4.

**Box/Dial firmware (both PEER copies, same change) [rev]:**
- `_boot_scan_games` (`bbox_server.py:720-723`, `bdial_server.py:714`) enrols a slug that has only `_icon.py`.
- `code_server.set_game`/`_lookup` (:298-310) resolve the role from the files present. `set_game` falls back to `_icon` when `<slug>.py` is missing, so `arm()`'s `_file_ready()` (:354-356) succeeds.
- No new module-scope content. Record the `idf_largest` change.

### 4.2 Retire the Splat Companion role
- **Remove the `splat` role:** `roles.js:69-84`, the Splat tabs (`index.html:181,256`) and the Splat starter ideas (`starterIdeas.js`).
- **Keep `_splat` reserved:** add it explicitly to `RESERVED_SUFFIXES`, because devices still skip `_splat.py`.
- **Migrate saved games [rev]:** when library load (`app.js:1461-1470`) finds `roleCode.splat`, it shows a warning naming the game and keeps the code as a read-only attachment. It never drops it silently.
- **Knowledge files:** replace `knowledge/devices/splat_companion.md` with Splat content in `wand.md`, and edit the Companion mentions in `game_patterns.md`, `platform.md`, `policy.md`, `troubleshooting.md` and `ADDING_A_DEVICE.md`.
- **Tests:** update `chat_request_test.mjs:48-49`, `prompt_eval.mjs:84-87,125` and `chatbroadcast_flow.mjs:60-124`.

### 4.3 Party-game generation (SPEC §11)
- **Wand signature:** add `net=None` as optional (`roles.js`, and `signatureFor` at :97).
- **New `knowledge/party_games.md`** in `SHARED_KNOWLEDGE` (`buildRequest.js:27`). It covers:
  - the `net` table and events, and `SPLATS_MIN`/`SPLATS_MAX`
  - one `play()` for both roles
  - required handling of `leader_lost`/`end`
  - a steer toward turn-based designs
  - one pooled example and one messages example
  - "every player taps the same card"
  - **solo Splat games:** `SPLATS_LOCAL`, the `SoloNet` subset, and when to choose solo over party, with one solo example
- **Splat block in `buildRequest.js:58-62`:** reword to `net.splat(i)` and `net.local`.
- **Send-time checks on the wand role.** Refuse:
  - `net` used without the parameter
  - `SPLATS_MIN` or `SPLATS_LOCAL` without `net`
  - both constants in one game
  - invalid `SPLATS_MIN`/`MAX` values
  - `SPLATS_LOCAL` that isn't an int from 1 to `MAX_SPLATS` (gate G2 sets it)
  - `net.send` in a solo game **Keep the broad action-name regex** in `splatActionCheck.js:36-39` **[rev]**: it catches aliasing such as `s = net.splat(i)` and doesn't collide with `buz.play(name)`.
- **Generated-game simulation check [rev]:** `prompt_eval.mjs` runs each generated party game in the Simulator's headless mode for N scripted seconds, with virtual peers and Splats (5.6/5.7). It fails on an exception or on unhandled `leader_lost`/`end`.
- **Direct-USB install:** after installing, offer "install on another wand".
- **Write against the real `net` API:** 4.3 waits for W2-a to land `party.py`, so the prompt matches the code, not just the SPEC. **[rev]**

### 4.4 NFC Station catalog push
- **A sibling link class** `nfcStationLink.js` on top of `BboxLink`. It is not added to the Box/Dial `EXPECTED_DEVICES` list, so the station is never offered Box firmware. **[rev]**
- **Push:** builds `{"cmd":"catalog.set","index":{slug:{name,tags}}}` from each saved game's `buildHardwareReqs().tags`, and parses the `ok` or `cmd_failed` replies.
- **Events:** forwards `card_read`, `card_written` and `write_failed`.
- **Test:** a Node test for building the index.

### 4.5 Icons view (new; replaces in-preview icon editing)
- **A workspace view "Icons",** a sibling of the preview, reached from a workspace toolbar button. The preview's "Edit icons" button (`index.html:187`) and the Display tab's static viewer (`iconPanel.js`, `#icon-sim-panel` at `index.html:208`) are removed.
- **Lists every icon the game uses:** `iconNamesIn()` (`iconLibrary.js:223-234`) over the wand and display code, plus `getGameIcons()`. Each icon is marked built-in, custom, or **missing** (`missingIconsIn`, :241-248).
- **Selecting an icon opens the existing Icon Maker** in that view. Reuse the iframe (`iconmaker/?embed=1`), `wireIconMaker()`/`libraryBridge.js` (`app.js:415-432`) and the toolbar (`bindIconToolbar`, `app.js:312-372`). Move `#icon-drawer`'s contents (`index.html:269-323`) into the view.
- **After a save,** the Simulator's display panel reloads the game's icons (5.5). The prompt's icon list marks custom icons as custom (`buildRequest.js:71-75`).
- **Device tabs leave the preview:** `#device-tabs` (`index.html:172-185`) is removed. Per-role code editing stays in the code drawer's `#code-device-tabs`, now wand and display only. `updatePreview` stops choosing a pane by active role (`app.js:1819-1825`).

## Phase 5: One-screen Simulator (`Simulator/`)

**Layout:** a single screen with the existing `<wand-sim>` wand always shown. Output panels sit beside it and appear only when the wand game uses them:
- **Splat panel:** appears for solo games (`SPLATS_LOCAL`), party games (`SPLATS_MIN`), or code that uses `net`/`net.local`. It shows the local Splats, plus the virtual peers' Splats with an owner badge in party games. Solo games show no peer strip.
- **Display panel:** appears when the game has a `_icon.py` file, or the wand broadcasts dict messages. It runs the display's Python when the file exists; otherwise it shows a feed of the wand's messages.
- **Peer strip:** for party games, compact rows for each virtual peer (MAC, identity color, Splat count, a "drop" button), plus the bus log.

**Pyodide count:** at most two (the wand, plus the display when it has code). Splats and peers are plain JS. This replaces "one Pyodide per device" and the Worker question. **[rev]**

| # | Step | Key files |
|---|---|---|
| 5.1 | **Switch `vendor/lib` from Bag2 to `MockWand/lib`**, and vendor `goalrace`/`color_quest`/`finddevice`. **Treat it as a real port [rev]:** `leds.py` differs by 467 lines, so the renderer's shape and geometry need checking (25 LEDs). Re-record the golden-frame tests. `buzzer.py` becomes synced instead of hand-kept. Re-run `sync_sources --check` after every wave that touches `MockWand/lib`. | `tools/sync_sources.py`, `vendor/` |
| 5.2 | **Bus and shared clock:** `js/bus.js` routes by MAC or broadcast, with latency/drop/duplicate settings and a log. `js/clock.js` is one virtual clock that every `time_patch` and peer reads, so `WAND_LOST_MS` and the heartbeats agree across devices. **[rev]** | new `js/bus.js`, `js/clock.js`, `py/time_patch.py` |
| 5.3 | **Real radio stack:** a bus-backed `ESPNow` shim (`send`, `irecv`, peers, ACK from the bus). Vendor the real `espnow_manager.py`, **run through the AST transform** (blocking `irecv`) **[rev]**, with per-device MACs through `network.WLAN.config('mac')`. Dicts go out as JSON, which fixes the repr problem in `_as_text` (`sim_state.py:237-244`). The "Heard from…" panel becomes a bus peer that can send dict JSON. | `py/shims/`, `py/devices/`, `js/controls.js` |
| 5.4 | **Output-panel host:** `<sim-room>` wraps `<wand-sim>` and adds the panels and the peer strip, shown based on the wand code's capabilities. Extend `get_capabilities` (`runtime.py:382-421`) with `party`, `splats_local`, `splats_min/max`, `uses_display` and `has_display_file`. `<wand-sim>` itself stays as is. `Simulator/index.html` uses `<sim-room>`. | new `sim-room.js`, `py/runtime.py` |
| 5.5 | **Display panel:** a second Pyodide running `py/icon_host.py`, which copies `IconDisplay/main.py`'s idle loop (:600-697) without running `main()`. A sim `Matrix` emits logical `src` plus intensity, drawn with `iconmaker/js/pipeline/preview.js` `renderPreview`. The game's icons (`getGameIcons()` plus built-ins) are written into its virtual FS as `<slug>_icons/`, and reloaded on the 4.5 save event. With no display file, it renders the wand's message feed. | new `py/icon_host.py`, `js/panels/display.js` |
| 5.6 | **Splats and virtual peers in JS:** A Splat model (color, sound/note shown as text and audio, press button). Inside the wand's Pyodide a fake `SplatLink` and hub forward to it, so the real `splat_api.py` runs unchanged; local Splats are auto-paired. **Virtual peers** are JS bots that implement the follower side of `pw_*`: join the lobby, heartbeat, run pooled Splat commands on their own Splats, and forward presses. A scripted `msg` responder handles messages-model games. "Drop" tests `wand_lost`. A peer that acts as leader covers only lobby, start and end, for testing the follower path. **Tested against the A6 transcripts.** | new `js/panels/splat.js`, `js/peers.js`, `py/shims/` |
| 5.7 | **`net` in the wand:** `runtime._run_play` reads `play.__code__.co_argcount` (`runtime.py:503-507`) and passes `SoloNet` (solo) or the party `net`. Vendor `party.py`/`pairing.py` through the transform. | `py/runtime.py`, `vendor/` |
| 5.8 | **Headless mode** for the 4.3 generated-game simulation check: run `<sim-room>` for N virtual seconds with scripted peers, and report exceptions and unhandled events. | `sim-room.js`, new `tools/sim_run.mjs` |
| 5.9 | **ChatBroadcast preview:** `#preview-panel` mounts `<sim-room>` in place of `<wand-sim>`. `pushSimSource` (`app.js:1928`) hands it the wand and display code plus the game's icons. The detail view (`app.js:1508-1546`) uses `<sim-room>` too. | `ChatBroadcast/js/app.js`, `index.html:202-208` |
| 5.10 | **Tests:** pytest for the bus shim and classification (dict to `raw`, `start_game` with `name`), the icon host, the fake Splats and `net` arity. A peer-versus-transcript test. A Playwright smoke that runs a party game with 2 peers and goalrace with a display, checking the expected `pw_*` and `goal` lines in the bus log and the panels that appear. | `Simulator/tests/`, new `tools/room_smoke.mjs` |

**Not simulated** (stated in the README): heap and fragmentation, compile size, radio timing, BLE pacing, and peers running real game code.

## Phase 6: Keeping copies consistent

1. **Add** `BroadcastCode/tools/sync_game_tags.py --check`, with `MockWand/lib/game_tags.py` as the source. It covers the NFC Station's tags, the Simulator's `vendor/lib` and `gameName.js` `WAND_RESERVED`. `MockWandEUM` gets an explicit allowed difference (`splatecho`). It excludes `Bag3/Code/lib/`, `Live_Page/` and Bag1/Bag2.
2. **List** the three `--check` tools in AGENTS.md's existing "shared libraries" section as **available**, not as a required step before committing. AGENTS.md says not to add verification requirements unless asked. **[rev]**
3. **Superseded Companion docs:** the legacy banner covers the contradictions in the Companion READMEs.

## Parallel execution by subagents

**What a subagent needs:** a self-contained package with its spec in the repo (this plan, `SPEC.md`, `PLAN.md`, `AGENTS.md`), owned files no other package touches in that wave, and checks that run without hardware. Each package runs in its own worktree, and the main session merges between waves.

**Stays in the main session:** Phase 0, the Phase 3 sessions, 5.9, merging, and end-to-end verification.

**Wave 1 (after Phase 0; runs alongside gates G1/G2):**

| Package | Tasks | Owns |
|---|---|---|
| W1-a ChatBroadcast fixes | 1.1, 1.4, 1.7 | `boxFirmwareInstaller.js`, `gameName.js`, `chatbroadcast_flow.mjs` |
| W1-b Device fixes | 1.3, plus `unpair` in the station tags, and 1.5 | station `game_tags.py`, `IconDisplay/main.py` |
| W1-c Icons | 1.9, 1.10 | icon dirs, `sync_icons.py`, `defaultIcons.js`, `gallery.html` |
| W1-d Simulator base | 1.2, 5.1, 5.2 | `Simulator/tools/`, `vendor/`, new `bus.js`, `clock.js`, `time_patch.py` |
| W1-g Tag drift tool | 6.1 (written now, run in wave 3) | new tool |

**Wave 1b: after G1/G2 pass.** The two packages run in sequence on file ownership: W1-f's fakes are written against the API that W1-e copies in, so W1-f starts once W1-e's A1 lands.

| Package | Tasks | Owns |
|---|---|---|
| W1-e Wand pairing | 1.6, A1–A5, A2.4 | `MockWand/main.py`, `MockWand/lib/` (except `party.py`), `sync_splat_actions.py`, `splatActions.js` |
| W1-f Party library | A6 (`party.py`, SPEC fixes, fakes, transcripts) | `MockWand/lib/party.py`, `MockWand/tests/` |

**Wave 2:**

| Package | Tasks | Needs |
|---|---|---|
| W2-a Wand games | A6.2 (hooks in `main.py`), A7, A8 | W1-e, W1-f |
| W2-b ChatBroadcast roles | 4.2, then the 4.1 app side | W1-a |
| W2-c Box/Dial firmware | The 4.1 firmware side (`_boot_scan_games`, `set_game`), in both PEER copies | none |
| W2-d NFC catalog push | 4.4: a new link class; one hook in `app.js`, merged after W2-b | none |
| W2-e Simulator radio and panels | 5.3, 5.4, 5.5 | W1-d |
| W2-f Simulator Splats and peers | 5.6, 5.7 | W1-d, W1-f (transcripts) |

**Wave 3:**

| Package | Tasks | Needs |
|---|---|---|
| W3-a ChatBroadcast party generation | 4.3 | W2-a, W2-b, 5.8 |
| W3-b Icons view | 4.5 | W2-b (`app.js`, `index.html` ownership) |
| W3-c Simulator headless mode and tests | 5.8, 5.10 | W2-e, W2-f |
| W3-d Docs sweep | 1.11, 6.2, 6.3 | everything else |

**Then, in the main session:** 5.9, re-run `sync_sources --check`, and the full verification.

## Hardware needs per task

The tags in the second column mean:
- **None:** finished with offline checks alone.
- **Confirm:** code and offline checks are done by a subagent, and the task closes after a short device check.
- **Gate:** a hardware result decides whether later work proceeds.

| Task | Hardware | Check |
|---|---|---|
| Phase 0, 1.2, 1.4, 1.7, 1.10, 1.11, 4.2, 4.5, Phase 5, Phase 6 | None | |
| 1.1 | Confirm | Install firmware from ChatBroadcast onto a Box or Dial |
| 1.3, A2.4 | Confirm | Write `splatecho`, `unpair` and `splat-<MAC>` cards on the station; `scan_splats` lists MACs |
| 1.5, 1.6 | Confirm | A game that raises shows a red X and the device returns to idle. Record the `idf_largest` change. |
| 1.9 | Confirm | The display shows `elephant` |
| G1, G2 | **Gate** | See Phase 3 |
| 3.2 | Measure | |
| 3.4, 3.5 | **Gate** (scope) | See Phase 3 |
| Phase 2 | Confirm, through 3.3b and 3.6 | Includes the `idf_largest` change for each `main.py` hook |
| 4.1 | Required (firmware side) | A display-only game is listed, armed and pulled by the display. Record the Box/Dial `idf_largest` change. |
| 4.3 | Confirm | Play a generated party game on wands; try "install on another wand" |
| 4.4 | Required | Push the catalog, then write cards from it |

**Bench sessions:**

| Session | When | Covers |
|---|---|---|
| **H1** | Now | G1, G2, 3.2, 3.4, 3.5 |
| **H2** | After waves 1/1b | 3.3b, plus the checks for 1.1, 1.3, 1.5, 1.6, 1.9, A2.4 |
| **H3** | After wave 2 | 3.6 (Part B plus battery), 4.1, 4.4 |
| **H4** | After 5.9 | Whole system: generate, preview, send, pull, pair, play, write cards, and 4.3 |

## Verification

**Offline, each wave:**
- `tools/devtests/compile_check.sh`.
- `sync_icons.py --check`, `sync_splat_actions.py --check`, `sync_game_tags.py --check`, `Simulator/tools/sync_sources.py --check`.
- `node` `chat_request_test.mjs`, `check_tags.mjs`, `prompt_eval.mjs --dry-run`.
- devtests `chatbroadcast_flow.mjs`, `role_state.mjs`, `icon_panel.mjs`.
- The MockWand CPython tests, `boot_wand_pairing.py`, `test_party.py`, the peer-versus-transcript test.
- `cd Simulator && python3 -m pytest -q` (needs `pytest` and `pytest-asyncio`).
- `chat_ui_smoke.mjs` and `room_smoke.mjs`.

**Browser:** serve `Bag3/Code/`.
- Generate a solo Splat game. The preview shows the wand and the Splat panel, with no peer strip and no lobby.
- Generate a party game. The preview shows the wand, the Splat panel and 2 peers.
- Generate goalrace. The display panel appears and reacts to `goal`.
- Edit an icon in the Icons view, and the display panel updates.
- Send to a Box. Send a display-only game. Push the catalog to the NFC Station.

**Hardware:** sessions H1–H4 above. Results go in `RESULTS-PartB.md` and `RESULTS-integration.md`.

## Open decisions (not in this plan; the reviewer's suggestions)
- **Party coordination:** a coordinator device without BLE (display, Box or a spare C6), or a "leader card", instead of the wand-leader model.
- **Single source of truth:** one manifest generating tags, icons and Splat action lists, including Live_Page.
