# Bag3 stress-test prep plan (written 2026-11-14, test in about 3 business days)

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
   which trees you changed. Do not touch Bag2 or the Simulator.
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
Leave the Box alone (it has no fleet commands). Check: py_compile, node --check,
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

### S8. Test-day kit (no code)

```
Task: write three short documents in Bag3/Code/docs_and_design/, dated today.
1. A one-page volunteer sheet: how to start a Splat host game (host first, then players), what
   each failure light means (take these from Wand Module/main.py and lib/lobby_game.py), how to
   stop, and what to write down when something breaks. One version each for Dial or CrowPanel
   tables and for Box tables (cards only, no distribute).
2. Tester questions: three slots or one on wands and displays; fill empty or pick what to
   overwrite; whether the paper remote should stay a fixed launcher or sync games from the
   controller; what they could not tell about Splat and host status.
3. A logging checklist for the user: one serial capture per controller and one host wand per
   table using tools/serial_monitor.py, where the files go, and a reminder that every prompt
   and generated game should be saved, including failures.
Plain language, no jargon the volunteers have not been taught. Ask the user to review.
```

### S9. Promote ChatBroadcast and the Simulator to Live_Page (after S3, S5, S6, S7)

```
Task: make the hosted copy match the bench-tested Bag3 trees. Volunteers use the hosted site.
Read Live_Page/AGENTS.md first.
1. Replace Live_Page/ChatBroadcast/ and Live_Page/Simulator/ with copies of
   Bag3/Code/ChatBroadcast/ and Bag3/Code/Simulator/. Leave out bak/, REPLY_HANDLING.md, the
   .code-workspace file, __pycache__ and test caches. The two are siblings in both places, so
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

## Hardware phases

Each phase is one hands-on block of 15 to 30 minutes, with at most 3 devices on USB. The agent
flashes and sets up before the block. Splats connect over BLE and do not use a USB port.

| Phase | When | On USB | Needs | What the user does | Pass means |
|---|---|---|---|---|---|
| H1 Wand smoke | Day 1 morning | 2 wands, Dial | S0 | Power on, tap a built-in game card, pull one custom game, start a plain lobby with both wands | Boot log clean on both; game runs; lobby starts |
| H2 Host and Splats | Day 1 afternoon | host wand, 1 player wand | H1 | Pair 4 Splats, start a host game, take one Splat away, tap a fifth; then a solo game with 2 Splats | Memory lines recorded with 4 Splats and a pulled game; slot policy cases noted |
| H2b Palette | with H2, 10 min | host wand | H2 | Look at 12 to 18 candidate colors on a Splat and say which are clear | User's list of clear colors |
| H3 Icon display | Day 2 morning | display, wand, Dial | H1 | Play Move Mixer and share a dance; pull a display game; play Picture Moves | Display shows the dance; display game runs |
| H4 Slots and distribute | Day 2 midday | Dial, host wand, 1 player wand (others on battery) | S1, S2, S3 | Distribute a host game with the host last; send a fourth game and pick what to replace | No red X while waiting; the chosen game is replaced; scan shows slots |
| H5 Controllers | Day 2 afternoon | Dial, CrowPanel, Box | S4, S5 | Unplug and replug the Dial mid-send; pull by card from each controller without arming | App state follows the cable; all three serve |
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
controller, a `set_role` sender on the Dial, bringing the Box level with the Dial, Simulator
host-screen polish, and the v1.29 host cause.

## Verification

- Off-device: `py_compile` on every changed `.py`, `node --check` on changed js,
  `sync_sources.py --check` passing after S6, the slot-list test from S2, Playwright screenshots
  from S6.
- On hardware: phases H1 to H6, each reported as "the log shows" plus what the user saw.
- End to end: H6, one table from a fresh ChatBroadcast prompt to a played solo game and a played
  host game, with serial logs kept.
