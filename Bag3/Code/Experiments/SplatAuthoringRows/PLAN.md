# Implement "game authoring by row" (Plan A) — Bag3 wand, Splat host, ChatBroadcast

## Context

Design: `Bag3/Code/docs_and_design/2026-11-13-game-authoring-rows.md` (commit `facdb4f0`).
Goal: the chat agent builds Splat games accurately and repeatably, and each game loads only what
its row needs. Defaults: a solo wand game; with 1–2 Splats, a solo wand driving its own Splats
directly (no lobby). Group Splat games go through a Splat host wand. Pooled Splats are removed.

Decisions taken (2026-11-13):
- **Delete the pooled paired-wand lobby path** and its three non-host games.
- **Station mode targeting = same as icon displays:** every Splat host in range acts on every
  command. Icon display games never filter by sender or target.
- **No color mapping needed:** a wand's identity name is already a Splat color name
  (`splatpair.PALETTE = ("turnred", …)`), so `net.wands[p][1]` passes straight to `splat.color()`.
  Document this; drop P7.
- **Splat turn-off at game end is owned by the wand:** `main._launch_game` → `_pair_ctl.after_game()`
  already turns off and re-glows. Games stop doing it.
- **Scope: everything, including station mode.**

**Location (user rule): unproven code lives in a dedicated experiment.** Nothing under
`Bag3/Code/Wand Module/`, `ChatBroadcast/`, `Simulator/` or `Live_Page/` changes.
All work goes in **`Bag3/Code/Experiments/SplatAuthoringRows/`** (no spaces):

```
SplatAuthoringRows/
  README.md            # purpose, status, what differs from Wand Module, promotion checklist
  wand/                # copy of Wand Module at 3cb1c884 (main.py, lib/, games/), then edited
  knowledge/           # draft game_types.md, splat_host_games.md, wand.md, platform.md, game_patterns.md diffs
  js/                  # draft splatGameCheck.js + splatActionCheck.js and their test
  tests/               # pytest using Simulator/py shims read-only via sys.path
  deploy.py            # copy wand/ to a bench wand (as SplatHostBench/install_com8.py)
```

Below, paths like `lib/splatpair.py` mean `SplatAuthoringRows/wand/lib/splatpair.py`. The four
game-tag consumers and the Simulator are **not** edited; Phase 2 lists the tag removals for promotion
only. Promotion into the live trees is a separate, later step after hardware proof. Bag2 is not touched.
Device code follows AGENTS.md: no new import ahead of radio bring-up; `py_compile` is the only
off-device check.

## Execution budget (low tokens)

- **Order by value; stop after any phase.** Phase 1 (type 2) + its draft `wand.md` section is the minimum useful slice. Then 3, 5, 4, 2, 6. Phase 7's README is written incrementally per phase.
- **Copy with `cp -r`, edit with targeted `Edit`s.** Don't read whole files; use `grep -n` and read ±30 lines around the change. Never read `lobby_game.py` (852 lines) in full: Phase 2 deletes by grep'd symbol names.
- **Delegate phases to fresh subagents with narrow briefs.** This conversation's context is already
  large, and each turn here re-pays for it. A subagent that starts with only the plan's phase section
  and the files below costs less. The main session only sequences phases and reviews diffs
  (`git diff --stat`, then spot-reads).

| Phase | Context the agent needs | Subagent? | Model |
|---|---|---|---|
| 0. Setup | `cp -r` Wand Module@3cb1c884 into `wand/`; README skeleton | yes (trivial) | haiku |
| 1. Type 2 API | `lib/splatpair.py` (`SplatPairing.poll`, `after_game`), `lib/splat_api.py` `SplatGroup` (L205–260), `main.py` `_splat_limits` / `_run_games` / `_start_play` (L446–620); AGENTS radio-first rule | yes | sonnet |
| 2. Delete pooled path | `lib/lobby_game.py` symbol list (`_PoolSplat`, `local`, `owner`, `_first`, `_service_local`, `_run_cmd`, `pw_cmd`, `pw_evt`); delete the 3 games; record the tag removals in the README | yes; needs care with the 852-line file | opus |
| 3. Host template + ports | design doc A5; `lobby_games.md` `net`/event tables; `wand.md` canonical template; one existing `host_splattag.py` | yes | sonnet |
| 4. Station mode | `lib/splat_host.py` `_loop` (L230–282); `splat_api` action names | yes | sonnet |
| 5a. Knowledge drafts | design doc (axes, types, A6); `wand.md` template; the outputs of phases 1 and 3 | yes, writing only | sonnet |
| 5b. JS check | `splatGameCheck.js`, `splat_game_check_test.mjs`; design doc A7 | yes | haiku |
| 6. Tests | `Simulator/py/shims` listing, `Simulator/tests/conftest.py`; the experiment `wand/lib` | yes; stop and report if the shims need Simulator edits | sonnet |
| 7. README / promote list | each phase's commit message | main session | — |

