# Bag3 advisor review: stability, shared contracts and stress-test risks (2026-11-14)

Reviewed on `ccr-eec157d8-pkam3d` (everything on `wand-splat-update` plus W6). The plan that
follows from this review is `Bag3/STRESS_TEST_PREP_PLAN.md`.

Paths are relative to `Bag3/Code/` and use the layout after the 2026-11-14 move
(`ChatBroadcast/`, `tools/`, `docs_and_design/`; `BroadcastCode/` is gone).

**Verified** means the code was read or a read-only check was run. **Inferred** means reasoned
from the code. Nothing here was run on hardware. Issues already in `known_issues/` are cited,
not re-tested.

## 1. Risks to classroom stability, ranked

1. **Distributing a Splat host game leaves early wands on a red X.**
   - Verified: the Dial pushes one device every 2.5 s (`TeacherTools/BroadcastDial/BDialFirmware/fleet.py:28,141`).
     Each wand launches as soon as its pull ends (`Wand Module/main.py:881`). A player wand looks
     for a host lobby for about 10 s, then gives up (`Wand Module/lib/lobby_game.py:41`, `main.py:590`).
   - Verified: status reports carry `kind=HUB_TYPE` only (`main.py:1079`), and nothing in
     `TeacherTools/` sends `set_role` or reads a game-mode declaration.
   - Inferred: within one table, a wand that finishes pulling before the host's lobby is up fails.
2. **The Splat host is a single point of failure with unmeasured memory in play.**
   - Recorded: a 4-Splat host boot and a 10 KB `compile()` with 4 connected were never run
     (`docs_and_design/2026-11-13-splat-host-status-overview.md`;
     `known_issues/2026-11-12-splat-host-v129-firmware.md`, `2026-09-30-known-issues.md`).
   - Verified: `Wand Module/lib/pairing.py:30` says more than 2 Splats per wand is untested.
3. **The practice window runs the old game-mode rules.**
   - Verified: `Simulator/py/runtime.py:706-718` accepts `SPLATS_MIN` alone, defaults
     `PLAYERS_MIN` to 1 and never reads `SPLATS_LOCAL`. `Simulator/sim-room.js:129` reads
     `wand_splats`; ChatBroadcast sends `splats` (`ChatBroadcast/js/app.js:150`).
   - Verified: `Simulator/tools/sync_sources.py --check` fails (drift in `lobby_game`, `pairing`,
     `splat_api`, `splat_host`, `splatpair`); `ChatBroadcast/tools/splat_game_check_test.mjs`
     reports 13 failures.
   - Note: the ChatBroadcast templates, knowledge and send-time checker are current. Only the
     Simulator is behind.
4. **The radio has one flat namespace.**
   - Verified: a lobby is found by slug alone (`lobby_game.py:183`); game messages are bare
     broadcasts (`Wand Module/games/colorsays.py:107`, `movemixer.py:140`); system types such as
     `score`, `song` and `splat_config` are claimed before a game sees them
     (`Wand Module/lib/espnow_manager.py:428-475`). No send-time check reserves them.
   - Inferred: a generated game that names its message `score` never receives it. Full-class
     load is unverified (`known_issues/2026-11-13-game-system-gaps.md`, R2).
   - User, 2026-11-14: cross-class interference is not a concern for the stress test.
5. **Refusals look alike, and old-rule games no longer load.**
   - Verified: a host wand given a non-host game only buzzes (`main.py:630-634`).
     `SPLATS_MIN` without `SPLAT_HOST` is a load failure (`main.py:454-455`).

## 2. Where the parts should share a contract or check

- **Game-mode declaration.** Four implementations, none in the controller: `Wand Module/main.py:439-481`,
  `ChatBroadcast/js/splat/splatGameCheck.js`, `Simulator/py/runtime.py:706`, and regexes in
  `ChatBroadcast/js/app.js:147` and `js/hardware.js:104`. A mode record written beside
  `.tags.json` at send time would serve the controller; the Simulator should vendor the wand's
  functions.
- **Addressing.** `find_device`, `code_push` and `set_role` use `"mac"` (`espnow_manager.py:450-461`);
  display station mode uses `"to": "<mac>"` (`Stations/IconDisplay/lib/display_station.py:100`);
  the knowledge teaches games `"to": "players"` as a role (`ChatBroadcast/knowledge/game_patterns.md:35,66`).
