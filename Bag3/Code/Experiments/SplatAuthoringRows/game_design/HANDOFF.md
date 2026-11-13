# Handoff: game design, built-in games, gaps and icons

> **Status 2026-11-13 (W6 session, branch `wand-splat-update`):** Prompt 0, the P1 icons and the
> seven games are built (py_compile only, hardware untested). The games live in the main trees,
> not the experiment: `Wand Module/games/` (+ `lib/signals.py`) and `Stations/IconDisplay/games/`.
> `IconDisplay/main.py` now mirrors the wand's structure and game contract, and station mode is
> `IconDisplay/lib/display_station.py`. M3 is decided (optional `"to": <mac>`; see the gap note).
> Knowledge edits (accessibility mobility bullet, Simon Stomp example, shared signals, display
> station mode) are committed but **`tools/prompt_eval.mjs` has not run** (no API key in the
> session); run it before merging. Sections below describe the plan as it stood before.

State as of 2026-11-13, branch `ccr-e1ed35ff-24apiv`. This line of work produced designs, notes,
prompts and a draft icon set; **no game code and no gap fixes are built yet**, and nothing has
been tested on hardware.

Read AGENTS.md first. Its rules apply throughout (experiment-only edits, radio-first memory rule,
`py_compile` as the only off-device check, Bag2/Bag3 trees independent, game tags in four places).

## 1. What exists

All paths are under `Bag3/Code/` unless stated.

| File | What it is | Status |
|---|---|---|
| `Experiments/SplatAuthoringRows/game_design/builtin_games_spec.md` | Spec for the seven built-in games, shared access rules, shared signal set, color/shape/note table, bonus games, system asks | Agreed with the user |
| `Experiments/SplatAuthoringRows/game_design/playground_game_examples.md` | Wider idea list (28 games) with CT and accessibility scores | Reference |
| `Experiments/SplatAuthoringRows/game_design/agent_prompts.md` | Prompt 0 (fill gaps) and prompts 1-7 (one per game), with a shared brief | Ready to run |
| `Experiments/SplatAuthoringRows/game_design/icon_needs.md` | Missing 5x5 and 16x16 icons, by priority | Verified against the icon sets |
| `Experiments/SplatAuthoringRows/game_design/icon_image_prompt.md` | Image generation prompt (7 sheets) plus the draft 1 review | Draft 1 reviewed; prompt revised |
| `Experiments/SplatAuthoringRows/game_design/tools/icon_sheet_preview.py` | Finds icons on a generated sheet and previews each at 16x16 | Works on draft 1 (85 icons found) |
| `known_issues/2026-11-13-game-system-gaps.md` | All system gaps with IDs (D, M, A, S, H, R, C, K) and status | Recorded |
| `known_issues/2026-11-13-game-ideas-backlog.md` | Ideas not chosen, and the gap blocking each | Recorded |

The game work depends on the SplatAuthoringRows experiment (type 2 local Splats, Splat host
template, station mode). Its own status and promotion checklist: `Experiments/SplatAuthoringRows/README.md`
and `PLAN.md`.

## 2. Decisions made (do not reopen without the user)

- **Seven built-in games:** Echo Beat (1), Simon Stomp (2), Move Mixer (3), Color Says (4),
  Picture Moves (5), Code Breakers (8), Pattern Stomp (9). No examples for types 6 and 7.
- **Equipment:** wands, Splats, icon display only. No speaker station (not built).
- **Splat host code is assumed verified** on hardware for planning.
- **Wands are the center of games.** Stations are limited and shared; a game must not leave
  children waiting for a station.
- **Move Mixer:** children build dances on their wands and choose to share; the display loops the
  latest shared dance. **No grading, no motion checks, no sender identity shown.** Do not single
  children out (no identity colors on shared displays).
- **Gross motor play** is preferred over screen-style games.
- **Hardware facts from the user:** Splats are designed for stomping; wands survive running and
  big shakes, most drops. The icon display has an NFC reader, no buzzer, no buttons.
- **M3 (targeted messages) is open:** it conflicts with "icon displays and station mode never
  filter by sender or target". Ask the user before building anything that needs it.

## 3. Work order

1. **Prompt 0, fill gaps** (`agent_prompts.md`): D3 display station mode, D2 `dance` message,
   K1/K2 accessibility knowledge drafts. In the experiment only.
2. **Icons P1** (needed by the games): 5x5 `SHAPE_TRIANGLE`, `SHAPE_HAND`, `SHAPE_SNOWFLAKE`;
   16x16 `circle`, `triangle`, `square`, `check`, `cross`. Draft 1 art exists for all of these.
3. **Prompts 1-7, games**, after step 1 is merged. 1, 3, 4, 5, 6 can run in parallel; 2 and 7
   both edit the knowledge files and the JS check test, so run them one after the other.
