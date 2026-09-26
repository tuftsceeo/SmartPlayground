"""
hubtype.py — Device type detection and per-device configuration
================================================================
PEER: this tree's own copy, diverged on purpose from MockWand's,
Bag3/Code/lib's and IconDisplay's -- see the "splat_companion" entry
below. The other three still carry the earlier, bridge-only entry
(has_nfc False, uses_ble True but no reader pins). Flagged in
docs/KNOWN_ISSUES.md rather than reconciled: this device tree is the one
place that config now has to be right.

Reads /hubtype.txt to determine what kind of device this is,
then provides hardware constants and feature flags.

/hubtype.txt contains a single line: wand, splat_companion,
programming_station, or score_board.

Usage:
    from hubtype import HUB_TYPE, HUB_CONFIG
"""

_CONFIGS = {
    "splat_companion": {
        "num_leds":       3,
        "led_pin":        20,
        "has_nfc":        True,
        "nfc_addr":       0x24,     # PN532 I2C address, same wiring as the wand
        "has_accel":      False,
        "has_battery":    True,
        "has_buzzer":     False,
        "has_motor":      False,
        "has_button":     False,
        "has_ble":        True,
        "uses_ble":       True,     # actively connects to a Splat
        "i2c_sda":        22,
        "i2c_scl":        23,
        # Shared with the PN532 (100 kHz is the wand's rate; 400 kHz was the
        # bridge-only config's, back when nothing else was on this bus).
        "i2c_freq":       100_000,
    },
}

_DEFAULT_TYPE = "splat_companion"


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