- **Reserved message types.** One list in `espnow_manager.py`, generated into the knowledge and
  a send-time check, as `sync_splat_actions.py` does for Splat actions.
- **Role visibility.** Add the role to `status_report`; give the Dial a `set_role` sender (the
  wand already handles it, `main.py:710`).
- **Host limit.** The 4 is written in `pairing.py:30`, `splatGameCheck.js:20` and as a literal in
  `main.py:458`.
- **Move names.** `Wand Module/games/movemixer.py:19-23` and `display_station.py:42-47` must match.
- **Stale documentation.** AGENTS.md names `SplatCompanion/Companion/splat_api.py` as the source
  of truth; the sync tool reads `Wand Module/lib/splat_api.py` (`ChatBroadcast/tools/sync_splat_actions.py`).
  `SplatCompanion` is still in `Stations/` (W2 not done). The comment at `main.py:285` describes
  the old rule.
- **Drift checks.** `sync_icons --check` and `sync_splat_actions --check` pass; `check_tags.mjs`
  has one failure; the Simulator check fails. One script that runs all four would help.

## 3. Simplifications for teachers

| Change | Who pays |
|---|---|
| Player wands wait for a host until a stop card | Firmware (`lobby_game.py`) |
| The Dial sends a host game to the host first and shows what the game needs | Controller firmware and ChatBroadcast |
| "Make this wand the host" from the Dial's device list | Controller firmware |
| Distinct refusal cues for no host, too few Splats, wrong role | Firmware |
| ChatBroadcast rewrites an old `SPLATS_MIN`-only game on load | ChatBroadcast |
| The practice window agrees with the wand (W3b items 1-4) | Simulator |

## 4. The lead agent's ten questions

Claims checked: the flash bundle lacks `signals.py` and the W6 games (confirmed); W6 is seven
games, not six; a game can in principle learn a display's MAC from `status_report`
(`Stations/IconDisplay/main.py:483`, inferred, undocumented).

1. **One message contract?** Yes, starting with a reserved-type list and one address key.
2. **One drift check?** Yes, one command, not a hook; add the flash bundle to it.
3. **Who picks the mode?** ChatBroadcast: the rule is mechanical (user decision 2).
4. **Station addressing.** User decision. Recommended: everyone obeys by default; `"to": mac`
   is for the controller, which knows MACs from its scan.
5. **Firmware lock-in.** v1.28 for hosts stands (decision 6). Recommended: refuse the host role
   on v1.29 instead of running with 2 Splats.
6. **Memory budget.** Yes, as a size ceiling for host games in the send-time check, once the
   bench produces numbers.
7. **Teacher visibility.** User decision on where. Recommended: the Dial, via role and Splat
   counts in `status_report`.
8. **Controller fit.** Neither controller knows modes or roles. Needs the mode record, host-first
   push and a `set_role` sender. The Box has no fleet commands.
9. **Simulator first?** Yes for W3b items 1-4.
10. **Radio limits.** Hold class-wide broadcast games for R2, host music for R3, outdoor play
    for R1. Solo games and small host games can go ahead.

## 5. Additional risks for the multi-teacher stress test

- **Untested firmware.** W1-W6 has had syntax checks only; the host role, slot policy, new
  `boot.py` and display station mode are the unproven parts.
- **Controllers differ.** The CrowPanel has open notes (`known_issues/2026-10-28-crowpanel5-display.md`,
  `2026-11-10-crowpanel-teacher-tool-ui.md`). The Dial and Box still gate serving behind
  arm/disarm (`2026-11-02-dial-box-arm-serving.md`). The Box is behind the Dial.
- **Dial reconnect state (user report).** After an unplug and replug, the app shows disconnected
  while the port is open. Suspect: the auto-reconnect path in `ChatBroadcast/js/app.js`
  (about lines 1080-1134). Not traced.
- **Game pile-up.** Pulled games accumulate in `/games` on wands and displays
  (`Wand Module/lib/game_store.py`); the plan caps them at three.
- **Requests likely to fail without a clear message:** words on the display (digits and `- : .`
  only), sound from the display, more than 4 Splats, which child stomped, a wand game driving a
  host's Splats, per-role code.
- **Palette.** The note that six colors "were read as distinct" was an agent's claim. The user
  has not confirmed it and expects 12 to 18 colors to be clear.
