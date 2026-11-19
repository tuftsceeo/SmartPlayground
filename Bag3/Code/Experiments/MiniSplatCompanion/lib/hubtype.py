"""
hubtype.py -- Mini Splat Companion pin map (not a copy of the Wand's)
=====================================================================
Same module API as Wand Module/lib/hubtype.py (HUB_TYPE, HUB_CONFIG) so the
copied libs (leds.py, espnow_manager.py ...) import it unchanged, but only
one type exists here: splat_mini, one XIAO ESP32-C6 with 3 NeoPixels on
GPIO20 and a MAX17048 fuel gauge on I2C 22/23 (as on the Bag2 board).
The battery wiring is the Bag2 board's; it was not confirmed against this
build (README "Assumed, not confirmed").
"""

_CONFIGS = {
    "splat_mini": {
        "num_leds":       3,
        "led_pin":        20,
        "has_nfc":        False,
        "has_accel":      False,
        "has_battery":    True,
        "has_buzzer":     False,
        "has_motor":      False,
        "has_button":     False,
        "has_ble":        True,
        "uses_ble":       True,
        "i2c_sda":        22,
        "i2c_scl":        23,
        "i2c_freq":       400_000,
    },
}

_DEFAULT_TYPE = "splat_mini"


def _read_hubtype():
    try:
        with open("hubtype.txt", "r") as f:
            raw = f.read().strip().lower()
        if raw in _CONFIGS:
            return raw
    except OSError:
        pass
    return _DEFAULT_TYPE


HUB_TYPE = _read_hubtype()
HUB_CONFIG = _CONFIGS[HUB_TYPE]
