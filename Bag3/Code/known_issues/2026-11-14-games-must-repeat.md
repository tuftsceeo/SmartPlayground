---
title: Generated games end after a win instead of starting a new round
date: 2026-11-14
status: fixed in code 2026-11-16 (S10), deployed 2026-11-18; not checked by a person
devices: [Wand (Mock Wand), Splat host wand]
components: [ChatBroadcast knowledge, generated games, lobby/host games]
code:
  - Bag3/Code/ChatBroadcast/knowledge/game_patterns.md
  - Bag3/Code/ChatBroadcast/knowledge/devices/wand.md
  - Bag3/Code/ChatBroadcast/knowledge/splat_host_games.md
  - Bag3/Code/ChatBroadcast/knowledge/interview.md
  - Bag3/Code/Simulator/vendor/games/melody.py
  - Bag3/Code/Simulator/vendor/games/cooking.py
  - Bag3/Code/Simulator/vendor/games/freeze_dance.py
open:
  - Knowledge has no rule that games repeat forever until a stop message.
  - Generated Memory game returned from play() after the win.
keywords: [repeat, forever, new round, play again, win, end, celebration, stop, return, play(), lobby, knowledge]
related:
  - Bag3/Code/known_issues/2026-11-14-send-check-errors-ux.md (same test game)
---

# Generated games end after a win, 2026-11-14

Found testing ChatBroadcast (stress-test prep) with a generated Splat host game (Memory): when the
players won, the game ended.

## Rule (user, 2026-11-14)
The fun continues until a stop message is sent. After a win, loss or end of round, show the players
an appropriate celebration, then the game (or lobby) starts a new round. **Every game repeats
automatically, forever.** Examples: `melody`, `cooking`, `freeze_dance`.

## Gap (from the code)
- None of the ChatBroadcast knowledge files states this rule. `game_patterns.md` mentions rounds and
  "next round" for specific patterns only; `interview.md` asks "how a round ends or who wins", which
  invites a one-shot ending, and the generated brief said "It ends when all pairs are found".
- The named examples are in `Simulator/vendor/games/` only, not in the Bag3 wand's `games/`, so the
  model may not see them as references.

## Direction (not decided)
State the rule in the shared knowledge (all game types, including lobby and Splat host games) and
in the interview/brief wording ("ends a round", not "ends"). Consider a send-time check for a
`play()` that returns outside the stop/lost events.

## 2026-11-19: outcome

Fixed in ChatBroadcast on 2026-11-16 (stress-test plan S10, commits `27d1f716` and `1077fd13`) and deployed with the hosted app on 2026-11-18. No person-checked result is recorded.
