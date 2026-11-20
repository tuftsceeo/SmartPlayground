---
title: Simulator shows a game's start tag in the card tray when play does not need it
date: 2026-11-14
status: fixed in code 2026-11-16 (S10), deployed 2026-11-18; not checked by a person
devices: [Simulator, Wand (Mock Wand), Splat host wand]
components: [Simulator tag tray, runtime capabilities, generated games, ChatBroadcast knowledge]
code:
  - Bag3/Code/Simulator/py/runtime.py
  - Bag3/Code/Simulator/js/controls.js
  - Bag3/Code/ChatBroadcast/knowledge/devices/wand.md
open:
  - The tray offers the game's own start tag (e.g. "memory") although the game starts in the Simulator without it.
  - Generated games may listen for their own start tag during play.
keywords: [tag tray, start tag, game card, NFC, COMMANDS, EXIT_TAGS, exit_tags_excluding, own tag, Simulator, reset, clear game]
related:
  - Bag3/Code/known_issues/2026-11-14-games-must-repeat.md (same test game)
---

# Start tag in the Simulator card tray, 2026-11-14

Found testing ChatBroadcast (stress-test prep) with a generated Splat host game (Memory). The
Simulator's card tray showed a **memory** card. The instructions said to tap the Memory card on the
helper wand and on each child's wand, but in the Simulator the game started from the hold on the
helper wand's button alone; the card was never needed.

## Rule (user, 2026-11-14)
The game's start tag is not a play card. Keep it out of the tray unless the game needs it for both
starting and play, and avoid games that need it during play: the start tag is sometimes used to
reset or clear a game.

## Cause (from the code)
`Runtime` builds the tray from the game's `COMMANDS` (or `GAME_COMMANDS`) minus `EXIT_TAGS`, then
adds back the game's own tag when the game uses `exit_tags_excluding(own_tag)` and lists it in
`COMMANDS` (`py/runtime.py`, about lines 590-605). A generated game that does this gets its start tag
in the tray.

## Direction (not decided)
- Simulator: leave the game's own start tag out of the tray (the Simulator starts the game itself).
- Knowledge: tell the model not to react to its own start tag during play.

## 2026-11-19: outcome

Fixed in ChatBroadcast on 2026-11-16 (stress-test plan S10, commits `27d1f716` and `1077fd13`) and deployed with the hosted app on 2026-11-18. No person-checked result is recorded.
