"""
2_leds.py -- bench stage 2: the 12-LED NeoPixel ring
=====================================================
Run on the hub: mpremote connect $HUB resume run bench/2_leds.py
Needs on the hub: /hubtype.txt, /lib/hubtype.py, /status_leds.py.

Walks one white pixel around the ring (pixel 0 first), then shows the
idle status colors for 2 s each: red (modem down), blue (BLE waiting),
cyan breathing (ready). Visual check only: report what the ring did.
"""

import time
from hubtype import HUB_CONFIG
from status_leds import StatusLeds

leds = StatusLeds(HUB_CONFIG["led_pin"], HUB_CONFIG["num_leds"])
print("bench 2: pin %d, %d LEDs" % (HUB_CONFIG["led_pin"], leds.n))

for i in range(leds.n):
    colors = [(0, 0, 0)] * leds.n
    colors[i] = (20, 20, 20)
    leds.show_each(colors)
    print("pixel", i)
    time.sleep_ms(250)

for name, color in (("red", (15, 0, 0)), ("blue", (0, 0, 15))):
    print("solid", name)
    leds.fill(color)
    time.sleep_ms(2000)

print("cyan breathing")
end = time.ticks_add(time.ticks_ms(), 4000)
while time.ticks_diff(end, time.ticks_ms()) > 0:
    leds.show((0, 12, 12), True, time.ticks_ms())
    time.sleep_ms(20)
leds.off()
print("DONE: report whether pixels 0..%d lit in order and the colors matched"
      % (leds.n - 1))
