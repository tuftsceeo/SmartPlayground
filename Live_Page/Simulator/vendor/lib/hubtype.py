"""
hubtype.py — Device type detection and per-device configuration
================================================================
Reads /hubtype.txt to determine what kind of device this is,
then provides hardware constants and feature flags.

/hubtype.txt contains a single line: wand, splat_companion,
programming_station, or score_board.

Usage:
    from hubtype import HUB_TYPE, HUB_CONFIG
"""

_CONFIGS = {
    "wand": {
        "num_leds":       25,
        "led_pin":        20,
        "has_nfc":        True,
        "has_accel":      True,
        "has_battery":    True,
        "has_buzzer":     True,
        "has_motor":      True,
        "has_button":     True,
        "has_ble":        True,
        "uses_ble":       False,  # not actively connecting to Splats (yet)
        "buzzer_pin":     19,
        "motor_pin":      21,
        "button_pin":     0,
        "accel_int1_pin": 1,
        "i2c_sda":        22,
        "i2c_scl":        23,
        "i2c_freq":       100_000,
    },
    "splat_companion": {
        "num_leds":       3,
        "led_pin":        20,
        "has_nfc":        False,
        "has_accel":      False,
        "has_battery":    True,
        "has_buzzer":     False,
        "has_motor":      False,
        "has_button":     False,
        "has_ble":        True,
        "uses_ble":       True,  # actively connects to Splat
        "i2c_sda":        22,
        "i2c_scl":        23,
        "i2c_freq":       400_000,
    },
    "programming_station": {
        "num_leds":       18,
        "led_pin":        21,
        "has_nfc":        True,
        "has_accel":      False,
        "has_battery":    False,
        "has_buzzer":     False,
        "has_motor":      False,
        "has_button":     True,
        "has_ble":        True,
        "uses_ble":       False,
        "button_pin":     0,
        "mux_rst_pin":    1,
        "pn532_rst_pin":  2,
        "i2c_sda":        22,
        "i2c_scl":        23,
        "i2c_freq":       100_000,
    },
    "score_board": {
        "num_leds":       40,
        "led_pin":        0,
        "has_nfc":        False,
        "has_accel":      False,
        "has_battery":    False,
        "has_buzzer":     False,
        "has_motor":      False,
        "has_button":     False,
        "has_ble":        True,
        "uses_ble":       False,
    },
}

_DEFAULT_TYPE = "wand"


def _read_hubtype():
    try:
        with open("hubtype.txt", "r") as f:
            raw = f.read().strip().lower()
        if raw in _CONFIGS:
            return raw
        print("[hubtype] Unknown '%s', defaulting to '%s'" % (raw, _DEFAULT_TYPE))
        return _DEFAULT_TYPE
    except OSError:
        print("[hubtype] No hubtype.txt, defaulting to '%s'" % _DEFAULT_TYPE)
        return _DEFAULT_TYPE


HUB_TYPE = _read_hubtype()
HUB_CONFIG = _CONFIGS[HUB_TYPE]
print("[hubtype] %s (%d LEDs)" % (HUB_TYPE, HUB_CONFIG["num_leds"]))