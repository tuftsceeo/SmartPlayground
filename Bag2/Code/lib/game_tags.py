"""Single source of truth for wand game / control tag names.

Imported by main.py (for CONTROLS / dispatch) and by every game module so
each game's NfcReader can recognize *any* game tag and exit cleanly when
one is tapped. This is what enables fluid game-to-game switching without
requiring an explicit "stop" tag.

Set design:
  GAME_TAGS  — names of game tags only (no "stop", no "start").
  CONTROL_TAGS — programming-mode controls ("start", "stop").
  EXIT_TAGS  — superset: every tag that should cause a running game to
               exit back to main.py. Equals GAME_TAGS | {"stop"}.
               GAME_TAGS itself stays clean (games only) so it can be
               used wherever "is this a game?" is the question.
"""

GAME_TAGS = {
    "colorquest", "freezedance", "jumpin", "cooking", "melody",
    "shake", "shakerainbow", "rainbow", "jump", "sound", "nfcsound",
    "simpleicecream", "multiicecream", "gestures",
}

CONTROL_TAGS = {"start", "stop"}

EXIT_TAGS = GAME_TAGS | {"stop"}