- **Brief format per agent:** the phase section of this plan, the file and line list above, the rule
  "only edit under `Experiments/SplatAuthoringRows/`", "commit, don't push", and "report: files
  changed + py_compile/test result, under 150 words".
- **Parallel:** run 4, 5b and 0 independently, and 1 ∥ 2 after 0. 3 waits on 2 (the `net` surface), 5a
  waits on 1 and 3, and 6 comes last.
- **The main agent does no file reading** beyond `git diff --stat` and failures the agents report.
- **Knowledge drafts as patches.** Write new sections only (`game_types.md`, the type 2 block, `splat_host_games.md`); don't copy the unchanged knowledge files into the experiment.
- **Ported host games: write fresh from the template**, not edit-in-place. Write one game and copy its shape for the other two.
- **Tests: one file, smallest cases.** Skip the prompt eval (step 4) and the Simulator-shim test if the shims need any wiring; `py_compile` + the JS check test are the floor.
- **One commit per phase, short messages; push at the end.**
- **New session per phase if context runs long:** the plan file and the README carry the state, so a fresh session can resume from "next phase".

## Status (2026-11-13)

Phases 0–3 are done in the experiment (commit `551887d1`, `py_compile` only). **Remaining: 4 and 5.**
Both write under `Experiments/SplatAuthoringRows/` only. Run them as two parallel subagents
(Phase 4 sonnet; Phase 5a knowledge drafts sonnet; Phase 5b JS check haiku), each briefed with its
phase section, the file list in the table above, and the rule "edit only under the experiment; commit,
don't push; report under 150 words". Notes from phases 1–3 for those briefs:
- **Host games** (`wand/games/host_*.py`) are the reference for the type 9 template and its example.
  Identity names are Splat color names; `WAND_COLOR` dict maps them to `leds` colors.
- **Type 2 contract:** `SPLATS_LOCAL = 1..2`, `play(..., batt=None, splats=None)`, `splats.count / unit(i) / poll()`.
- **Pooled path is gone**: no `net.local`, `net.owner`, `wand_splats`, or `SPLATS_MIN` without `SPLAT_HOST`.
  `SPLATS_MIN` alone is now only a plain type 7 lobby (no Splats), so the JS check must treat
  `SPLATS_MIN` without `SPLAT_HOST` as an error or a Splat-free lobby.
- **Phase 4 touchpoint:** `wand/lib/splat_host.py` `_loop`, in the `mt == "raw"` branch; reuse
  `splat_api.COLOR_RGB / NOTE_VALUES / ANIMAL_SOUNDS` and `ctl.group.unit(i)`.
- **Output paths:** `knowledge/game_types.md`, `knowledge/wand_type2.md` (the type 2 block for `wand.md`),
  `knowledge/splat_host_games.md`, `knowledge/platform_patch.md`, `knowledge/game_patterns_patch.md`,
  `js/splatGameCheck.js`, `js/splatActionCheck.js`, `js/splat_game_check_test.mjs`.

## Phase 1 — Type 2: local Splat API (no lobby)

- **`Wand Module/lib/splatpair.py`**: add a small `GameSplats` handle (inside this already-loaded
  module; no new import before the radio). It wraps `SplatPairing`:
  - `count`: the number of paired Splats.
  - `unit(i)` → `self.group.unit(i)`, the existing `splat_api.SplatAPI`, with `color / note / sound / play / off`.
  - `poll()` → takes one event from `SplatPairing.poll()` (which also services links and lost
    tracking), returns `("press", i)` / `("release", i)` or `None`, buffering the rest.
  - `SplatPairing.game_handle()` returns it.
- **`Wand Module/main.py`**:
  - Extend `_splat_limits()` to read `SPLATS_LOCAL` (int 1–2). It returns a distinct "local"
    result and raises `ValueError` if `SPLATS_LOCAL` is combined with `SPLATS_MIN` or `SPLAT_HOST`.
  - In `_run_games`, a local game skips `_enter_lobby`. It passes `_pair_ctl.game_handle()`, or `None`
    when the wand has no Splats, as the 8th argument through the existing `_start_play` (arity
    handling unchanged). `lobby_game` is not imported on this path.
  - Refuse `SPLATS_LOCAL` on a wand in the `splat_host` role, like the existing non-host-game refusal.
