"""
3_ble_splat.py -- bench stage 3: BLE to the Splat(s)
=====================================================
Run on the hub: mpremote connect $HUB resume run bench/3_ble_splat.py
Needs on the hub: /hubtype.txt, /lib/hubtype.py, /splat_link.py,
/splat_hub.py, /splat_api.py, /lib/ble_splat.py. Switch the Splat(s) on.

Connects to max_splats Splats (hubtype.py; splat_macs pins them). PASS
when all are ready within CONNECT_S. Then, for PRESS_S, each press
flashes that Splat green and prints its index; the user presses each one.
"""

import time
import ubluetooth
from hubtype import HUB_CONFIG

ubluetooth.BLE().active(True)

from splat_hub import SplatHub
from splat_api import SplatGroup

CONNECT_S = 60
PRESS_S = 30
FLASH_MS = 300

hub = SplatHub(HUB_CONFIG.get("max_splats", 1), HUB_CONFIG.get("splat_macs"))
splat = SplatGroup(hub)
print("bench 3: waiting for %d Splat(s)" % splat.count)

end = time.ticks_add(time.ticks_ms(), CONNECT_S * 1000)
while splat.connected_count < splat.count and time.ticks_diff(end, time.ticks_ms()) > 0:
    splat.poll()
    time.sleep_ms(1)
for i, link in enumerate(hub.links):
    print("  unit %d: %s %s" % (i, link.state_name(), link.mac_address))
if splat.connected_count < splat.count:
    print("FAIL: %d/%d Splats ready after %d s"
          % (splat.connected_count, splat.count, CONNECT_S))
    raise SystemExit
print("PASS: %d Splat(s) ready -- press each one now (%d s)" % (splat.count, PRESS_S))

end = time.ticks_add(time.ticks_ms(), PRESS_S * 1000)
off_at = None
presses = [0] * splat.count
while time.ticks_diff(end, time.ticks_ms()) > 0:
    ev = splat.poll()
    if ev == "press":
        i = splat.last_index
        presses[i] += 1
        print("press on unit %d" % i)
        splat.unit(i).color("turngreen")
        off_at = time.ticks_add(time.ticks_ms(), FLASH_MS)
    if off_at is not None and time.ticks_diff(time.ticks_ms(), off_at) >= 0:
        splat.off()
        off_at = None
    time.sleep_ms(1)
splat.off()
print("DONE: presses per unit %s, write failures %d" % (presses, splat.write_failures))
