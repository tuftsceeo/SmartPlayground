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

# Games dispatched only over ESP-NOW (never via NFC). Not in GAME_TAGS, so they
# never appear as tappable games / webapp commands / remote buttons, but they
# are valid GAME_DISPATCH keys. "finddevice" is the targeted identify animation.
HIDDEN_TAGS = {"finddevice"}

EXIT_TAGS = GAME_TAGS | {"stop"}


def exit_tags_excluding(game_tag):
    """EXIT_TAGS copy without this game's entry tag.

    The entry tag is often still under the wand when play() starts; excluding
    it avoids an immediate exit on the first NFC poll. Never mutates EXIT_TAGS.
    """
    tags = set(EXIT_TAGS)
    tags.discard(game_tag)
    return tags