- **Game contract:** `def play(nfc, leds, buz, accel, i2c, enow, batt=None, splats=None)`. This is
  the ordinary wand loop (`enow.poll()` every loop, return on stop/start_game) plus `ev = splats.poll()`.

## Phase 2 — Delete the pooled lobby path

- **`Wand Module/lib/lobby_game.py`**:
  - Remove `_PoolSplat`, `net.local` / `local_count` / `owner`, pool indexing (`_first`),
    `_service_local` forwarding, `pw_cmd`/`pw_evt` handling, `_run_cmd`, and `_track_local_ready` for followers.
  - Keep the host group path and the plain wand lobby (type 7, no Splats).
  - `net.splat(i)` remains host-only, over the host's own `_pair_ctl.group`.
- **Remove** `games/splattag.py`, `relaycolor.py` and `lobbytest.py`, and their tag entries in the four
  game-tag consumers: `Wand Module/lib/game_tags.py`, `Live_Page/WebApp2/hubCode2/game_tags.py`,
  `Live_Page/WebApp2/js/utils/commands.json` and `Live_Page/wand_icons.html`. Also remove the matching
  `Stations/IconDisplay/games/relaycolor.py` reference only if it exists solely for the wand game.
  Flag it rather than delete it if it has other uses.
- **`Wand Module/lib/pairing.py`**: keep `MAX_SPLATS = 2` for a player wand and `HOST_MAX_SPLATS = 4`.

## Phase 3 — Type 9 template and host game ports

- **Rewrite** `games/host_splattag.py`, `host_relaycolor.py` and `host_lobbytest.py` to the template
  shape (design doc A5):
  - Declarations plus `GAME_ICON`, and a `net is None` guard.
  - Loop: `net.poll()` first; return on end/leader_lost; cards every `NFC_EVERY`; sleep.
  - Three hook regions: host event, host timer, player message.
  - `live_splats()` / `live_players()` helpers.
  - Only documented APIs: `leds.fill` and `leds` colors; `Pin(0, …)` for the button.
    No `leds.np`, `WAND_RGB`, `splatpair` or `HUB_CONFIG`; `NfcReader` instead of `read_tag_command`.
  - No Splat turn-off in `finally`; no diagnostic prints.
  - The relay color game drops its `relay_pass` icon broadcast unless it is kept as a Pattern C example.
- **Wand-light color for a player:** the template carries a 6-entry dict from Splat color name to
  `leds` color (`"turnred": RED`, …), matching the six-color table already in the knowledge.

## Phase 4 — Splat host station mode (G1–G3)

- **`Wand Module/lib/splat_host.py` `_loop`**:
  - A `raw` dict with `type == "splat"` → `{"s": i or absent, "a": [names]}`. Validate the names
    against `splat_api` `COLOR_RGB / NOTE_VALUES / ANIMAL_SOUNDS`, and print `[ERR]` for an unknown
    name, not silently ignored. Apply the actions to unit `s`, or to every unit when `s` is absent.
  - Every host in range obeys.
  - Idle presses still glow via `ctl.on_press`. Each press is also broadcast as
    `{"type": "splat_press", "s": i, "c": <host identity name>}`.
- **`platform.md` reserved types:** add `splat` and `splat_press`. Check the Live_Page / ChatBroadcast
  tag and type lists for a collision with an existing game slug `splat`.

## Phase 5 — Knowledge, prompt and send-time check (ChatBroadcast)

- **New `knowledge/game_types.md`**: the two axes, the teams modifier, the type table, and "state the
  row first". Add it to `SHARED_KNOWLEDGE` in `js/prompt/buildRequest.js`.
- **`knowledge/devices/wand.md`**: add the type 2 template and the `splats` API next to the canonical
  template. Replace the "Splats" section.
- **Replace `knowledge/lobby_games.md` with `knowledge/splat_host_games.md`** (type 9 template, one
  example, trimmed `net` / event tables) plus a short type 7 appendix. Update `buildRequest.js` paths.
- **`knowledge/game_patterns.md`**: label patterns by row; add the station mode example (teacher wand
  broadcasts `{"type": "splat", "a": ["turnred"]}`).
- **`knowledge/platform.md`**: in `[GAME_SETTINGS:]`, replace `wand_splats` with `splats` (1–2) for
  type 2; keep `splat_host`; add the reserved types.
