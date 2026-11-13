# SplatAuthoringRows

Experiment for `../../BroadcastCode/docs_and_design/2026-11-13-game-authoring-rows.md`: one
authoring shape per game row, a local Splat API for solo wands, host games on one template, and
Splat host station mode. Plan and phase status: `PLAN.md`.

**Status (2026-11-13): drafted and unit-tested off-device. Nothing has run on hardware, and no prompt
eval has been run.** `Wand Module/`, ChatBroadcast, Simulator and `Live_Page/` are unchanged.

`wand/` is a copy of `Wand Module/` at `3cb1c884` (without `flash_bundle/`). Only the files in the
next table differ from it; everything else is an unchanged copy.

## Changed files (against `Wand Module/`)

| File | Change |
|---|---|
| `wand/main.py` | `_splats_local`: `SPLATS_LOCAL` 1..2, a mix with `SPLATS_MIN`/`SPLAT_HOST` is a load failure. `_run_games`: a local game skips the lobby, gets `_pair_ctl.game_handle()` as its 8th argument and is refused at load (load-failure feedback) unless at least `SPLATS_LOCAL` Splats are connected; the handle is closed after the game. Pooled games removed from `GAME_MODULES` and the start-signature table. |
| `wand/lib/splatpair.py` | `GameSplats` (`count`, `unit(i)`, `poll()`, `close()`) and `SplatPairing.game_handle()`. |
| `wand/lib/lobby_game.py` | Pooled path removed (`_PoolSplat`, `net.owner`, `pw_cmd`, `pw_evt`, follower Splat forwarding). `net.splat(i)` is leader-only. |
| `wand/lib/splat_host.py` | Station mode (`_station_cmd`, `splat` messages), `splat_press` broadcast limited to one per Splat per `PRESS_GAP_MS` (250). |
| `wand/lib/game_tags.py` | The three pooled tags removed. |
| `wand/games/host_splattag.py`, `host_relaycolor.py`, `host_lobbytest.py` | Rewritten to the type 9 template. |
| `wand/games/splattag.py`, `relaycolor.py`, `lobbytest.py` | Deleted. |
| `wand/README.md`, `wand/manifest.js` | Describe the unpooled lobby; deleted games dropped from the notes. |

Experiment-only files: `PLAN.md`, `deploy.py` (stages files and prints `mpremote` commands; touches no
port), `knowledge/` (drafts for ChatBroadcast), `js/` (draft send-time check), `tests/`.

## Contracts

- **Type 2** (solo wand, 1-2 Splats): `SPLATS_LOCAL = 1..2`; `play(..., batt=None, splats=None)`;
  `splats.count`, `splats.unit(i)`, `splats.poll()`. No lobby. The wand refuses the game at load unless
  at least `SPLATS_LOCAL` Splats are connected, so `splats` is never `None` inside `play()`.
- **Type 9** (Splat host group): `SPLAT_HOST = True`, `SPLATS_MIN`, `SPLATS_MAX` (<= 4), `PLAYERS_MIN`,
  `GAME_ICON`; `play(..., net=None)`; `net.poll()` first, never `enow.poll()`; return on `("end",)` and
  `("leader_lost",)`. The wand turns Splats off after any game.
- **Station mode** (idle Splat host): `{"type": "splat", "s": i, "a": [names]}` from any wand (`s`
  omitted = every Splat); every host in range obeys. The host broadcasts
  `{"type": "splat_press", "s": i, "c": <host identity name>}` on a press; `c` says which host, it does
  not target. A host running a type 9 game ignores `splat` messages.

## Tests

- `python3 -m unittest discover -s tests` (17 tests): `GameSplats`; `_station_cmd`; `_run_games` wiring
  (local game skips the lobby and closes its handle, refusal with too few or no Splats, a host refuses a
  non-host game), extracted from `main.py` with `ast` because `main.py` boots hardware at import; the host
  loop routes `splat` messages to `_station_cmd` and rate-limits `splat_press`.
- `node js/splat_game_check_test.mjs`: the send-time check, including the shipped host games.
- `py_compile` on `wand/`.
- Not covered: the real host idle loop on a radio, BLE, the lobby, and any hardware behavior. The
  Simulator shims were not used.
- Prompt eval: not run. `ChatBroadcast/tools/prompt_eval.mjs` needs `ANTHROPIC_API_KEY` and reads the
  live knowledge files, so it needs a knowledge-path option to test the drafts.

## Not done

- Hardware proof on MicroPython v1.28.0 (type 2 with 2 Splats; host tag game with 4 Splats; station mode
  with two hosts). The v1.29.0 firmware issue is open (`known_issues/2026-11-12-splat-host-v129-firmware.md`).
- Prompt eval (above).
- Draft wiring: `js/wiring/wiring.patch` (apply with `patch -p1` from `ChatBroadcast/`) changes
  `app.js`, `chat.js`, `buildRequest.js` and `tools/chat_request_test.mjs`: `wand_splats` becomes `splats`,
  `SHARED_KNOWLEDGE` gains `game_types.md` and swaps `lobby_games.md` for `splat_host_games.md`. Checked on a
  scratch copy with the draft knowledge files: `chat_request_test.mjs` passes (20 checks).
