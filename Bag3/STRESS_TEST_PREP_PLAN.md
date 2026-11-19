# Bag3 stress-test prep plan (written 2026-11-14; closed 2026-11-19)

**Closed.** The stress test ran on 2026-11-18. This file is now a record: the outcome below,
then the plan as it stood. Open work moves to the debrief
(`Code/docs_and_design/2026-11-18-stress-test-debrief.md`) and to `Code/known_issues/`.

## Outcome (recorded 2026-11-19 from the repo)

Sources: the two unattended bench reports (`STRESS_TEST_UNATTENDED_2026-11-16.md`,
`STRESS_TEST_UNATTENDED_2026-11-17.md`), the test-day debrief and bench results
(`Code/docs_and_design/2026-11-18-stress-test-debrief.md` and
`2026-11-18-multi-controller-bench/`), the known-issue notes and the commits. "On hardware"
means a serial log in those reports, almost all read by an agent; nothing here was re-run.

The hosted app was promoted on 2026-11-18 (`640a9c2b`) and reached `September_2026`, the
deploy branch, through PR #191 before the test. It included the S10 fixes.

### Steps

| Step | What | Result |
|---|---|---|
| S0 | Bundle and baseline | Done. Bundle check up to date on 11-17 |
| S1 | Player wands wait for the host | In code. Never run on hardware: the bench wand was a host (11-16) and the Dial cannot send `start_game` (11-17) |
| S2 | Three slots on wands and displays | Passed on hardware 11-16 (eviction by age and by `replace`); display eviction passed 11-17 |
| S3 | Slot picker in the app | In code; per-device replace added 11-17 (`eeba96ab`, `36035868`). Replace passed from the Dial 11-17 |
| S4 | Dial serves without arming | Passed on hardware (11-14, 11-17) |
| S5 | Dial reconnect; upload without restart | Reconnect bug never reproduced. Upload without restart passed: 10 games, no reset (11-17) |
| S6, S7 | Simulator modes; small fixes | Done |
| S8 | Test-day kit | Dropped |
| S9 | Promote to `Live_Page` | Done 11-18 and deployed |
| S10 | Generated-game fixes | In code 11-16 and deployed; no person-checked result recorded |
| S11 | Dial keyboard stall (D2, D3) | Bench steps not run. The stall was not seen on 11-17. Still open |
| S12 | Box: no arming, fleet | No arming and scan/distribute passed 11-16; 60-minute soak with no reset. Range, battery and a card tap during a distribute untested |
| S13 | Waveshare mockup | Merged; no record of it running on the board |

### Sitting blocks (2026-11-16 plan)

The single sitting was replaced by unattended agent runs on 11-16/17 and the test itself.

| Block | Result |
|---|---|
| 1 Host and Splats | Host wand booted with 4 Splats (log: `idfmax` 10240 after BLE) and ran a pulled host game. Fifth-Splat tap and the palette check not recorded |
| 2 Dial | Upload without restart, distribute to 3 wands and replace passed (11-17, reported by another agent; logs not in the repo). The keyboard sequence was not run |
| 3 Box | See S12 |
| 4 Icon display and CrowPanel | Display free space 924 KB of 2048 KB (11-17, reported). CrowPanel scan and distribute passed (11-16). Display station mode (show, dance) not seen; the display's USB was silent on 11-17 |
| 5 Dry run | Replaced by the test itself |
| 6 Waveshare | Not recorded |

### Fixed during the prep window

- A Splat host dropped a push that arrived mid-game: fixed in code 11-17 (`3c897264`), not re-run.
- The wand ignored Ctrl-C once stdin filled: fixed and passed on hardware 11-17.
- The wand's boot countdown went from 30 s to 2 s (`cddfcd32`).
- Controllers fail a push at once when they hold no file for the device's kind (`36035868`).
- A host wand returns to player after two restarts with no Splat (`splat_host.py`, 11-17).

### What the test found (2026-11-18, 8 controllers, 15+ devices)

Details and ideas are in the debrief.

- The device list varied (12, then 2, then 5). Bench runs the same afternoon traced this to
  polls from several controllers pushing back each device's reply, with only 4 of 16 reply
  slots in use. Card-tap pulls kept working throughout.
- Find Me ends a running game, and a landed Find makes the device drop out of later lists.
- Teachers could not tell which wand was which, wanted a map of devices and Splats, found the
  Splat host confusing, and saw every USB port in the picker.
- Some teachers liked the interview; others wanted a form.
- The Box dropped off USB during a bench run and stayed silent (debrief, "Find control").

### Still open

| Item | Where |
|---|---|
| Device list, Find Me, room view, roster | `known_issues/2026-11-18-stress-test-find-and-scan.md`, debrief |
| Dial keyboard stall (D2) and the lines after a soft reset (D3) | `known_issues/2026-11-14-dial-keyboard-send-stall.md` |
| Player wait-for-host never run on hardware | S1 |
| Wand panic when Ctrl-C lands during boot | `known_issues/2026-11-17-wand-ctrlc-boot-crash.md` |
| Icon display: icons never pruned; USB silent while the radio works | `known_issues/2026-11-16-icon-store-full.md`, 11-17 report |
| Box: range, battery, card tap during a distribute; the USB drop on 11-18; reader detection (WS1850S or PN532) | `known_issues/2026-11-15-box-fleet-port.md`, 11-16 report |
| Splat palette size (12 to 18 colors) | your call; no result recorded |
| 13 `splat_game_check_test` cases, 1 `check_tags` case, 3 `prompt_eval --self-test-sim` cases | 11-17 report, Part 0 |
| Hold-to-start clarity (U2) | `known_issues/2026-11-14-hold-interactions-ux.md` |

