"""
Icon display game / control tag names.

The same shape as the wand's game_tags.py, so a display game reads like a
wand game: a module-level COMMANDS set of string literals, unioned with the
exit tags. It is a separate table rather than an import of the wand's --
the two devices do not play the same games, and the card that starts a wand
game must not also start something on the display.

  GAME_TAGS    -- names of display game tags (no "stop", no "getcode").
  CONTROL_TAGS -- idle-mode controls the display answers to.
  EXIT_TAGS    -- every tag that exits a running game (GAME_TAGS | {"stop"}).
  exit_tags_excluding(tag) -- EXIT_TAGS without one game's own entry tag.

main.py checks GAME_TAGS against its own GAME_MODULES at boot and prints a
mismatch: nothing else keeps the two in step.
"""

GAME_TAGS = {
    "goalrace",
}

CONTROL_TAGS = {"stop", "getcode"}

EXIT_TAGS = GAME_TAGS | {"stop"}


def exit_tags_excluding(game_tag):
    """EXIT_TAGS copy without this game's own entry tag.

    The entry tag is often still on the reader when play() starts; excluding
    it avoids an immediate exit on the first NFC poll. Never mutates
    EXIT_TAGS.
    """
    tags = set(EXIT_TAGS)
    tags.discard(game_tag)
    return tags
