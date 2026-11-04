"""
Battery Display — Show battery level on LEDs
===============================================
Works on any device with any LED count.

Usage:
    from battery import show_battery
    show_battery(batt, leds, buzzer)   # buzzer can be None
"""

import time


def show_battery(batt, leds, buzzer):
    if batt is None:
        print("  [WARN] Battery sensor not available")
        if buzzer:
            buzzer.warn()
        return

    try:
        voltage = batt.voltage
        soc = batt.soc
    except Exception as e:
        print("  [WARN] Battery read failed: %s" % str(e))
        if buzzer:
            buzzer.warn()
        return

    r, g, b, lit = leds.show_battery_level(soc)
    print("  Battery: %.1f%%  (%.2fV)  [%d/%d LEDs]" % (soc, voltage, lit, leds.num))
    if buzzer:
        buzzer.beep(600, 60)
    time.sleep_ms(2500)
    leds.fade_out_battery(r, g, b, lit)