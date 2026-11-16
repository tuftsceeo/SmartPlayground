"""Wand game / control tag names.

Cards carry plain NDEF text (see HARDWARE_PROTOCOL.md, "NFC card safety"),
so the names below ARE the wire format -- there is no byte encoding to keep
in step with them. This file used to re-export them from opcodes.py, whose
4-byte card scheme the wand stopped using; nothing here needed the rest of
that module.

  GAME_TAGS    -- names of game tags only (no "stop", no "start").
  CONTROL_TAGS -- programming-mode controls ("start", "stop").
  HIDDEN_TAGS  -- ESP-NOW-only "games" (never on a physical card).
  EXAMPLE_TAGS -- the built-in example games in games/ (copied to
                  /games/<slug>.py, found at runtime like pulled games, so
                  they are not in main.py's GAME_MODULES).
  EXIT_TAGS    -- every tag that exits a running game (GAME_TAGS | EXAMPLE_TAGS | {"stop"}).
  exit_tags_excluding(tag) -- EXIT_TAGS without one game's own entry tag.

main.py checks GAME_TAGS|HIDDEN_TAGS against its own GAME_MODULES at boot and
prints a mismatch: nothing else keeps the two in step.
"""

GAME_TAGS = {
    "colorquest",
    "freezedance",
    "jumpin",
    "cooking",
    "melody",
    "shake",
    "shakerainbow",
    "rainbow",
    "jump",
    "sound",
    "nfcsound",
    "simpleicecream",
    "multiicecream",
    "gestures",
    "goalrace",
    "splatecho",
}

CONTROL_TAGS = {"start", "stop", "unpair"}

# ESP-NOW only, never printed on a card.
HIDDEN_TAGS = {"finddevice"}

# Built-in examples (game_design/builtin_games_spec.md). picturemoves and
# codebreakers also have display halves (IconDisplay/games/).
EXAMPLE_TAGS = {
    "echobeat",
    "simonstomp",
    "movemixer",
    "colorsays",
    "picturemoves",
    "host_patternstomp",
}

EXIT_TAGS = GAME_TAGS | EXAMPLE_TAGS | {"stop"}


def exit_tags_excluding(game_tag):
    """EXIT_TAGS copy without this game's own entry tag.

    The entry tag is often still under the wand when play() starts;
    excluding it avoids an immediate exit on the first NFC poll. Never
    mutates EXIT_TAGS.
    """
    tags = set(EXIT_TAGS)
    tags.discard(game_tag)
    return tags
