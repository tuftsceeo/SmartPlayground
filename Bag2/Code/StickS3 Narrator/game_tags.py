"""Single source of truth for wand game / control tag names.

Bundled copy of ../lib/game_tags.py (UIFlow upload needs every file at the
device root -- keep in sync by hand, same pattern as ../M5Paper Remote/).
"""

GAME_TAGS = {
    "colorquest", "freezedance", "jumpin", "cooking", "melody",
    "shake", "shakerainbow", "rainbow", "jump", "sound", "nfcsound",
    "simpleicecream", "multiicecream", "gestures",
}

CONTROL_TAGS = {"start", "stop"}

HIDDEN_TAGS = {"finddevice"}

EXIT_TAGS = GAME_TAGS | {"stop"}


def exit_tags_excluding(game_tag):
    tags = set(EXIT_TAGS)
    tags.discard(game_tag)
    return tags
