# Agent prompts: known issues and built-in games

Prompts for fresh agents. Each is self-contained; paste one per session. All work starts from
branch `ccr-e1ed35ff-24apiv`, which holds the spec this file refers to.

Source documents (in this folder):

- `builtin_games_spec.md`: the seven built-in games, shared access rules, signal set, color table,
  bonus games and system asks.
- `playground_game_examples.md`: the wider list of game ideas with CT and access scores, and the
  first list of system asks.

---

## Prompt 0: record firmware gaps and game ideas as known issues

```
Repo: SmartPlayground. Start from branch ccr-e1ed35ff-24apiv; commit on your session's branch and
push there. Read AGENTS.md, then Bag3/Code/known_issues/README.md and one existing note for the
front matter format.

Task: record, do not implement. Turn the system asks in
Bag3/Code/Experiments/SplatAuthoringRows/game_design/builtin_games_spec.md ("New system asks")
and playground_game_examples.md ("System asks") into known-issue notes, plus one note for game
ideas.

1. Group the asks into a few notes by component, not one per ask:
   - Icon display: D1 (card-order/set game logic), D2 (`dance` message), D3 (display station mode),
     M1 (display host/peripheral roles).
   - Splat host: M2 (host federation for 8-12 Splats), A1 (who stomped a Splat).
   - Wand: A2 (stillness check), A3 (team totals via a leader wand), A4 (peer token pass),
     A5 (rhythm relay latency), A6 (wand proximity; not supported), K2 (vibration motor or buzzer
     only).
   - Speaker station: S1 (card reader or wand control), S2 (layered sounds).
   - Cross-cutting: M3 (targeted messages), which conflicts with the decision that icon displays
     and Splat station mode never filter by sender or target. Record it as a decision needed.
   - Knowledge: K1 (mobility guidance missing from ChatBroadcast knowledge/accessibility.md).
2. For each ask give: one-sentence need, the games that need it, current status (verified,
   unverified, not supported), and the code paths involved. Before writing a status as verified,
   check the code with grep; otherwise write "unverified".
3. One more note, "game ideas", listing the games in playground_game_examples.md not chosen as
   built-ins, each with the ask that blocks it (or "design only"), and the bonus games B1 Habitat
   Hop and B2 Stepping Song.
4. Use the front matter of existing notes (title, date, status, devices, components, code, open,
   keywords). Add one index row per note to known_issues/README.md.
5. Do not re-test or fix anything. Do not edit device code.

Report under 150 words: notes created, asks you marked verified (with the evidence), and any ask
that duplicates an existing known issue.
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
- Bag3/Code/known_issues/README.md, and any note whose keywords match your game.
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
- Each buzzed beat flashes the matrix at the same time (the DHH rule).
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

Build "3. Move Mixer" from builtin_games_spec.md: the wand game as wand/games/movemixer.py and a
display listener as display/games/movemixer.py.
- Wand: no motion checks; build, preview, change and share as the spec says. The share message is
  {"type": "dance", "s": [...]} and carries no sender data.
- Display: play(nfc, panel, enow), as Bag3/Code/Stations/IconDisplay/games/scoreboard.py; read it
  and lib/draw16.py first. Hold each dance for two full loops; the newest waiting dance replaces
  older waiting ones.
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
