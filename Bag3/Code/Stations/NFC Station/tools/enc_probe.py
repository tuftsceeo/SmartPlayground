"""enc_probe.py -- does the Dial's encoder lose detents when the loop stalls?

No LVGL, no station. Two 15 s phases; in each, turn the knob exactly 5
detents forward. Prints every value change with the time since the phase
started, and the end value.

  phase fast   poll every 1 ms (M5.update + read)
  phase stall  same, but sleep 300 ms per loop, like a slow redraw

If the stall phase ends with a smaller value than the fast phase, the
Rotary is decoded in software during M5.update() and stalls drop steps.
The counts per detent also show whether one detent is one count.

    mpremote connect <port> resume run tools/enc_probe.py
"""

import time

import M5
from hardware import Rotary

M5.begin()
rot = Rotary()
print("Rotary:", Rotary, [n for n in dir(rot) if not n.startswith("_")])


def phase(name, stall_ms, seconds=15):
    rot.reset_rotary_value()
    last = rot.get_rotary_value()
    start = time.ticks_ms()
    print("== phase %s (stall %d ms)" % (name, stall_ms))
    while time.ticks_diff(time.ticks_ms(), start) < seconds * 1000:
        M5.update()
        v = rot.get_rotary_value()
        if v != last:
            print("%6d ms  value %d  (%+d)" % (time.ticks_diff(time.ticks_ms(), start), v, v - last))
            last = v
        time.sleep_ms(stall_ms if stall_ms else 1)
    print("== %s end value %d" % (name, rot.get_rotary_value()))


phase("fast", 0)
time.sleep_ms(2000)
phase("stall", 300)
