---
title: Splat host games under-count wands by one (host wand left out)
date: 2026-11-14
status: open (no change made)
devices: [Splat host wand, Wand (Mock Wand)]
components: [ChatBroadcast device line, GAME_SETTINGS, interview brief]
code:
  - Bag3/Code/ChatBroadcast/js/app.js
  - Bag3/Code/ChatBroadcast/js/chat.js
  - Bag3/Code/ChatBroadcast/knowledge/splat_host_games.md
  - Bag3/Code/ChatBroadcast/knowledge/interview.md
open:
  - Device line for a Splat host game shows children's wands only (e.g. "2 wands, 4 Splats" for a game needing 3 wands).
  - The interview brief can also give "Wands 2-2" without the host.
keywords: [wand count, Splat host, helper wand, device line, deviceNeeds, savedGameDevices, GAME_SETTINGS, wands, splat_host, brief]
---

# Splat host games under-count wands by one, 2026-11-14

Found testing ChatBroadcast (stress-test prep) with a generated Splat host game (Memory). The app
showed **2 wands, 4 Splats**. The game needs **3 wands**: 2 children's wands plus 1 Splat host wand
(which holds the 4 Splats).

## Cause (from the code)
- `GAME_SETTINGS` `wands` counts children's wands only; `splat_host` is the host's Splat count
  (`knowledge/splat_host_games.md`).
- `savedGameDevices()` in `js/app.js` passes `wands` straight to `deviceNeeds()` and adds the host's
  Splats, but never adds the host wand.
- The first interview brief for the same game said "Wands (min-max): 2-2" with a helper wand in the
  text; a later brief said "2 children's wands, plus 1 helper wand (3 in all)". The brief format in
  `knowledge/interview.md` does not say to count the host.

## Direction (not decided)
Show the host as its own item ("2 wands + 1 Splat host wand, 4 Splats") or add it to the total,
and have the interview brief count it. Check every place the device line is built.
