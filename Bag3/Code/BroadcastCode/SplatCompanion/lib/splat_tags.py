"""Splat Companion game / control tag names.

Shaped like MockWand/lib/game_tags.py, but its own table -- deliberately
not shared, per AGENTS.md ("Shared libraries are duplicated by hand").

  GAME_TAGS    -- names of game tags only (no "stop", no "getcode").
  CONTROL_TAGS -- "stop" and "getcode" (this device has no NFC "start" mode:
                  a tapped game tag launches directly, like IconDisplay).
  EXIT_TAGS    -- every tag that exits a running game (GAME_TAGS | {"stop"}).
  exit_tags_excluding(tag) -- EXIT_TAGS without one game's own entry tag.

main.py checks GAME_TAGS against its own GAME_MODULES at boot and prints a
mismatch: nothing else keeps the two in step.
"""

GAME_TAGS = {
    "splatwhack",
}

CONTROL_TAGS = {"stop", "getcode"}

EXIT_TAGS = GAME_TAGS | {"stop"}


def exit_tags_excluding(game_tag):
    """EXIT_TAGS copy without this game's own entry tag.

    The entry tag is often still under the reader when play() starts;
    excluding it avoids an immediate exit on the first NFC poll. Never
    mutates EXIT_TAGS.
    """
    tags = set(EXIT_TAGS)
    tags.discard(game_tag)
    return tags