## Context

Six volunteer "teachers", each with a controller (Broadcast Box, Dial, CrowPanel, possibly a new
mini panel), a table of wands, Splats and icon displays, and the Bag3 M5Paper Remote. They will
generate their own games in ChatBroadcast. The goal is to break things and collect feedback, so
functionality stays in; prep only removes failures that would hide the interesting ones.

What the advisor review found (branch `origin/ccr-eec157d8-pkam3d`):

- The W1-W6 firmware has only had syntax checks. `Wand Module/flash_bundle/` is stale (no
  `signals.py`, no W6 games).
- A player wand gives up looking for a Splat host after about 10 s (`lobby_game.py:41`), but the
  Dial pushes one device every 2.5 s (`fleet.py:28`), so a distributed host game shows a red X on
  early wands.
- Pulled games pile up in `/games` on wands and icon displays with no limit.
- The Dial and Box still gate serving behind arm/disarm (`known_issues/2026-11-02-dial-box-arm-serving.md`).
- ChatBroadcast shows a wrong connect state after the Dial is unplugged and replugged (user report).
- The practice window's Simulator runs the old game-mode rules (`Simulator/py/runtime.py:706-718`,
  `sim-room.js:129`).
- Host memory with 4 Splats and a pulled game has never been measured.

Decisions already made by the user:

- Controllers hold any number of games; warn above ten, never force. Wands and icon displays are
  capped at three custom games.
- Class interference and remixing are not concerns for this test. No guardrails that teachers
  would not get.
- CrowPanel is in. Paper remotes are in scope.
- Slot design (three vs one, how the paper remote fits) is a question for the testers.
- The Splat palette size is the user's call. The note that six colors "were read as distinct"
  (`2026-11-13-splat-host-status-overview.md:53`) was an agent's claim, not something the user
  saw. The user expects 12 to 18 colors to be clear.

Assumption to confirm: in the slot status, "role" means the game's mode (solo, host game, plain
lobby, ordinary), and the wand's own role (player or `splat_host`) is reported once per device.

Paths: `Bag3/Code/BroadcastCode/` was removed on 2026-11-14. ChatBroadcast is `Bag3/Code/ChatBroadcast/`,
and its former `tools/` and `docs_and_design/` are merged into `Bag3/Code/tools/` and
`Bag3/Code/docs_and_design/`. Paths in this plan are relative to `Bag3/Code/` unless they start
with `Bag3/`. The review behind this plan is
`Bag3/Code/docs_and_design/2026-11-14-advisor-review.md`.

## Status on 2026-11-16, before the test (superseded by the outcome above)

Test day is Wednesday 2026-11-18. **One branch holds everything: `Chat_to_Tap_Doggle`.** Agents
start from it and pull it before each commit. `ccr-eec157d8-pkam3d` is kept level with it.

| Step | What | State |
|---|---|---|
| S0, S6, S7 | Bundle, Simulator game modes, small fixes | Done; checks pass |
| S1, S2, S3 | Wait for host, three slots, slot picker | Written; partly seen on hardware 11-14 |
| S4 | Dial serves without arming | Written; first hardware evidence 11-14 |
| S5 | Dial reconnect; upload without restart | Reconnect bug not reproduced. Upload written, not bench-proven |
| S10 | Generated-game fixes | Written 11-16; node tests pass; not yet tried by a person |
| S11 | Dial keyboard and distribute stall | Step 1 (code reading) done; bench steps open |
| S12 | Box: no arming, fleet scan and distribute | Written; never run on a Box |
| S13 | Waveshare 1.9 mockup | Merged 11-16; never run on the board |
| S9 | Promote to `Live_Page` | See the end of this section |
| S8 | Test-day kit | Dropped |

S10 and S11 were missing from this file between 2026-11-14 and 2026-11-16 (deleted by mistake
with S8) and are restored below.

Found in review on 2026-11-16, each recorded in `Code/known_issues/`:

- Box radio power is low (8 dBm); scan and distribute range is unmeasured (`2026-11-15-box-fleet-port.md`).
- The icon display carries 250 icons (835 KB). A pull onto a full flash now fails cleanly, but
  free space on a real unit is unmeasured (`2026-11-16-icon-store-full.md`).
- The Dial clears a game's old icons before a re-sent upload is verified (`2026-11-14-dial-upload-during-pull.md`).

### The sitting: six blocks in one session, about 2.5 hours

At most 3 devices on USB. Each block is run by the agent that prepared it; that agent sends
one message with numbered steps, flashes at the start of its block, and keeps a serial capture
running in the background. If a block fails in its first minutes, the agent stops and reports;
move to the next block and come back.

