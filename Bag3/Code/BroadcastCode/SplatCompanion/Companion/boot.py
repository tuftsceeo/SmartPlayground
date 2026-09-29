"""
boot.py -- runs before main.py.

Deliberately does almost nothing, like IconDisplay's boot.py: this device
brings BLE up before anything else allocates (main.py's memory-order rule,
see AGENTS.md), and a boot-time NeoPixel write here would allocate ahead of
that. The status LEDs are built in main.py, after BLE and the modem are up.

/lib is already on sys.path on this port.
"""

try:
    import memprobe
    memprobe.probe("boot")
except Exception as e:
    print("  [BENCH] memprobe unavailable at boot:", e)
