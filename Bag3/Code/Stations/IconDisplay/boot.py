"""
boot.py -- runs before main.py.

Deliberately does almost nothing. The wand's boot.py opens a NeoPixel here
for a power-on pixel, but this device's panel is 256 pixels: constructing it
would take a NeoPixel buffer, the offset table, the LUT and a frame buffer
out of the IDF heap before main.py has claimed the radio, which is exactly
the allocation order that caused "WiFi Out of Memory" on the wand. The panel
is built in main.py, after enow.init().

/lib is already on sys.path on this port.
"""

try:
    import memprobe
    memprobe.probe("boot")
except Exception as e:
    print("  [BENCH] memprobe unavailable at boot:", e)
