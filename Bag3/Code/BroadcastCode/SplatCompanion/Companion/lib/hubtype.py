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
        "num_leds":       12,       # NeoPixel ring on GPIO20 (D9)
        "led_pin":        20,
        "has_nfc":        True,
        "nfc_addr":       0x24,     # PN532 I2C address, same wiring as the wand
        "has_accel":      False,
        "has_battery":    True,
        "has_buzzer":     False,
        "has_motor":      False,
        "has_button":     False,
        "has_ble":        True,
        "uses_ble":       True,     # actively connects to Splats
        # Splats this companion connects to at once, 1 to
        # splat_hub.BLE_MAX_CONNECTIONS (4 on stock MicroPython firmware).
        # Run on hardware with 1 and 2; see README "Multiple Splats".
        "max_splats":     1,
        # None: take the first max_splats Splats found by BLE name. A list
        # of MAC strings, e.g. ["AB:42:00:00:7E:B6", ...], pins specific
        # Splats and their order (unit 0, 1, ...); its length is the count.
        "splat_macs":     None,
        "i2c_sda":        22,
        "i2c_scl":        23,
        # Shared with the PN532 (100 kHz is the wand's rate; 400 kHz was the
        # bridge-only config's, back when nothing else was on this bus).
        "i2c_freq":       100_000,
        # UART1 to the ESPNowModem board (XIAO D6/D7), crossed: this TX
        # to its RX. main.py sets these on espnow_manager before init().
        "modem_uart_tx":  16,
        "modem_uart_rx":  17,
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
