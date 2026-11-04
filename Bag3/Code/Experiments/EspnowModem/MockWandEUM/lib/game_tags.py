"""Wand game / control tag names.

Cards carry plain NDEF text (see HARDWARE_PROTOCOL.md, "NFC card safety"),
so the names below ARE the wire format -- there is no byte encoding to keep
in step with them. This file used to re-export them from opcodes.py, whose
4-byte card scheme the wand stopped using; nothing here needed the rest of
that module.

  GAME_TAGS    -- names of game tags only (no "stop", no "start").
  CONTROL_TAGS -- programming-mode controls ("start", "stop").
  HIDDEN_TAGS  -- ESP-NOW-only "games" (never on a physical card).
  EXIT_TAGS    -- every tag that exits a running game (GAME_TAGS | {"stop"}).
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
}

CONTROL_TAGS = {"start", "stop"}

# ESP-NOW only, never printed on a card.
HIDDEN_TAGS = {"finddevice"}

EXIT_TAGS = GAME_TAGS | {"stop"}


def exit_tags_excluding(game_tag):
    """EXIT_TAGS copy without this game's own entry tag.

    The entry tag is often still under the wand when play() starts;
    excluding it avoids an immediate exit on the first NFC poll. Never
    mutates EXIT_TAGS.
    """
    tags = set(EXIT_TAGS)
    tags.discard(game_tag)
    return tags
