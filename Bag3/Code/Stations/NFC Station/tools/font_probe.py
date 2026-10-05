"""font_probe.py -- list the built-in Montserrat sizes on this firmware.

    mpremote connect <port> resume run tools/font_probe.py
"""

import lvgl as lv

found = [s for s in range(8, 50, 2) if hasattr(lv, "font_montserrat_%d" % s)]
print("built-in montserrat sizes:", found)
for want in (28, 40, 48):
    print("%d px:" % want, "built in" if want in found else "MISSING")
