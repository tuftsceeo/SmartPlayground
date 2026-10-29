"""
boot.py -- runs before main.py.

Selects the onboard antenna, then does almost nothing else, like
IconDisplay's boot.py: this device brings BLE up before anything else
allocates (main.py's memory-order rule, see AGENTS.md), and a boot-time
NeoPixel write here would allocate ahead of that. The status LEDs are built
in main.py, after BLE and the modem are up.

Antenna: XIAO C6 GPIO3 low enables the RF switch and GPIO14 low selects the
onboard antenna. This hub board has no u.FL antenna fitted. Left undriven,
GPIO3 reads high. code_puller.py drives the same pins for a WiFi pull.

/lib is already on sys.path on this port.
"""

import time
from machine import Pin

Pin(3, Pin.OUT).value(0)
time.sleep_ms(100)
Pin(14, Pin.OUT).value(0)

try:
    import memprobe
    memprobe.probe("boot")
except Exception as e:
    print("  [BENCH] memprobe unavailable at boot:", e)
