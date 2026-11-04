"""Curated wand commands and e-ink layout constants for M5Paper remote."""

import json

from game_tags import GAME_TAGS

try:
    import os
except ImportError:
    os = None

# Set to 1-11 only if wands do not respond on the default channel.
ESPNOW_CHANNEL = None

SETTINGS_PATH = "/flash/settings.json"

SCREEN_W = 540
SCREEN_H = 960

MARGIN = 12
GAP = 8
TOP_BAR_H = 52
FOOTER_H = 96
BATTERY_BTN_H = 64
STOP_BTN_H = 110

SETTINGS_SAVE_H = 72
SETTINGS_MAC_H = 28
GEAR_HIT = 44

GEAR_PNG = "/flash/assets/gear.png"
BATTERY_PNG = "/flash/assets/battery.png"
BOLT_PNG = "/flash/assets/bolt.png"
# Signal-strength icons, ascending bars. Index = level 0..3 (Poor..Strong).
SIGNAL_PNGS = (
    "/flash/assets/signal-0.png",
    "/flash/assets/signal-1.png",
    "/flash/assets/signal-2.png",
    "/flash/assets/signal-3.png",
)
SIGNAL_WORDS = ("Poor", "Fair", "Good", "Strong")

GEAR_W = 36
GEAR_H = 36
BATT_W = 46
BATT_H = 22
BOLT_W = 12
BOLT_H = 16
BATT_NUB_W = 4
BATT_FILL_INSET = 2
# Battery is slow-moving; poll every 5 min (awake and asleep) to save power and
# avoid needless e-ink refreshes. update_battery() only redraws on bucket change.
BATT_POLL_MS = 300000
# At/below this SOC the sleep screen switches to a low-battery warning.
BATT_CRIT_SOC = 10

# ── Sleep / wake ──────────────────────────────────────────────────────────
# After this long with no touch or side-button activity, show the sleep screen
# and power down the ESP-NOW radio (the dominant battery draw). E-ink holds the
# sleep image for free.
INACTIVITY_SLEEP_MS = 120000
# Poll cadence of the low-power sleep loop (watches side button + touch).
SLEEP_TICK_MS = 150
# Opt-in true light sleep between ticks. Leave False until verified that it does
# not disturb the touch panel / e-ink on this UIFlow2 build.
USE_LIGHTSLEEP = False

# M5Paper side rocker GPIOs (input-only; board has external pull-ups -> 0 = pressed).
SIDE_BTN_UP = 37
SIDE_BTN_PRESS = 38
SIDE_BTN_DOWN = 39

# Signal icon geometry (must match assets/_generate_icons.py::signal()).
SIGNAL_W = 40
SIGNAL_H = 34
SIGNAL_BARS = 4
SIGNAL_BAR_W = 7
SIGNAL_BAR_GAP = 4
SIGNAL_BAR_MIN_H = 10
SIGNAL_BAR_STEP = 8

# Device-status overlay row geometry.
STATUS_ROW_H = 60
STATUS_ROW_GAP = 6
# Up/Down pagination buttons in the status header (square, in the top bar).
STATUS_NAV_W = 64

# DejaVu point sizes (see ui._set_font); must be keys in _DEJAVU_NAMES.
FONT_GAME = 24
FONT_STOP = 40
FONT_FOOTER = 24
FONT_BATTERY = 24
FONT_SETTINGS = 18
FONT_SETTINGS_SMALL = 12
FONT_STATUS = 24

BORDER_W = 3

DEBOUNCE_MS = 300
PRESS_FLASH_MS = 150

# On-device REPL: endWrite() alone flushes batched draws; set True only if show() required.
LCD_SHOW_AFTER_END_WRITE = False

ALL_GAMES = [
    {"id": "colorquest", "label": "Color Quest"},
    {"id": "freezedance", "label": "Freeze Dance"},
    {"id": "jumpin", "label": "Jump In"},
    {"id": "cooking", "label": "Cooking"},
    {"id": "melody", "label": "Melody"},
    {"id": "shake", "label": "Shake Fill"},
    {"id": "shakerainbow", "label": "Shake Rainbow"},
    {"id": "rainbow", "label": "Rainbow"},
    {"id": "jump", "label": "Jump Counter"},
    {"id": "sound", "label": "Bell Choir"},
    {"id": "nfcsound", "label": "NFC Bell Choir"},
    {"id": "simpleicecream", "label": "Ice Cream"},
    {"id": "multiicecream", "label": "Multi Ice Cream"},
    {"id": "gestures", "label": "Gestures"},
]

DEFAULT_ENABLED_IDS = [
    "jumpin",
    "gestures",
    "freezedance",
    "cooking",
    "melody",
    "simpleicecream",
    "rainbow",
    "sound",
    "colorquest",
    "shake",
]

CONTROLS = [
    {"id": "stop", "label": "STOP"},
    {"id": "status", "label": "Status"},
]

WHITE = 0xFFFFFF
BLACK = 0x000000


def build_commands(enabled_ids):
    """Build command dicts for enabled games in catalog order."""
    enabled = set(enabled_ids)
    return [
        {"id": g["id"], "label": g["label"]}
        for g in ALL_GAMES
        if g["id"] in enabled
    ]


def _sanitize_enabled_ids(ids):
    """Keep only valid game ids; return list preserving order."""
    if not ids:
        return list(DEFAULT_ENABLED_IDS)
    clean = []
    seen = set()
    for gid in ids:
        if gid in GAME_TAGS and gid not in seen:
            clean.append(gid)
            seen.add(gid)
    if not clean:
        return list(DEFAULT_ENABLED_IDS)
    return clean


def load_enabled_ids():
    """Load enabled game ids from flash; fall back to default."""
    try:
        with open(SETTINGS_PATH, "r") as f:
            data = json.load(f)
        if isinstance(data, list):
            return _sanitize_enabled_ids(data)
    except Exception:
        pass
    return list(DEFAULT_ENABLED_IDS)


def save_enabled_ids(ids):
    """Persist enabled game ids to flash."""
    clean = _sanitize_enabled_ids(ids)
    try:
        with open(SETTINGS_PATH, "w") as f:
            json.dump(clean, f)
    except Exception as e:
        print("  settings save err: %s" % str(e))


def validate_config():
    """Validate catalog and defaults against GAME_TAGS."""
    bad = []
    for g in ALL_GAMES:
        if g["id"] not in GAME_TAGS:
            bad.append(g["id"])
    for gid in DEFAULT_ENABLED_IDS:
        if gid not in GAME_TAGS:
            bad.append(gid)
    if bad:
        raise ValueError("Unknown game ids in config: %s" % ", ".join(bad))
