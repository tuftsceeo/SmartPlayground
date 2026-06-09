"""Curated wand commands and e-ink layout constants for M5Paper remote."""

from game_tags import GAME_TAGS

# Set to 1-11 only if wands do not respond on the default channel.
ESPNOW_CHANNEL = None

SCREEN_W = 540
SCREEN_H = 960

MARGIN = 12
GAP = 8
TITLE_H = 48
STATUS_H = 32
GAME_BTN_H = 108
CONTROL_BTN_H = 72
STOP_BTN_H = 100

DEBOUNCE_MS = 300
GHOST_REFRESH_EVERY = 12

COMMANDS = [
    {"id": "colorquest", "label": "Color Quest"},
    {"id": "freezedance", "label": "Freeze Dance"},
    {"id": "rainbow", "label": "Rainbow"},
    {"id": "shake", "label": "Shake Fill"},
    {"id": "sound", "label": "Bell Choir"},
    {"id": "jump", "label": "Jump Counter"},
]

CONTROLS = [
    {"id": "stop", "label": "STOP"},
    {"id": "battery", "label": "Battery"},
]

WHITE = 0xFFFFFF
BLACK = 0x000000


def validate_config():
    """Ensure every game command id is in GAME_TAGS. Raises on mismatch."""
    bad = []
    for cmd in COMMANDS:
        if cmd["id"] not in GAME_TAGS:
            bad.append(cmd["id"])
    if bad:
        raise ValueError("Unknown game ids in COMMANDS: %s" % ", ".join(bad))