| # | Block | Min | On USB | You do | It answers |
|---|---|---|---|---|---|
| 1 | Host and Splats | 25 | host wand, player wand | Pair 4 Splats; start a built-in host game; pull one custom host game and start it; tap a fifth Splat; step one Splat through 16 colors (`tools/devtests/splatcolors.py`) | Host memory with 4 Splats (sets Splats per host for Wednesday); slot refusals; your list of clear colors |
| 2 | Dial | 25 | add the Dial | Send a game (USB should stay up); re-send a game that has icons; open the keyboard and distribute at once; distribute while turning the dial; distribute a host game with the host wand last; send a fourth game and pick one to replace | Upload without restart; D2 and D3; no red X while waiting; replace works; scan shows slots |
| 3 | Box | 25 | swap the Dial for the Box | Pull by card without arming; send a second game; scan, find and distribute at table distance, then about 3 m and 6 m; tap a card during a distribute; repeat one distribute with the Box on battery | No arming; Box fleet; range; any silent reset |
| 4 | Icon display and CrowPanel | 25 | icon display, CrowPanel, 1 wand | Read the free-space line; play Move Mixer and share a dance; pull a display game; pull by card from the CrowPanel and run one scan | Display free space; display station mode; CrowPanel serves |
| 5 | Dry run | 30 | one controller, host wand (logs only) | From `Live_Page/` served locally: a fresh prompt to a played solo game, then a host game | End to end, as a volunteer would do it |
| 6 | Waveshare look | 10 | Waveshare board | Flash the mockup; photograph each of the seven screens | First look only; not part of Wednesday |

Cut order if time runs short: block 6, the CrowPanel half of 4, Box fleet in 3 (card pulls still
work), the battery repeat in 3. Do not cut block 1, the first two steps of 2, or block 5.

What each result decides:

- Block 1 fails at 4 Splats: choose 2 or 3 per host for Wednesday.
- Block 2 upload fails: turn it off in the app (`supportsJsonUpload` in
  `ChatBroadcast/js/device/jsonGameUpload.js`); sends restart the Dial as before.
- Block 3 resets silently: the Box goes to Wednesday without fleet; reopen `2026-09-01-bbox-usb-reboots.md`.
- Block 4 free space under about 300 KB: trim the display's icon set before flashing.

After the sitting: fixes from the blocks, then S9 again if ChatBroadcast, the Simulator or the
Icon Maker changed, then flashing every device (H7, two blocks of 3 devices at a time) and the
user's push to the deploy branch.

## Merged from `Chat_to_Tap_Doggle` on 2026-11-14, and what it changes here

- **Simulator location.** That branch had moved `Simulator/` into `BroadcastCode/`. After the
  merge it stays at `Bag3/Code/Simulator/`, beside `Bag3/Code/ChatBroadcast/`, which gives the
  same sibling layout as `Live_Page/`. No step changes.
- **Simulator display fix** (`Simulator/js/panels/display.js`): a display got `start_game` twice
  on load. Merged; S6 does not touch that file.
- **`Live_Page/` copies of ChatBroadcast and Simulator** were refreshed from that branch, so they
  predate the W1-W6 game modes (no `splat_host_games.md`, older `splatGameCheck.js`). The hosted
  site deploys from `September_2026` (`.github/workflows/static.yml`). **Decided 2026-11-14:**
  teachers and volunteers use the hosted `Live_Page/` version, and the user pushes the
  bench-tested build there. Step S9 below re-copies it; phase H6 runs against that copy.
- **Flasher** (`Live_Page/Flasher/`) now lists the Broadcast Box, Dial, Icon Display and
  CrowPanel, and reads the wand from `Wand Module/flash_bundle/flash_manifest.json` at a chosen
  branch. S0's regenerated bundle is therefore what the Flasher installs. For H7, adding the
  frozen branch to `Flasher/js/devices.js` (`REFS`) and serving the Flasher locally would let
  wands be flashed from the browser instead of by `mpremote`; S0 should check this and report.
