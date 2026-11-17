# Prompt: build the seven built-in games

```
Repo: SmartPlayground. Start from branch ccr-e1ed35ff-24apiv; work and push on your session's
branch. No PR unless asked.

Goal: build seven built-in example games for Bag3 playground devices (wands, Splats, the
16x16 icon display). They will ship on the devices and in the ChatBroadcast example gallery, and
the chat agent will copy them when generating new games, so each should be a clean, readable
example of its game type.

The games and the reasoning behind them are in
Bag3/Code/Experiments/SplatAuthoringRows/game_design/builtin_games_spec.md; context, decisions
and testing notes are in game_design/HANDOFF.md. Treat the spec as the intent, not a script: its
timings, layouts and message shapes are starting points, and you decide how to implement.

The games:
1. Echo Beat: shake back a rhythm the wand buzzes.
2. Simon Stomp: one child repeats a growing pattern on their own 2 Splats.
3. Move Mixer: children build dances on their wands and can share one to the display for
   everyone to dance along. Ungraded; never show who shared.
4. Color Says: the teacher's wand picks a color; every wand shows it; each color means a move.
5. Picture Moves: the display shows animals; everyone moves like them.
6. Code Breakers: a small group cracks a card-order code at the display.
7. Pattern Stomp: a small group repeats a growing pattern on 4 Splats run by a Splat host wand.

What matters:
- Fun, big-movement play for ages 5-9; wands at the center, stations as shared extras.
- Accessible: color never the only signal, sound paired with light, gentle mistakes,
  predictable cues shared across all seven games. See ChatBroadcast knowledge/accessibility.md.
- Don't single children out.
- Simple code a teacher-facing chat model can learn from.

Constraints:
- Read AGENTS.md first, and Bag3/Code/known_issues/ for anything you touch (notably
  2026-11-13-game-system-gaps.md and the icon list in game_design/icon_needs.md).
- Unproven code stays in Bag3/Code/Experiments/SplatAuthoringRows/. Note what would need to
  change elsewhere (game tags, gallery, icon sets) for promotion instead of editing it.
- Follow the device rules in AGENTS.md, especially the radio-first memory rule.
- No hardware in this session: check with py_compile and the experiment's tests, and leave a
  short hardware test list for a later session with the user.
- If something in the spec doesn't work out (a missing icon, a gap such as display station
  mode, a better mechanic), make a reasonable call, note it, and keep going; ask only about
  real design choices.

Commit as you go. When done, report briefly: what was built, how it was checked, what you
changed from the spec and why, and what's left.
```
