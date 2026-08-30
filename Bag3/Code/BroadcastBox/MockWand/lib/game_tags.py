"""Wand game / control tag names — compatibility shim.

The tag-name sets now live in opcodes.py alongside the on-card byte
encoding (they must stay in lockstep with the opcode table). This module
re-exports them so existing `from game_tags import ...` lines keep working.

  GAME_TAGS    — names of game tags only (no "stop", no "start").
  CONTROL_TAGS — programming-mode controls ("start", "stop").
  HIDDEN_TAGS  — ESP-NOW-only "games" (never on a physical card).
  EXIT_TAGS    — every tag that exits a running game (GAME_TAGS | {"stop"}).
  exit_tags_excluding(tag) — EXIT_TAGS without one game's own entry tag.
"""

from opcodes import (
    GAME_TAGS,
    CONTROL_TAGS,
    HIDDEN_TAGS,
    EXIT_TAGS,
    exit_tags_excluding,
)