4. **Icons P2/P3** and regeneration of the draft 1 failures.
5. **Hardware tests** (section 5), with the user.

## 4. Off-device testing

Run from the repo root unless stated.

| Check | Command | Expected |
|---|---|---|
| Device code compiles | `find Bag3/Code/Experiments/SplatAuthoringRows -name '*.py' -exec python -m py_compile {} \;` then delete `__pycache__` | no output |
| Experiment unit tests | `cd Bag3/Code/Experiments/SplatAuthoringRows && python3 -m unittest discover -s tests` | all pass (8+ before new work) |
| Splat game send check | `cd Bag3/Code/Experiments/SplatAuthoringRows && node js/splat_game_check_test.mjs` | `all passed`; add a case per new Splat game |
| Icon drift (16x16) | `python3 Bag3/Code/BroadcastCode/ChatBroadcast/tools/sync_icons.py --check` | exit 0; run after adding icons |
| Icon readability | `python3 Bag3/Code/Experiments/SplatAuthoringRows/game_design/tools/icon_sheet_preview.py <sheet.jpg> <out.png>` | review each icon at 16x16 by eye |
| Scope | `git diff --stat origin/ccr-e1ed35ff-24apiv` | changes only under the experiment (plus known_issues notes) |

pytest is not installed in the cloud container; use `unittest`. No serial ports in cloud sessions.

**Per game, also check against the spec by reading the code:**
- Uses the shared signal set and color/shape/note table exactly.
- Every light cue has a sound and every sound has a light (access rules).
- Returns on `stop` or a `start_game` for another game; `enow.poll()` every loop.
- No new import ahead of radio bring-up; no prints in modules imported before the radio.
- Game slug does not collide with existing tags (`Wand Module/lib/game_tags.py`).
- Icons named exist in `Stations/IconDisplay/icons/`.

## 5. Hardware testing (with the user, local session)

Load the `bag3-hardware-protocol` skill and read `HARDWARE_PROTOCOL.md` before any port. Wands on
MicroPython v1.28.0 (`known_issues/2026-11-12-splat-host-v129-firmware.md`). Copying to a running
Splat host with mpremote is a known issue (`2026-11-12-wand-mpremote-copy-fails.md`). The
experiment's `deploy.py` stages files and prints commands; it opens no port.

| Test | Pass when |
|---|---|
| Boot memory | `idf largest` after imports is at least 163840 (bench figure at `9d1a8b8d`) |
| Echo Beat | Shake rhythms of 2-6 beats are recognized within tolerance; lights flash with each beat |
| Simon Stomp | 2 Splats light and play notes; a wrong order replays without a harsh sound; refused with fewer than 2 Splats |
| Move Mixer | Cards add steps; preview plays at the 2 s beat; `share` updates a display in range; display holds each dance 2 loops; no sender shown |
| Color Says | Teacher wand (Freeze Dance's leader mechanism) sets every wand's color, shape and note; freeze shows amber on movement |
| Picture Moves | Display cycles animals every 15 s; wands chime on each change |
| Code Breakers | Card order feedback is correct; layout readable at 16x16 |
| Pattern Stomp | Host with 4 Splats and 2+ player wands; group stomps scored; a lost Splat pauses the game |
| Station mode (D3) | Two displays both obey one wand's `show` message |
| Radio (R1, R2) | Range across the playground; behavior with about 25 wands sharing (record, do not fix) |

Record results and failures as known-issue updates; don't re-test a documented failure.

## 6. Icon work

- **Draft 1:** about 50 of 85 read well at 16x16. Redo list, missing sheet 3, and style fixes are
  in `icon_image_prompt.md` ("Draft 1 review"); the style block already includes the fixes.
- **Next:** regenerate the failures and sheet 3 one sheet per request; preview with the tool;
  crop, downsample to 16x16 and convert to the icon file format in
  `Stations/IconDisplay/icons/` (no converter exists yet; `Stations/Icon Display Station/` has
  `grid_to_icon.py` and `hand_author_icons.py` to start from).
- **5x5 shapes** are hand-drawn index lists in `leds.py` and mirrored in `shapes5.js`; keep them
  plain constants (radio-first rule).
- **Before shipping art:** draft 1 looks close to a common emoji style. If the image tool copied
  an existing emoji set, check its license.
- `SHAPE_PACMAN` and `SHAPE_INVADER` resemble trademarked characters; flagged, not changed.

## 7. Open questions for the user

- M3: allow targeted messages, or keep "every device obeys"?
- Display hardware: add a buzzer (H1) or button (H2)?
- Wand icon: what does the real wand look like, for the `wand` icon?
- Move Mixer: is a 2 s step right for ages 5-9?
- Which tree gets the built-ins when promoted (Bag3 only, per the spec)?
