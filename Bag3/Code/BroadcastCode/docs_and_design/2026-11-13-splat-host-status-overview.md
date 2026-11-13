# Splat host wand: status overview and completion guide (2026-11-13)

Bag3 only; Bag2 is not touched. Branch `wand-splat-update` at `4c1ddf7a`, in step with `origin`.
This note sits above three narrower handoffs and says what is done, what is checked, and the order
to finish in.

| Topic | Detailed handoff |
|---|---|
| Screen, pairing, Simulator | `2026-11-13-splat-host-handoff.md` and the plan `2026-11-12-splat-host-screen-pairing-plan.md` (this folder) |
| Memory and the 4-Splat limit | `Bag3/Code/Experiments/SplatHostBench/HANDOFF.md` |
| Game authoring rows, built-in games, icons | `Bag3/Code/Experiments/SplatAuthoringRows/game_design/HANDOFF.md`, `README.md`, `PLAN.md` |

Read `AGENTS.md`, `Bag3/Code/HARDWARE_PROTOCOL.md` and the known-issue notes
`2026-11-11-simple-mode-large-changes.md` (item 3) and `2026-11-12-splat-host-v129-firmware.md` first.

## What the role is

A wand whose `/role.txt` is `splat_host`, set by an NFC `splat_host`/`player` card or a teacher
`set_role` message. It holds up to `pairing.HOST_MAX_SPLATS` (4) Splats and always leads the lobby
of a `SPLAT_HOST = True` game. The lobby player count excludes the host. It is operated by the teacher,
held right side up, and takes no tilt input. Its screen has four 2x2 corners (one Splat each, shown as
its color pair) and a center cross that shows the state.

## Commits on the branch

| Commit | Content |
|---|---|
| `12d09ff` | Role, `HOST_MAX_SPLATS`, host lobby (`h:1`, `p`), `host_*` games, Simulator host card, ChatBroadcast `splat_host` setting and checks, knowledge |
| `76f6a4b` | Splat `left`/`right` light parts (`splat_api.py`, `splatActions.js`), Simulator zones |
| `45b02d9` | Simulator Splat colors: additive blends, LED model |
| `9d1a8b8` | `main.py` starts ESP-NOW before other imports; bench scripts; `deploy.py` fix |
| `d9855f74` "splat test work" | Plan firmware: corners, pairs, slot reuse, peek, holds, `pw_lobby` `c`; devtest extended |
| `e534aef`, `3cb1c88`, `d24fcc05` | Memory bench (`Experiments/SplatHostBench/`) |
| `ccr-*` merges, `59a5c390` | SplatAuthoringRows experiment: type 2/type 9 contracts, station mode, game designs, icon drafts |
| `4c1ddf7a` | The plan and the screen/pairing handoff committed |

## Status by area

### Firmware (`Bag3/Code/Wand Module/`)

- **Done:** role switching; host lobby; `splat_host.py` screen (corners, next-slot breathing, missing flash,
  pulse, cross for lobby/playing/hold, center lobby color) and button (peek 4 s, start hold 1.5 s,
  end hold 3 s, forget hold 4 s); `pairing.py` slots (own, then first missing, then first empty;
  fifth refused); pairs from the Splat MAC; `pw_lobby` `c`; ESP-NOW first in `main.py`.
- **Not confirmed against the plan:** the player-wand dots in a host lobby; the tap feedback (sound and
  buzz on pair and refuse); the `left`/`right` pair glow on the Splat. Review `d9855f74` line by line
  against the plan.
- **Stale:** `flash_bundle/wand_main.mpy` was last built 2026-11-10, before `9d1a8b8` and `d9855f74`.
  Regenerate it before any deploy that uses the bundle.

### Hardware results