- Readers: `js/wiring/readers.patch` (applies after `wiring.patch`; `patch -p1` from `ChatBroadcast/`) covers
  `hardware.js` `isLobbyGame`, `prompt_eval.mjs` and `splat_game_check_test.mjs`. `js/wiring/devtests.patch`
  (root `BroadcastCode/tools/devtests/`) ports `lobbysim.py`, `test_lobby_game.py`, `test_lobby_games.py` and
  `test_splat_host.py`; in a scratch copy 57, 15 and 39 checks pass. Not re-applied to a fresh copy; generic
  lobby cases there still gate on non-host `SPLATS_MIN` with Splat counts, which `main.py` now refuses.
  `prompt_eval.mjs --self-test-sim` is not run (Simulator unsynced).
- Send check: a type 9 game must name `splat_lost` and `wand_lost` outside comments. It is the only
  automatic test of generated games until an eval and hardware run exist.
- `knowledge/splat_host_games.md` is 120 lines. Its Splat Tag example is reduced (no score digits) and differs
  from `wand/games/host_splattag.py`, which the devtests script.
- `wand/games/colorpads.py` is the type 2 example as a bench game (`deploy.py --colorpads`);
  `BENCH_CHECKLIST.md` lists the hardware tests and what to report.
- `roles.js` signature check is unchanged (`net` optional, `splats` passes) while the prompt `roleSummary`
  still shows `net=None`.
- `Stations/IconDisplay/games/relaycolor.py` is orphaned (it listens for `relay_pass`).
- Deleting `lobby_games.md` at promotion replaces its refused examples (Splat Race, Pass the Glow) with
  Color Pads (`wand_type2.md`, type 2) and Splat Tag (`splat_host_games.md`, type 9).
- A player wand in a host game still reports its paired-Splat count at join; the lobby accepts it and
  no game path uses it.
- A game slug `splat` could collide with the new `splat` message type; reserve both names in `platform.md`.

## Promotion checklist

1. Hardware proof (above).
2. Copy the changed `wand/` files into `Wand Module/`.
3. Remove the pooled tags (`splattag`, `relaycolor`, `lobbytest`) from the other game-tag consumers:
   `Live_Page/WebApp2/hubCode2/game_tags.py`, `Live_Page/WebApp2/js/utils/commands.json`,
   `Live_Page/wand_icons.html`; also `BroadcastCode/tools/sync_game_tags.py`, `tools/devtests/test_lobby_games.py`,
   `boot_wand_lobby_game.py`, `test_splat_host.py`, and `ChatBroadcast` `gameName.js`, `prompt_eval.mjs`,
   `tools/splat_game_check_test.mjs`, which still name them.
4. `Stations/IconDisplay/games/relaycolor.py` (the Relay Timer display) listens for `relay_pass`, which
   only the deleted wand `relaycolor.py` broadcast; `host_relaycolor.py` does not. Nothing else in
   `Stations/IconDisplay` references it. Decide whether to delete it or restore the broadcast. Not
   edited here.
5. Re-run `Simulator/tools/sync_sources.py`; drop pooled cases from `Simulator/tests/test_lobby_game.py`.
6. Move `knowledge/` into ChatBroadcast `knowledge/` and `js/` into `js/splat/`; apply `platform_patch.md`
   and `game_patterns_patch.md`; replace `lobby_games.md`.
7. Update `known_issues/2026-11-11-simple-mode-large-changes.md` (host role is hardware-tested).

## Prompting notes for `claude-sonnet-5-5`

Source: the Claude API skill, "Migrating to Claude Sonnet 5.5". Checked against
`ChatBroadcast/js/prompt/buildRequest.js` (unchanged).

Already compatible, no change needed:

- Model id `claude-sonnet-5-5`; no `thinking`, `tool_choice`, `temperature` or prefill is sent.
- `output_config.format` is used for the interview turn.
- Three `cache_control` breakpoints, with the session text after the last one.

Rules for the draft knowledge files:

- **Order for caching.** Put stable content first: `game_types.md`, then the type files, then per-device
  files. Session data stays after the last breakpoint. A byte change early in the prompt invalidates
  everything after it. The minimum cacheable prefix is 512 tokens.
- **One canonical template per row.** The model copies the shape it is given; examples are the strongest
  signal. Mark the editable region and keep the rest identical across examples.
- **State rules positively, with the reason.** "Call `net.poll()` first: it reads the radio" works better
  than a bare NEVER. Avoid shouting, "do not be lazy" and similar workarounds.
- **Do not tell the model to think less.** Lower `CLAUDE_EFFORT` instead.
- **Effort.** Start at `low` for chat and generation from a template (current setting). Sweep `medium`
  on the eval for type 9 games, where host/player logic has more branches. Changing top-level effort
  invalidates the cache.
- **Row first.** The "state the row in one line" step doubles as a plan; keep it before any code.
- **Verification.** At `low` the model may report done without a check. The send-time check
  (`splatGameCheck.js`) is the verification, not the prompt.

Not applicable here: forced tool use, computer use, advisor, and task budgets.
