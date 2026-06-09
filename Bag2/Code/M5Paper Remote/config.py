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
FOOTER_H = 96
BATTERY_BTN_H = 48
STOP_BTN_H = 110

# DejaVu point sizes (see ui._set_font); must be keys in _DEJAVU_NAMES.
FONT_TITLE = 12
FONT_STATUS = 12
FONT_GAME = 18
FONT_STOP = 24
FONT_FOOTER = 40
FONT_BATTERY = 12

BORDER_W = 3

DEBOUNCE_MS = 300
GHOST_REFRESH_EVERY = 8
PRESS_FLASH_MS = 150

COMMANDS = [
    {"id": "jumpin", "label": "Jump In"},
    {"id": "gestures", "label": "Gestures"},
    {"id": "freezedance", "label": "Freeze Dance"},
    {"id": "cooking", "label": "Cooking"},
    {"id": "melody", "label": "Melody"},
    {"id": "simpleicecream", "label": "Ice Cream"},
    {"id": "rainbow", "label": "Rainbow"},
    {"id": "sound", "label": "Bell Choir"},
    {"id": "colorquest", "label": "Color Quest"},
    {"id": "shake", "label": "Shake Fill"},
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