- **Pairs:** all 30 ordered pairs of the six palette colors, on the Splat's left/right halves at
  `GLOW_SCALE` 0.5, were read as distinct. The palette is still provisional (plan: six colors, not the spec's 12).
- **Splat count:** the limit comes from the IDF main heap, not a connection cap.
  - v1.28.0: 4 of 4 Splats.
  - v1.29.0 bare (STEP 0): 4 of 4.
  - v1.29.0 after the full wand imports (STEP 3): 1 of 4.
  - v1.29.0 full boot: 2 of 4.
- **Open bench:** the connect-first bench (`bench_step5.py`) has only an invalid run (the board was not
  reset). It needs a clean run on COM11 (hard reset, Splats power-cycled).
- **Never run:** a host boot with 4 paired Splats on the plan firmware; memory for play
  (`compile()` of a 10 KB game, a code pull) with 4 connected.

### Simulator (`Bag3/Code/Simulator/`)

- **Done:** host card; Splat zones and colors; vendored firmware synced at `d9855f74`, except as below.
- **Failing now:**
  - `tools/sync_sources.py --check` reports drift in `vendor/lib/splatpair.py`. Re-run `sync_sources.py`.
  - `pytest tests/test_splat_host.py` fails `test_host_leads_and_counts_players` (no `pw_start`). The
    test presses the button briefly, which is now a peek; a start needs a 1.5 s hold. Update the test,
    not the firmware.
  - `node --test tests/js/*.test.mjs` passes, 24 of 24.
- **Not done (plan):**
  - The host wand drawn compact, without tilt or shake controls.
  - Slots in `js/panels/splatController.js` showing pair colors and the missing state.
  - Oversized wand-owned Splat cards.
  - `gameSplats` (`js/panels/wands.js:145`) is a fixed 1 for game wands and does not read `caps.splat_host`.
  - A browser check with screenshots.

### ChatBroadcast and API knowledge (`Bag3/Code/BroadcastCode/ChatBroadcast/`)

- **Live and passing:**
  - `[GAME_SETTINGS:]` `splat_host` 0–4.
  - The `splatGameCheck.js` host checks (`SPLAT_HOST`, `PLAYERS_MIN`, `HOST_MAX_SPLATS`).
  - `knowledge/{lobby_games,platform,game_patterns}.md`.
  - Host games written by default.
  - `splat_game_check_test.mjs` passes.
  - `sync_splat_actions.py --check` is OK: 29 names, with `left`/`right`.
- **Drafted, not applied:** in `Experiments/SplatAuthoringRows/`:
  - `knowledge/splat_host_games.md`;
  - the stricter `js/splatGameCheck.js`;
  - `js/wiring/readers.patch` and `devtests.patch`.

  These change the contract: type 9 games call `net.poll()` and get the Splats through `net`, pooled
  games are removed, and type 2 games use local Splats. No prompt eval has been run.

### Experiment: SplatAuthoringRows

- **State:** `wand/` is a fork of `Wand Module/` at `3cb1c884`, with:
  - pooled Splats removed;
  - `GameSplats` for solo games;
  - station mode, where an idle host obeys `splat` messages and broadcasts `splat_press`.
- **Tests:** 17 tests pass off-device. Nothing has run on hardware.
- **Dependencies:** the seven built-in game designs and the icon work build on this experiment.
  The experiment has not been promoted into `Wand Module/`.
- **Rebase needed:** the fork predates `d9855f74`. Its `splat_host.py`, `splatpair.py` and `lobby_game.py`
  need the plan firmware merged in before promotion.

## Completion order

1. **Off-device fixes.** Re-sync the Simulator vendor files, then update the Simulator host test to hold
   the button. Then run `py_compile` on the changed `.py`, all four test sets (devtests script,
   Simulator pytest, `node --test`, ChatBroadcast tool tests), and both `--check`s.
2. **Plan review.** Check `d9855f74` against the plan, and fill the gaps: player dots, tap feedback,
   the pair glow on the Splat.
3. **Simulator plan items.** Then a browser check: pair 4, unpair and re-pair one to see the
   missing slot reused, the lobby cross, the peek, the start/end/forget holds, the player dots.
4. **Hardware, with the user's OK and under `HARDWARE_PROTOCOL.md`.**
   - (a) A clean `bench_step5.py` on COM11.
   - (b) If connecting first holds 4 Splats on v1.29.0, move that order into `main.py` as
     `SplatHostBench/HANDOFF.md` step 3 describes.
   - (c) A host boot with 4 paired Splats: count, MEM lines, corners, pair glow, missing flash, peek,
     holds, fifth refused.
   - (d) Memory for play.
   - Fallbacks if (b) fails: frozen libraries, a fixed heap, `.mpy` games.
5. **Regenerate `flash_bundle`.** Then record the results in the two known-issue notes.
6. **Promote SplatAuthoringRows.** Rebase `wand/` onto the plan firmware, then apply the ChatBroadcast
   wiring and knowledge, after a prompt eval. Then follow the game-design handoff: gap fill, P1
   icons, the seven games.

## Open decisions for the user

- The final color palette, after the palette bench test (six colors is provisional).
- Whether v1.29.0 is supported for hosts, or hosts stay on v1.28.0, if step 4(b) fails.
- M3 targeted messages, a game-design handoff item that conflicts with station mode's "never filter".
- When to push, and when to open a PR against `September_2026`. Nothing in this note is pushed by its author.
