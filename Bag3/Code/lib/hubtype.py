"""
hubtype.py -- device identity and per-hubtype hardware description.

Reads hubtype.txt from the filesystem root and exposes:

    HUB_TYPE    the hubtype name
    HUB_CONFIG  pins and geometry for this hubtype
    CAPS        capability names this hubtype provides

CAPS is what the rest of the firmware branches on. devices.build() uses it to
decide which drivers to construct, the capability dispatcher uses it to decide
which ESP-NOW "cap" messages to answer, and ChatBroadcast uses it to decide
which knowledge sections a role file needs.

A missing or unrecognised hubtype.txt raises. A device that does not know what
it is cannot be trusted to drive its pins.
"""

_CONFIGS = {
    "wand": {
        "caps": ("matrix5", "buzzer", "accel", "button", "nfc", "motor", "battery"),
        "idle_ms":        200,      # Bag2 idle pace; NFC sleeps after 30 s
        "idle_poll_ms":   0,
        "game_ms":        20,
        "num_leds":       25,
        "led_pin":        20,
        "matrix_cols":    5,
        "matrix_rows":    5,
        "nfc_addr":       0x24,
        "power_led_pin":  2,
        "buzzer_pin":     19,
        "motor_pin":      21,
        "button_pin":     0,
        "accel_int1_pin": 1,
        "i2c_sda":        22,
        "i2c_scl":        23,
        "i2c_freq":       100_000,
    },
    "code_station": {
        "caps": ("slots4", "slotleds", "button", "nfc"),
        "idle_ms":        10,       # Bag2 programming station: poll() + sleep_ms(10)
        "idle_poll_ms":   0,
        "game_ms":        20,
        "num_leds":       18,
        "led_pin":        21,
        "slots":          4,
        "slot_leds":      ((16, 17), (13, 14), (10, 11), (7, 8)),  # slot 0..3
        "nfc_addr":       0x24,
        "mux_addr":       0x70,
        "button_pin":     0,
        "mux_rst_pin":    1,
        "pn532_rst_pin":  2,
        "i2c_sda":        22,
        "i2c_scl":        23,
        "i2c_freq":       100_000,
    },
    "score_station": {
        "caps": ("bars4", "nfc"),
        "idle_ms":        0,        # Bag2 slide score: the blocking poll is the pacing
        "idle_poll_ms":   100,
        "game_ms":        20,
        "num_leds":       40,
        "led_pin":        0,
        "bars":           4,
        "bar_height":     10,
        "serpentine":     True,
        # NFC pins provisional until the reader is fitted.
        "nfc_addr":       0x24,
        "i2c_sda":        22,
        "i2c_scl":        23,
        "i2c_freq":       100_000,
    },
    "icon_station": {
        "caps": ("icon16", "nfc"),
        "idle_ms":        0,
        "idle_poll_ms":   100,
        "game_ms":        20,
        "num_leds":       256,
        "led_pin":        0,
        "matrix_cols":    16,
        "matrix_rows":    16,
        "max_intensity":  0.50,
        # NFC pins provisional until the reader is fitted.
        "nfc_addr":       0x24,
        "i2c_sda":        22,
        "i2c_scl":        23,
        "i2c_freq":       100_000,
    },
    "dial_station": {
        # M5Dial under UIFlow2. Pins belong to the M5 board support, not here.
        "caps": ("audio", "encoder", "screen"),
        "idle_ms":        10,
        "idle_poll_ms":   0,
        "game_ms":        20,
        "audio_uart":     1,
        "audio_port":     (1, 2),
        "max_volume":     30,
    },
}

PATH = "hubtype.txt"


class UnknownHubType(Exception):
    """hubtype.txt is missing, empty, or names a hubtype with no config."""


def _read():
    try:
        with open(PATH, "r") as f:
            raw = f.read().strip().lower()
    except OSError:
        raise UnknownHubType(
            "no %s -- write one containing one of: %s"
            % (PATH, ", ".join(sorted(_CONFIGS))))
    if raw not in _CONFIGS:
        raise UnknownHubType(
            "%s says %r -- expected one of: %s"
            % (PATH, raw, ", ".join(sorted(_CONFIGS))))
    return raw


HUB_TYPE = _read()
HUB_CONFIG = _CONFIGS[HUB_TYPE]
CAPS = frozenset(HUB_CONFIG["caps"])


def has(cap):
    """True if this hubtype provides `cap`."""
    return cap in CAPS


def hubtypes_with(cap):
    """Every hubtype name providing `cap`. Used by tooling, not on-device."""
    return sorted(n for n, c in _CONFIGS.items() if cap in c["caps"])


print("[hubtype] %s %s" % (HUB_TYPE, sorted(CAPS)))
