---
title: Game start signature (GAME_ICON) — partial
date: 2026-11-11
status: open
devices: [wand, icon_display]
components: [ChatBroadcast, Wand Module]
code:
  - Bag3/Code/ChatBroadcast/knowledge/platform.md
  - Bag3/Code/ChatBroadcast/js/chat.js
  - Bag3/Code/ChatBroadcast/js/app.js
  - Bag3/Code/Wand Module/main.py
open:
  - App does not draw the signature anywhere (save, library, send-confirm)
  - Marker names are not validated against leds shapes/colors
  - Wand shows the green check after a pull, not the pulled game's GAME_ICON
  - freezedance, simpleicecream, multiicecream do not open with their GAME_ICON pair
  - main.py lists melody as (SHAPE_MUSIC, CYAN) but melody.py opens with TEAL; cooking opens with no shape
keywords: [GAME_ICON, start signature, entry sound, marker, shape, color]
aliases: []
---

# Game start signature (GAME_ICON)

Generated games declare `GAME_ICON = (SHAPE_X, COLOR)` and open with that shape and color for about
1 s plus an entry sound; an icon display file opens with the same pair. The rules are in
`knowledge/platform.md` ("Start signature") and the device templates. The chat reply carries
`[GAME_ICON: SHAPE_X, COLOR]`; `parseGameIcon` reads it and the app stores it as `gameIcon` in
state and in the saved library entry.

## Open

- The app stores the signature but does not show it anywhere.
- Marker names are not validated; a misspelled name is stored as given.
- After a radio pull the wand still shows `SHAPE_CHECK` in GREEN. The game's own `play()` shows
  its signature next.
- freezedance and the ice cream games don't open with their main.py pair. In main.py's table
  melody is listed as (SHAPE_MUSIC, CYAN), but melody.py opens with TEAL. Cooking opens with no
  shape.
