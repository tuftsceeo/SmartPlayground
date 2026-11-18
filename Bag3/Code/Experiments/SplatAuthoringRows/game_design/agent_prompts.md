# Agent prompts: known issues and built-in games

Prompts for fresh agents. Each is self-contained; paste one per session. All work starts from
branch `ccr-e1ed35ff-24apiv`, which holds the spec this file refers to. Run prompt 0 first and
merge its branch; the game prompts (1-7) build on it.

Source documents (in this folder):

- `builtin_games_spec.md`: the seven built-in games, shared access rules, signal set, color table,
  bonus games and system asks.
- `playground_game_examples.md`: the wider list of game ideas with CT and access scores, and the
  first list of system asks.

---

## Prompt 0: fill the system gaps the built-in games need

Run this first; the game prompts come after it is merged into the branch.

```
Repo: SmartPlayground. Start from branch ccr-e1ed35ff-24apiv; commit on your session's branch and
push there. No PR.

Read first: AGENTS.md; Bag3/Code/known_issues/README.md;
Bag3/Code/known_issues/2026-11-13-game-system-gaps.md (the gap list, with IDs and evidence);
Bag3/Code/Experiments/SplatAuthoringRows/README.md; and in
Bag3/Code/Experiments/SplatAuthoringRows/game_design/builtin_games_spec.md the sections
"3. Move Mixer" and "New system asks".

Fill only these gaps, which the seven built-in games need:
1. D3, icon display station mode. With no game running, the display obeys from any wand:
   {"type": "show", "icon": <name>}, {"type": "show", "px": [[row, col, [r, g, b]], ...]},
   {"type": "show", "text": <short string>}. No sender or target filtering. Unknown icon names
   print [ERR] and are ignored, not silently dropped. Model it on the Splat station mode in
   Experiments/SplatAuthoringRows/wand/lib/splat_host.py (_station_cmd) and use
   Stations/IconDisplay/lib/draw16.py and icon_store for drawing.
2. D2, the `dance` message: {"type": "dance", "s": [move names]}. The display loops the dance one
   step every 2 s, holds each for at least 2 full loops, and lets the newest waiting dance replace
   older waiting ones. No sender data. Build it on D3 if that keeps it simple; otherwise as a
   display game (play(nfc, panel, enow), as games/scoreboard.py).
3. K1 and K2, knowledge drafts: a mobility section for ChatBroadcast knowledge/accessibility.md,
   and a check of its vibration advice (every Bag3 wand has a vibration motor on GPIO 21 as well as
   the piezo speaker; the advice stands). Write them as
   a patch file in the experiment's knowledge/ folder; do not edit the live file.

Where: copy the files you change from Stations/IconDisplay/ into
Experiments/SplatAuthoringRows/display/ (same layout) and edit the copies. Do not edit
Stations/IconDisplay/, Wand Module/ or ChatBroadcast. Record the copy-back as a promotion step in
the experiment README.

Do not work on M1, M2, M3, S1, S2, A1-A6: they are recorded but out of scope. M3 needs the
user's decision.

Device rules (AGENTS.md): no allocation ahead of radio bring-up, so lazy-import anything new
after bring-up; py_compile is the only off-device check; no hardware, do not open serial ports.
Add unit tests in the experiment's tests/ with the display stubbed, as tests/test_wiring.py does.

When done, update the gap note's status rows for D2, D3, K1, K2 to "built in experiment, hardware
untested", with file paths.

Report under 150 words: files changed, test results, and any part of D2/D3 you could not do as
specified, with the reason.
```

---

## Shared brief for the game prompts (prompts 1-7)

Each game prompt below starts with this block. Paste the block, then the game's section.

```
Repo: SmartPlayground. Start from branch ccr-e1ed35ff-24apiv; commit on your session's branch and
push there. No PR.

Read first:
- AGENTS.md (device rules: no allocation before radio bring-up, py_compile is the only off-device
  check, f-strings fine, no type annotations, time.sleep_ms(1) in serial loops).
- Bag3/Code/known_issues/README.md, 2026-11-13-game-system-gaps.md, and any note whose keywords
  match your game.
- Bag3/Code/Experiments/SplatAuthoringRows/README.md (the experiment and its rules).
- Bag3/Code/Experiments/SplatAuthoringRows/game_design/builtin_games_spec.md: "Scope and rules",
  "Shared access rules", the shared signal set, the color/shape/note table, your game's section,
  and "Delivery checklist".

Rules:
- Edit only under Bag3/Code/Experiments/SplatAuthoringRows/. Do not edit Wand Module, the icon
  display tree, ChatBroadcast, Simulator, Live_Page, or the four game-tag consumers; list those
  changes as promotion steps in the experiment README.
- Use the shared signal set and color table exactly, so every built-in game looks and sounds the
  same.
- Read code around what you change (grep, then about 30 lines of context); do not read large
  files whole.
- No hardware is available. Do not open serial ports.
- Do not swallow errors.

Deliver:
- The game file, py_compile clean.
- A draft gallery entry for ChatBroadcast js/examples.js, as a file in the experiment
  (game_design/examples/<slug>.js), following the existing entries' fields.
- Teacher text: the quoted request, the card list, and the access notes.
- A README row under "Built-in games" with the slug, file, status, and promotion steps
  (game-tag consumers, gallery, Simulator vendor copy).
- One commit, message starting "SplatAuthoringRows:".

Report under 150 words: files changed, check results, anything in the spec you could not follow
and why, and open questions.
```