- **`js/splat/splatGameCheck.js`**: rules per design doc A7.
  - `SPLATS_LOCAL` needs `splats`, 1–2, and no `SPLATS_MIN` or `SPLAT_HOST`.
  - A host game needs `net`, an `"end"` return, `net.splat(` only with `is_host` present, and no `enow.poll(`.
  - Neither declaration: 7 params.
  - Drop the old `MAX_SPLATS` pooled wording.
- **`js/splat/splatActionCheck.js`**: accept `splats.unit(i)` handles as well as `net.splat(i)`.
- **`js/app.js` / `js/chat.js`**: read `splats` in place of `wand_splats` from `GAME_SETTINGS` for
  the practice window.
- **Update `tools/splat_game_check_test.mjs` and `tools/devtests/test_splat_host.py`.** Add
  `tools/eval_fixtures` cases for a cooking game (type 2), freeze dance (type 4) and a host tag game (type 9).

Phase 5 edits are drafts under `SplatAuthoringRows/knowledge/` and `SplatAuthoringRows/js/`; the
live ChatBroadcast prompt is unchanged, so it keeps generating games the fielded firmware runs.

## Phase 6 — Experiment tests (Simulator untouched)

- **`SplatAuthoringRows/tests/`**: pytest that puts `Simulator/py/shims` (fake `splat_hub`, ESP-NOW)
  on `sys.path` read-only, ahead of `SplatAuthoringRows/wand/lib`.
- **Cases:** a local Splat game via `game_handle()`; a host group game; station mode; the type 7 lobby
  without Splats.
- **If the shims can't load the experiment without Simulator edits**, record what is missing in the
  README as a promotion item rather than editing Simulator.

## Phase 7 — Docs, promotion checklist, known issues

- **`SplatAuthoringRows/README.md`**: list each change against `Wand Module@3cb1c884`. Also the
  promotion checklist: copy back to Wand Module, the four tag consumers, Simulator sync, ChatBroadcast
  knowledge/js, and the stale `known_issues/2026-11-11-simple-mode-large-changes.md` row.
- **Link the experiment** from the design doc (`docs_and_design/2026-11-13-game-authoring-rows.md`
  status line). That is the only edit outside the experiment.

## Verification

1. **Run** `python -m py_compile` on every file under `SplatAuthoringRows/wand/`.
2. **Run** `pytest Bag3/Code/Experiments/SplatAuthoringRows/tests`.
3. **Run** `node SplatAuthoringRows/js/splat_game_check_test.mjs` against the draft checker.
4. **Prompt eval (optional):** run `ChatBroadcast/tools/prompt_eval.mjs` with the draft knowledge
   files passed in, if it accepts a knowledge path; otherwise note it as a promotion step.
5. **Confirm** `git diff --stat` shows changes only under `Experiments/SplatAuthoringRows/` and the one
   design-doc line.
6. **Hardware (via `SplatAuthoringRows/deploy.py`, with the user, following `bag3-hardware-protocol`; wands on MicroPython v1.28.0):**
   - A type 2 cooking game on one wand with 2 Splats.
   - A type 9 host tag game with 4 Splats and 2 players.
   - Station mode: a teacher wand broadcasts a color and two hosts both obey.
   - Check that `idf largest` after imports is no lower than the `9d1a8b8d` bench figure (163840).
7. **Commit** in phases on `ccr-38821932-f2qplq` and push. No PR unless asked.

## Status update (2026-11-13, later)

Phases 0-5 and 6 (lightweight) are done in the experiment; see `README.md` for tests and gaps.
Remaining: prompt eval (needs an API key and a knowledge-path option in `prompt_eval.mjs`), replace the two
refused lobby examples, trim `splat_host_games.md`, draft the `app.js`/`chat.js`/`buildRequest.js`
wiring, link the experiment from the design doc, hardware check on MicroPython v1.28.0.

## Status update (2026-11-13, later)

- `knowledge/platform_patch.md` and `knowledge/game_patterns_patch.md` exist; the `wand_splats` to
  `splats` settings change is in `platform_patch.md`, not `station_mode.md`.
- `deploy.py` exists: it stages the manifest files and prints `mpremote` commands; it opens no port.
- **Option A chosen:** a type 2 game is refused at load unless at least `SPLATS_LOCAL` Splats are
  connected, so `splats` is never `None` in `play()`.
- `splat_press` is limited to one per Splat per 250 ms; a host running a type 9 game ignores `splat`
  messages.
- Tests: `tests/test_wiring.py` covers `_run_games` and the host loop. Current status: `README.md`.