- **`tools/wandtest.py`** (user's bench script, 60 LEDs in 5 rows) and
  **`Experiments/Waveshare19_Controller/`** (display and backlight probes) are new. Neither is
  part of the test firmware. A Waveshare table, if there is one, runs like a Box table: cards
  only, no distribute.
- **Unchanged failures:** `Simulator/tools/room_smoke.mjs` fails on both branches; the other
  failing checks are the ones already listed in this plan.

## Slot design for this test (minimal diff)

Games stay as `/games/<slug>.py` because the wand imports by slug (`lib/game_store.py`). No slot
directories.

- **Device (wand, icon display):** keep `/games/slots.json`, a list of up to three slugs in pull
  order. After a successful pull, if there are more than three, delete the slug named in the
  push's optional `"replace"` field, else the oldest, with its `<slug>_icons` folder. Built-ins
  do not count.
- **Status:** `status_report` adds `"role"` (device role) and `"g": [[slug, mode], ...]` for the
  slots. Three 16-character slugs fit well inside the 250-byte ESP-NOW limit.
- **Controller and app (Dial, CrowPanel):** the distribute overlay shows each device's slots from
  the scan. If any target is full, the teacher picks one game to replace; devices that do not hold
  that game drop their oldest. `code_push` carries `"replace"`.
- **Box and card taps:** no picker; the device drops its oldest.
- **Paper remote:** no change. It stays a fixed launcher for built-ins and stop.
- **Controller clean-up:** ChatBroadcast shows a note when the controller holds more than ten games.

## Rules every agent prompt starts with

Paste this block at the top of each prompt below.

```
You are working in the SmartPlayground repo, Bag3 only. Start from origin/ccr-eec157d8-pkam3d.
Ask the user which branch to commit to before your first commit. Do not push or open a PR
unless asked.

Read first: AGENTS.md, Bag3/Code/known_issues/README.md, and the plan at
Bag3/STRESS_TEST_PREP_PLAN.md.
Do not re-test issues recorded in known_issues/. Keep the diff small; no refactors. Device code
is MicroPython: no type annotations, `python -m py_compile` is the only static check, nothing
may allocate before the radio comes up, and shared libraries are per-tree copies (say which tree
you changed).

Talking to the user:
- The user is building hardware and switching between several strands of work. Assume they have
  not seen your tool calls, reasoning or opened files. Every report says: what you were asked to
  do, what is done, what is not, what you need from them.
- During any run of more than a few tool calls, send a one-line update: where things stand and
  what you are about to do.
- Never state that hardware behaved a certain way unless the user told you they saw it. Say
  "the log shows" for what you read and "you reported" for what they saw.

Hardware (only if this task needs it):
- Load the bag3-hardware-protocol skill and read Bag3/Code/HARDWARE_PROTOCOL.md first.
- Ask which board is on which port and which machine and shell you are on (the docs record both
  macOS /dev/cu.* with python3 and Windows COM ports with python). Ask before opening a port.
- Run every hardware command in the background, never the foreground. Check it within 10 s; if
  it has not made progress, stop it, find what holds the port, and tell the user. While one is
  running, check it at least once a minute and say what you see.
- At most 3 devices on USB at once.
- The user's hands-on time comes in 15 to 30 minute blocks. Before a block, send one message
  with: the goal, the devices and ports needed, numbered physical steps, what to report back,
  and the expected length. Do all flashing and setup that needs no hands before the block
  starts. If the block runs out, stop and report; do not ask for more time mid-block.
```

## Prep steps, each as a prompt

Order: S0 first. S1, S2, S4, S6, S7 can run in parallel sessions. S3 follows S2. S5 needs a Dial.
S8 is dropped. S12 (Box) and S13 (Waveshare mockup) were added 2026-11-14; S13 is independent of the test.
S10 and S11 came from the 2026-11-14 hands-on findings; S10 runs before S9, S11 needs a Dial.
S9 runs last, before phase H6, and again if anything in ChatBroadcast or the Simulator changes after it.

### S0. Bundle and baseline (no hardware)

```
Task: make the wand firmware flashable and confirm it is syntactically sound.
1. Regenerate Bag3/Code/Wand Module/flash_bundle/ with tools/build_wand_bundle.py so it includes
   lib/signals.py, lib/splat_host.py, boot.py and every file in games/. Check the manifest lists
   them.
2. Run python -m py_compile on every .py under Wand Module/ and Stations/IconDisplay/, and
   node --check on the ChatBroadcast js files changed since wand-splat-update.
3. Run the four read-only checks and record results without fixing them:
   ChatBroadcast/tools/sync_icons.py --check, sync_splat_actions.py --check,
   node ChatBroadcast/tools/check_tags.mjs, Simulator/tools/sync_sources.py --check.
4. Check the Bag3 M5Paper Remote (TeacherTools/M5Paper Remote/): compare its game_tags.py and
   config.py catalog with Wand Module/lib/game_tags.py. Report differences; do not reconcile.
Report: what is in the bundle, each check's result, the paper remote differences.
```

### S1. Player wands wait for the host

```
Task: stop a distributed Splat host game from failing on wands that pull before the host.
In Bag3/Code/Wand Module/lib/lobby_game.py, _wait_for_host() gives up after HOST_FIND_TRIES
(about 10 s) and main.py then shows a red X. Change it to keep searching, with the existing
spinner, until a stop card, an ESP-NOW stop or start_game, or a long ceiling of about 3 minutes.
Keep the unconditional sleep in the loop. Do not change the Dial.
Then update the copy in Simulator/vendor only if S6 has not already resynced it; otherwise leave
it and say so.
Check: py_compile. Report the new exit conditions and what the wand shows while waiting.
```

### S2. Three game slots on wands and icon displays

```
Task: cap custom games on the wand and the icon display at three, and report them.
Read the "Slot design for this test" section of the plan. Reuse Wand Module/lib/game_store.py
(slugs(), path(), exists()) and the pull path in main.py (_espnow_pull_and_launch) and
lib/espnow_code.py.
1. Add /games/slots.json handling to game_store.py: record a slug after a successful pull;
   if more than three, remove the slug named by the push's "replace" field, else the oldest,
   including its <slug>_icons folder and any loaded module. Built-in games never count.
   A missing or corrupt slots.json is rebuilt from slugs().
2. Pass "replace" through from the code_push message (main.py _queue_push) to the pull.
3. Add "role" and "g" to status_report in lib/espnow_manager.py. "g" is a list of
   [slug, mode] where mode is one letter: s solo, h host game, l plain lobby, o ordinary.
   Compute it without importing the game (a text scan of the first lines for the declaration
   names), lazily, after the radio is up. Keep the payload under 250 bytes.
4. Do the same in Stations/IconDisplay (its own espnow_manager.py copy and game storage). Say
   which trees you changed. Do not touch Bag2 or the Simulator. Do not touch IconEditor/ either (icon authoring tools).
Check: py_compile, and an off-device test of the slot list logic run with plain Python.
Report: the file format, the eviction rule, the exact status_report shape with a sample.
```

### S3. Controllers and ChatBroadcast: show slots, pick what to replace

```
Task: let a teacher see each device's three slots and choose what to overwrite. Depends on S2;
read its status_report shape from the code.
1. Dial: TeacherTools/BroadcastDial/BDialFirmware/fleet.py passes "role" and "g" through in the
   status_report it forwards, and accepts an optional "replace" slug in fleet.distribute, which
   it adds to each code_push.
2. CrowPanel: make the same change in Experiments/CrowPanel5_Display/fleet.py. It is a separate
   copy; say what differs between the two.
3. ChatBroadcast js/distribute.js: show each scanned device's slots and role. If any selected
   device has three games and does not already hold this one, ask which game to replace before
   sending. One choice applies to all selected devices.
4. ChatBroadcast: when the connected controller lists more than ten games, show a one-line
   clean-up note. Never block.
Leave the Box alone here; S12 step 3 gives it fleet commands. Check: py_compile, node --check,
node tools/distribute_test.mjs. Report with a description of what the teacher sees.
```

### S4. Dial serves without arming

```
Task: remove the arm/disarm gate on the Dial. Read
Bag3/Code/known_issues/2026-11-02-dial-box-arm-serving.md; state the issue in one sentence and
get the user's confirmation before changing code (AGENTS.md rule for known issues).
Port the CrowPanel change (commits 784d79f and 218433b, Experiments/CrowPanel5_Display/
code_link.py radio_on/radio_off) to TeacherTools/BroadcastDial/BDialFirmware/code_link.py and
bdial_server.py: radio and code server on by default, paused only during an NFC read or write.
Keep the arm and disarm serial commands as accepted no-ops so an older app does not error.
Then assess the Box: list what the same change would touch and how long it would take, and ask
the user whether to do it before the test. Check: py_compile. Update the known-issue note.
```

### S5. Dial reconnect state in ChatBroadcast (needs a Dial)

```
Task: fix the state the app gets into when the Dial is unplugged at a bad moment and plugged
back in. The user sees: connected, then disconnected, and clicking the disconnected control
gives an error that the Dial is already connected. Suspect: the auto-reconnect path
(js/app.js tryAutoReconnect, about lines 1080-1134 and 2938-2970, and js/device/serialAdapter.js)
reopens the port without the visible state following.
1. Read those paths and write down, in three or four sentences, the sequence you think causes it.
2. Reproduce with the user and the app's debug log before changing anything. This needs one
   hands-on block: ask for it using the block format in the rules.
3. Make the smallest fix: one place owns the link state, and both the manual button and the
   auto-reconnect go through it.
Report the cause as the log shows it, the fix, and the steps for the user to confirm.
4. (Added 2026-11-14, after step 3. Planning decision 4: do this for the Dial before the test,
   in its own session, with the raw-REPL path kept as the fallback; the Box only if time
   allows. If it is not bench-proven by the end of day 2, ship the fallback.) Send games without a reset. Today Send to device drops the
   Dial and the Box into the raw REPL, writes the files and soft-resets
   (js/device/boxFirmwareInstaller.js pushPayload), which drops USB and goes through the same
   reconnect path every time; it also clears the Dial's pull counts. Add a chunked game-upload
   command on the JSON link (bdial_server.py and bbox_server.py): write to /flash/games, then
   rescan the game list, with the program and radio left running. Switch ChatBroadcast to it for
   the Dial and Box and keep the raw-REPL path as a fallback for older firmware. Do not restart
   the program in place after a REPL session (the CrowPanel's meta.resume): the radio needs its
   memory claimed at boot (AGENTS.md).
```

### S6. Simulator matches the wand's game modes

```
Task: make the practice window agree with the wand. This is items 1 to 4 of W3b in
Bag3/Code/docs_and_design/2026-11-13-splat-host-completion-plan.md. Do not do
items 5 to 7.
1. Run Simulator/tools/sync_sources.py, remove the deleted lobbytest, relaycolor and splattag
   games from its manifest and vendor folder, then run --check until it passes.
2. In Simulator/py/runtime.py, replace _splat_limits with the rules from
   Wand Module/main.py _splat_limits and _splats_local (copy them; do not rewrite them).
3. For a SPLATS_LOCAL game, pass the wand's Splat handle to play() and refuse to start with too
   few Splats, as main.py _run_games does.
4. In Simulator/sim-room.js and js/panels/wands.js, read the `splats` setting instead of
   `wand_splats`.
Check in a browser with Playwright (already installed): colorpads (solo, 2 Splats), a
PLAYERS_MIN lobby with 2 wands, and host_splattag with a 4-Splat host. Take screenshots.
Report which of the three ran, with the screenshots.
```

### S7. Small firmware and knowledge fixes

```
Task: five small changes. Keep each to a few lines.
1. Wand Module/main.py about line 630: when a Splat host wand is given a game that is not a
   host game, show the red X as well as the reject sound.
2. Wand Module/main.py: when a solo game has too few Splats, show a distinct shape instead of
   the generic load failure. Reuse an existing shape from lib/leds.py.
3. ChatBroadcast/knowledge/game_patterns.md: change the role key in a game's own messages from
   "to" to "for" (lines 35 and 66-70), because "to" now means a device MAC in display station
   mode.
4. ChatBroadcast/knowledge/platform.md: add one sentence listing message types a game must not
   use as its own: stop, score, song, song_ack, colors, splat_config, start_game, show, dance,
   and anything starting with pw_. Take the list from Wand Module/lib/espnow_manager.py poll().
5. Docs: in docs_and_design/2026-11-13-splat-host-status-overview.md, mark the "all 30 pairs
   were read as distinct" line as an agent's reading that the user has not confirmed, and record
   that the user expects 12 to 18 colors to be clear and will decide the palette. Fix the stale
   comment at main.py:285 and the AGENTS.md line naming SplatCompanion's splat_api.py as the
   source of truth (it is Wand Module/lib/splat_api.py).
Check: py_compile; node tools/chat_request_test.mjs. Report each change in one line.
```

### S8. Test-day kit: dropped

Dropped by the user on 2026-11-14. Not needed at this time.

### S12. Bring the Broadcast Box level with the Dial (needs a Box)

Decided by the user on 2026-11-14: update the Box before the test. Extended 2026-11-15: fleet
scan and distribute are in.

Power, not memory (user, 2026-11-15). `known_issues/2026-09-01-bbox-usb-reboots.md` dates from
the earliest prototype and its front matter still says open. The user recalls the resets were
traced to power: USB-A current split between the screen, NFC, the radio and, on the Box only,
battery charging. The Box was more stable on battery alone. That finding led to the rule that
NFC and WiFi/ESP-NOW never run at the same time, which the Dial now follows (S4). The user
expects the same rule to clear the Box. Earmark: if the Box resets silently again during S12
or the test, stop adding features and reopen that note with the reset-reason lines.

```
Task: the Broadcast Box (TeacherTools/BroadcastBox/BBoxFirmware/) is behind the Dial. Bring it
level, in the order below. Read known_issues/2026-11-02-dial-box-arm-serving.md and
known_issues/2026-09-01-bbox-usb-reboots.md, and the "Power, not memory" paragraph above S12
in the plan. State each note in one sentence and get the user's confirmation before changing
code. The radio-first rule still holds: no imports or prints ahead of the radio. Commit after
each numbered step so any one can be backed out.
1. Serve without arming. Port commit cb19272 (S4, Dial) to the Box's code_link.py,
   bbox_server.py and bbox_ui.py: radio and code server on by default, paused only during an
   NFC read or write. Keep arm and disarm as accepted no-ops. NFC and the radio must never be
   on together; this is the power rule, so show in your report where the code guarantees it.
   The Box differs from the Dial in one case the note records: with no game on flash it has no
   radio at all. Decide how that case behaves and say so.
2. List what else the Dial got that the Box lacks (git log for BDialFirmware since
   2026-10-20 is a start) and report it as a table: change, would it fit the Box, size.
3. Fleet scan, find and distribute. The slot picker and device list live in ChatBroadcast
   (js/distribute.js); the Box only relays, so it needs no new screens.
   a. Copy BDialFirmware/fleet.py to BBoxFirmware/ unchanged if you can. It is imported on the
      first fleet.* command, after the radio is up; keep that.
   b. Box code_link.py: CodeLink.poll() gains the on_msg argument the Dial's has (messages
      that are not code-transfer go to fleet).
   c. bbox_server.py: add fleet.scan, fleet.find, fleet.distribute and fleet.cancel, the
      fleet.step() call in the main loop, on_pull() after each pull result, and cancel when
      the radio pauses for NFC. Follow bdial_server.py lines 128-150, 691 and 720-765.
   d. bbox_ui.py: add show_progress(done, total), which fleet.py calls. One line of text on
      the Box screen is enough ("Sending 2/5").
   e. ChatBroadcast js/app.js about line 2932 hides the Distribute button when the device
      says it is a broadcast_box. Have the Box report that it has fleet commands (a field in
      its identity reply) and show the button when that field is present, so a Box on old
      firmware still hides it.
   f. Add a known_issues note for the Box fleet port: status "untested on hardware", and the
      earmark above.
4. Only if S5 step 4 is already bench-proven on the Dial: port its JSON-link game upload so a
   send does not restart the Box. Otherwise leave it and say so.
Check: py_compile, tools/devtests/game_menu_scan.py, node --check,
node ChatBroadcast/tools/distribute_test.mjs. Then two hands-on blocks, both run once on USB
and once on battery where the step allows it.
Block A (steps 1 and 4): flash the Box, pull a game by card onto one wand without arming,
send a second game from ChatBroadcast, pull again.
Block B (step 3): with two wands powered, scan from ChatBroadcast, find one wand, distribute a
game to both, then tap an NFC card on the Box during a second distribute.
Capture the Box's serial log in the background for both blocks and report the reset-reason
lines from reset_log.py. Update the known-issue notes.
```

### S13. Waveshare 1.9 "bigger box": early mockup (not part of the stress test firmware)

Asked for by the user on 2026-11-14. The board work started 2026-11-13 and so far is bench
probes only (`Experiments/Waveshare19_Controller/`: display, backlight, colour, touch).

```
Task: mock up a first version of the Waveshare ESP32-S3-Touch-LCD-1.9 as a larger Broadcast
Box: 170x320 portrait touch screen, LVGL (lvgl_micropython, as on the CrowPanel), no buttons.
This is an early mockup for the user to react to, not finished firmware. Work only in
Bag3/Code/Experiments/Waveshare19_Controller/. Read its board.py and display_test.py, the
Box's screens (TeacherTools/BroadcastBox/BBoxFirmware/bbox_ui.py), the CrowPanel app for LVGL
patterns and the design tokens (Experiments/CrowPanel5_Display/panel.py, home.py,
ds_tokens.py), and known_issues/2026-11-10-crowpanel-teacher-tool-ui.md for what the user
already corrected in that design.
1. Screen list first, as a short table for the user: what the Box shows today, and what the
   larger touch screen lets each screen add (game list with names, write-card flow, serving
   status, pull counts, battery). Ask the user to confirm or cut before building.
2. An HTML mockup of those screens at 170x320, one file, no build step, using the design
   tokens. Publish nothing; put it in the experiment folder and send the file to the user.
3. After the user has seen it: the same screens on the device in LVGL with made-up data, no
   radio, no NFC and no file transfer. One module per screen and a main.py that starts the
   mockup. Keep display_test.py and the other probes working.
4. List what the board lacks to be a real controller, from board.py: it has no NFC reader
   (which free pins could take one), the SD card is SDMMC 1-bit, and whether the firmware
   build has ESP-NOW. Report; do not build these.
Hardware: one short hands-on block for step 3, to flash and look at the screens. The agent
cannot see the display, so it asks the user for a photo or a description of each screen.
```

### S10. Generated-game fixes from the 2026-11-14 hands-on test (before S9)

Source: `Bag3/STRESS_TEST_FINDINGS_2026-11-14.md`, items K1-K4, U1 and U3. Planning decisions
1 and 2 are answered here.

```
Task: six small changes so a generated game is right the first time and its faults reach the
chat. Read Bag3/STRESS_TEST_FINDINGS_2026-11-14.md and the four known-issue notes it cites
(games-must-repeat, send-check-errors-ux, splat-host-wand-count, start-tag-in-tray). These are
known issues: state each in one sentence and get the user's confirmation before changing code.
1. K1, games repeat. In ChatBroadcast/knowledge/ (game_patterns.md, platform.md and
   interview.md) say that every game celebrates a win and then starts a new round, forever,
   until a stop message. Change the interview question from how the game "ends" to what a win
   looks like. Check the knowledge examples follow the rule.
2. U1, checks run early. ChatBroadcast/js/upload.js:122 runs splatGameProblems() only at Send.
   Run it when a game is generated or edited as well. Show failures through the same "fix it"
   path the Simulator failure uses (js/app.js about line 2677), with the problem sentences as
   the request to the chat. In Simple mode send that request automatically, once per generated
   game; if the second version still fails, show the problems and stop. Keep the Send-time
   check as it is.
3. K2 needs no separate change: it is one of the problems step 2 now reports.
4. K3, wand count. savedGameDevices() in js/app.js (about line 140) adds one wand for the host
   when the game has SPLAT_HOST = True, and the brief format in the knowledge says to count
   the host wand.
5. K4, start card. The Simulator's card tray leaves out the game's own start tag.
6. U3, brief in Simple mode. Show Simple-mode users a short summary of the brief (name, what
   players do, devices needed), not the full text. If this needs more than a small change,
   stop and report instead.
Check: node tools/chat_request_test.mjs, tools/hardware_pills_test.mjs and
tools/splat_game_check_test.mjs (13 cases there already fail; do not fix them), then one
browser run with Playwright: generate or paste a host game that ignores splat_lost and confirm
the fix request appears. Report each item in one line, with a screenshot for item 2.
```

### S11. Dial keyboard and distribute stall (finding D2; needs a Dial)

Planning decision 3: reproduce before the test, in one hands-on block. A teacher uses the
keyboard to write card text, so this is on the main path.

```
Task: find out why a distribute failed with the Dial's keyboard open. Read finding D2 and D3 in
Bag3/STRESS_TEST_FINDINGS_2026-11-14.md. The Dial printed "RuntimeError: schedule queue full"
from its screen timer, free memory fell from 53 KB to 27 KB when the keyboard was built
(BDialFirmware/station_ui.py builds it on first use), and neither wand's request arrived.
1. Without hardware: read station_ui.py, text_entry.py, bdial_server.py's main loop and
   fleet.py, and write down what blocks the main loop while the keyboard is built or shown,
   and what the screen timer schedules.
2. One hands-on block with a Dial and two wands, serial capture running in the background.
   Three sends, in this order: restart the Dial, open the keyboard and send at once; send
   while the user turns the dial; send two minutes later. Record free memory and any
   "schedule queue full" line for each.
3. If the first send fails and the others pass, make the smallest fix: hold a distribute until
   the keyboard build has finished, or do not schedule a screen update while one is pending.
   If memory is the cause, report the numbers and stop; do not restructure the keyboard.
4. D3: in the same capture, save the lines printed right after a soft reset and report where
   the "object isn't callable" errors come from if the log shows it. Do not chase it further.
Add a known-issue note for D2 and D3 with the capture results.
```

### S9. Promote ChatBroadcast, the Simulator and the Icon Maker to Live_Page (after S3, S5, S6, S7)

```
Task: make the hosted copy match the bench-tested Bag3 trees. Volunteers use the hosted site.
Read Live_Page/AGENTS.md first.
1. Replace Live_Page/ChatBroadcast/ and Live_Page/Simulator/ with copies of
   Bag3/Code/ChatBroadcast/ and Bag3/Code/Simulator/, and add Live_Page/IconEditor/webapp/ from
   Bag3/Code/IconEditor/webapp/ (ChatBroadcast embeds it as ../IconEditor/webapp/?embed=1 and
   iconView.js imports its preview.js; since 2026-11-15 there is no ChatBroadcast/iconmaker/).
   Delete the old Live_Page/ChatBroadcast/iconmaker/. Leave out bak/, REPLY_HANDLING.md, the
   .code-workspace file, __pycache__ and test caches. The three are siblings in both places, so
   make no path edits; if a path edit seems needed, stop and report it instead.
2. Serve Live_Page/ locally and check in a browser with Playwright: the ChatBroadcast page
   loads with no console errors, the practice window starts for one solo game and one host
   game, and the example gallery loads a game. Take screenshots.
3. Check the Flasher (Live_Page/Flasher/): confirm the wand entry reads
   Bag3/Code/Wand Module/flash_bundle/flash_manifest.json and say which branch names it offers
   (js/devices.js REFS). Report whether the test branch needs adding for H7.
4. Commit on the working branch. Do not push to September_2026 or any deploy branch: the user
   pushes the bench-tested build there. End your report with the exact commit to promote.
Report: what was copied, the browser results with screenshots, and anything in the copy that
cannot work when hosted (for example the firmware installer's paths to other Bag3 folders).
```

## Hardware phases (original schedule; superseded by "The sitting" near the top)

Each phase is one hands-on block of 15 to 30 minutes, with at most 3 devices on USB. The agent
flashes and sets up before the block. Splats connect over BLE and do not use a USB port.

| Phase | When | On USB | Needs | What the user does | Pass means |
|---|---|---|---|---|---|
| H1 Wand smoke | Day 1 morning | 2 wands, Dial | S0 | Power on, tap a built-in game card, pull one custom game, start a plain lobby with both wands | Boot log clean on both; game runs; lobby starts |
| H2 Host and Splats | Day 1 afternoon | host wand, 1 player wand | H1 | Pair 4 Splats, start a host game, take one Splat away, tap a fifth; then a solo game with 2 Splats | Memory lines recorded with 4 Splats and a pulled game; slot policy cases noted |
| H2b Palette | with H2, 10 min | host wand | H2 | Look at 12 to 18 candidate colors on a Splat and say which are clear | User's list of clear colors |
| H3 Icon display | Day 2 morning | display, wand, Dial | H1 | Play Move Mixer and share a dance; pull a display game; play Picture Moves | Display shows the dance; display game runs |
| H4 Slots and distribute | Day 2 midday | Dial, host wand, 1 player wand (others on battery) | S1, S2, S3 | Distribute a host game with the host last; send a fourth game and pick what to replace | No red X while waiting; the chosen game is replaced; scan shows slots |
| H5 Controllers | Day 2 afternoon | Dial, CrowPanel, Box | S4, S5, S11, S12 | Unplug and replug the Dial mid-send; pull by card from each controller without arming | App state follows the cable; all three serve |
| H6 Dry run | Day 3 morning | one controller, host wand, 1 wand (logs only) | all, S9 | Run one whole table as a volunteer would, from a fresh prompt to play, using the `Live_Page/` copy | A generated solo game and a generated host game both play |
| H7 Flash and freeze | Day 3 afternoon | 3 wands at a time | H6 fixes | Swap wands through three cables; then push the frozen build to the deploy branch | Every wand and display on the frozen build; hosted site serves the same build |

Notes:

- H2 decides the host Splat count for the test. If 4 Splats with a pulled game fails, the user
  chooses between 2 or 3 per host and a fix attempt.
- H7 is the most hands-on step: about 30 wands at 3 per batch. The agent should prepare one
  background command per batch so the user's part is only swapping cables. Split it into two
  blocks.
- If a phase fails in its first minutes, the agent stops, reports what the log shows and
  proposes the next block; it does not hold the user while it debugs.

## Not in this plan (after the test)

The 13 stale checker cases, a single drift-check command, a shared game-mode record on the
controller, a `set_role` sender on the Dial, Simulator
host-screen polish, and the v1.29 host cause.

## Verification

- Off-device: `py_compile` on every changed `.py`, `node --check` on changed js,
  `sync_sources.py --check` passing after S6, the slot-list test from S2, Playwright screenshots
  from S6.
- On hardware: phases H1 to H6, each reported as "the log shows" plus what the user saw.
- End to end: H6, one table from a fresh ChatBroadcast prompt to a played solo game and a played
  host game, with serial logs kept.
