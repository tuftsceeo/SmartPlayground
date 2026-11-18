---
title: Hold-to-act interactions are not clear to teachers
date: 2026-11-14
status: open (UX concern, no change made)
devices: [Splat host wand, Wand (Mock Wand), BroadcastDial]
components: [splat_host.py button/frame, lobby_game.py host button, ChatBroadcast knowledge and game briefs]
code:
  - Bag3/Code/Wand Module/lib/splat_host.py
  - Bag3/Code/Wand Module/lib/lobby_game.py
  - Bag3/Code/ChatBroadcast/knowledge/splat_host_games.md
open:
  - The hold that starts a Splat host game does not read as "keep holding, something is happening".
  - Generated game text says "the teacher holds the helper wand's button to start" with no cue for how long or what to watch.
  - No shared rule that every hold interaction shows progress.
keywords: [hold, long press, button, start, progress, indicator, Splat host, helper wand, lobby, START_HOLD_MS, END_HOLD_MS, FORGET_HOLD_MS, UX]
---

# Hold-to-act interactions are not clear to teachers, 2026-11-14

Found while testing ChatBroadcast (stress-test prep). A generated Splat host game (Memory) told the
teacher: "Teacher holds the helper wand's button to start." The user judged this not a clear way to
start a game.

## Concern
Hold interactions need a visible progress indicator, like the Broadcast Dial's, so the person can
see that the hold is doing something and should keep holding until it triggers.

## Current state (from the code, not observed)
- `splat_host.py`: start needs `START_HOLD_MS` 1500, end `END_HOLD_MS` 3000, forget
  `FORGET_HOLD_MS` 4000. After `SHORT_PRESS_MS` 400 the host fills a cross (`CROSS_FILL`,
  `HOLD_RGB`) in proportion to the hold; forget turns corners off once per second. An indicator
  exists, but the user still found the start unclear.
- `lobby_game.py`: the lobby host uses the same button handler (short press peeks the count, hold
  starts).
- The teacher-facing text (`knowledge/splat_host_games.md`, game briefs) says only "hold the
  button", with no duration or what to look for.

## Directions (not decided)
- Make the fill unmistakable from the first moment of the hold, finishing with a clear "done" flash
  and sound.
- Apply one rule to every hold interaction on every device: progress shown from press to trigger.
- Have generated descriptions say what the teacher will see ("hold until the lights fill").
