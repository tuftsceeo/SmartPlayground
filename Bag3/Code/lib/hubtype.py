"""
hubtype.py — Device type detection and per-device configuration
================================================================
Reads /hubtype.txt to determine what kind of device this is,
then provides hardware constants and feature flags.

/hubtype.txt contains a single line: wand, splat_companion,
programming_station, or score_board.

Usage:
    from hubtype import HUB_TYPE, HUB_CONFIG

Bag3 differences vs Bag2 (wand):
    • LED matrix is 6×10 (60 LEDs) instead of 5×5 (25 LEDs).
    • NFC reader is an M5Stack RFID2 / WS1850S at I2C 0x28
      (the PN532 was at 0x24). The lib/pn532.py shim remaps the old
      0x24 address to 0x28 automatically, so nfc_addr is informational.
    • A discrete power-status LED is wired to GPIO 2 (power_led_pin).
"""

_CONFIGS = {
    "wand": {
        "num_leds":       60,       # 6×10 matrix on Bag3 (was 25 on Bag2)
        "led_pin":        20,
        "matrix_cols":    6,        # 6 columns laid left→right
        "matrix_rows":    10,       # 10 rows; row-major, index = row*6 + col
        "has_nfc":        True,
        "nfc_addr":       0x28,     # WS1850S default (PN532 was 0x24)
        "has_accel":      True,
        "has_battery":    True,
        "has_buzzer":     True,
        "has_motor":      True,
        "has_button":     True,
        "has_ble":        True,
        "has_power_led":  True,     # Bag3 only: discrete power-status LED
        "power_led_pin":  2,
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
