"""
Battery Display — Show battery level on LEDs
===============================================
Reads MAX17048 and displays state of charge as an LED bar.

Usage:
    from battery import show_battery

    show_battery(batt, leds, buzzer)
"""

import time


def show_battery(batt, leds, buzzer):
    """
    Read battery and display SoC as an LED bar for 2 seconds.

    Args:
        batt: MAX17048 instance, or None if unavailable
        leds: Leds instance
        buzzer: Buzzer instance
    """
    if batt is None:
        print("  [WARN] Battery sensor not available")
        buzzer.warn(); return

    try:
        voltage, soc = batt.read_all()
    except Exception as e:
        print("  [WARN] Battery read failed: %s" % str(e))
        buzzer.warn(); return

    r, g, b, lit = leds.show_battery_level(soc)

    print("  Battery: %.1f%%  (%.2fV)" % (soc, voltage))
    buzzer.beep(600, 60)
    time.sleep_ms(2000)
    leds.fade_out_battery(r, g, b, lit)