---

## Prompt 1: Echo Beat (type 1, wand)

```
[shared brief]

Build "1. Echo Beat" from builtin_games_spec.md as wand/games/echobeat.py.
- Standard wand game: play(nfc, leds, buz, accel, i2c, enow, batt=None), returning on stop or a
  start_game for another game, like the canonical wand template.
- Reuse the shake detection in wand/shake.py; do not write a new detector.
- Rhythms come from a fixed list per length (2-6 beats), defined at the top of the file.
- Each beeped beat flashes the matrix at the same time (the DHH rule).
```

## Prompt 2: Simon Stomp (type 2, wand + 2 Splats)

```
[shared brief]

Build "2. Simon Stomp" from builtin_games_spec.md as wand/games/simonstomp.py.
- Type 2 contract: SPLATS_LOCAL = 2 and play(..., batt=None, splats=None). Read the type 2 block
  in the experiment's knowledge/wand_type2.md and GameSplats in wand/lib/splatpair.py.
- Call enow.poll() and splats.poll() every loop. Leave Splat cleanup to the wand.
- Run node js/splat_game_check_test.mjs from the experiment and add a case for this game.
- Replace the Color Pads example in knowledge/wand_type2.md with this game, keeping the template
  shape.
```

## Prompt 3: Move Mixer (type 3, wand + optional icon display)

```
[shared brief]

Build "3. Move Mixer" from builtin_games_spec.md as wand/games/movemixer.py.
- Wand: no motion checks; build, preview, change and share as the spec says. The share message is
  {"type": "dance", "s": [...]} and carries no sender data.
- Display: use the `dance` support built by prompt 0 (gap D2, in the experiment's display/). Do
  not write a second display listener.
- Check the six card names (move_jump, move_spin, move_wave, move_freeze, move_twice, share)
  against every game and control tag in wand/lib/game_tags.py; rename on a clash and update the
  spec.
- Confirm the icons bunny, sunflower, hand and snowflake exist in
  Bag3/Code/Stations/IconDisplay/icons/.
```

## Prompt 4: Color Says (type 4, teacher's wand leads)

```
[shared brief]

Build "4. Color Says" from builtin_games_spec.md as wand/games/colorsays.py.
- First read wand/freeze_dance.py and find how it chooses and runs the leader (teacher) wand.
  Use the same mechanism; if Freeze Dance has none that fits, stop and report rather than
  inventing one.
- The teacher taps the existing action cards turnblue, turnyellow, turnpurple and turnwhite.
- The freeze check reuses Freeze Dance's motion check. No score.
- Teacher text names the game as Simón Dice / Simon Says.
```

## Prompt 5: Picture Moves (type 5, icon display leads)

```
[shared brief]

Build "5. Picture Moves" from builtin_games_spec.md: the display game as
display/games/picturemoves.py and the wand side as wand/games/picturemoves.py.
- Display: play(nfc, panel, enow), as Bag3/Code/Stations/IconDisplay/games/scoreboard.py. Show
  each animal icon for 15 s, broadcast the animal name on each change, and end after 8.
- Wand: chime and show a shape on each change; nothing else to check.
- Confirm every animal icon in the spec exists in Bag3/Code/Stations/IconDisplay/icons/.
```

## Prompt 6: Code Breakers (type 8, icon display)

```
[shared brief]

Build "6. Code Breakers" from builtin_games_spec.md as display/games/codebreakers.py.
- Display only: play(nfc, panel, enow), reading animal cards on the display's own NFC reader. Read
  Bag3/Code/Stations/IconDisplay/games/scoreboard.py, lib/draw16.py and icon_store.scale_into
  first.
- Feedback per the spec (bright dot per right place, dim dot per right animal in the wrong place),
  laid out with blank space between slots, feedback and try count.
- There is no chest icon: use star for the win. Do not add icons.
- The display has no buzzer; all feedback is visual. Note this as an access limit in the teacher
  text.
```

## Prompt 7: Pattern Stomp (type 9, Splat host + 4 Splats)

```
[shared brief]

Build "7. Pattern Stomp" from builtin_games_spec.md as wand/games/host_patternstomp.py.
- Type 9: write it fresh from the template in knowledge/splat_host_games.md, in the shape of
  wand/games/host_splattag.py. SPLAT_HOST = True, SPLATS_MIN = 4, play(..., batt=None, net=None).
- Group scoring only; a Splat does not know who stomped it.
- Handle lost Splats and lost players as the template does.
- Run node js/splat_game_check_test.mjs from the experiment and add a case for this game.
- Remove wand/games/host_lobbytest.py from the knowledge examples in favor of this game; keep the
  file itself and note it in the README.
```
