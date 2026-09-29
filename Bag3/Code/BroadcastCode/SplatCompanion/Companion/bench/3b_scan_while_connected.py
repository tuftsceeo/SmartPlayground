"""
3b_scan_while_connected.py -- does a BLE scan drop a connected Splat?
=====================================================================
Run on the hub: mpremote connect $HUB resume run bench/3b_scan_while_connected.py
Needs on the hub: the stage-3 files (bench/README.md). One Splat on.

Connects one Splat, holds the link HOLD_S with no scan, then HOLD_S with a
scan running at SCAN (interval_us, window_us), and counts link drops in
each phase. splat_hub.py is built on the answer being "yes, it drops".
"""

import time
import ubluetooth

ubluetooth.BLE().active(True)

from splat_hub import SplatHub
from splat_api import SplatGroup

HOLD_S = 10
SCAN = (100000, 20000)   # 20% duty, the hub's earlier shared-scan setting


def phase(label, splat, link, seconds):
    drops0 = link.drops
    end = time.ticks_add(time.ticks_ms(), seconds * 1000)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        splat.poll()
        time.sleep_ms(1)
    n = link.drops - drops0
    print("%s: %d drop(s) in %d s, state %s" % (label, n, seconds, link.state_name()))
    return n


hub = SplatHub(1)
splat = SplatGroup(hub)
link = hub.links[0]
end = time.ticks_add(time.ticks_ms(), 60000)
while not link.ready and time.ticks_diff(end, time.ticks_ms()) > 0:
    splat.poll()
    time.sleep_ms(1)
if not link.ready:
    print("FAIL: no Splat ready in 60 s (%s)" % link.state_name())
    raise SystemExit
print("connected to %s" % link.mac_address)

quiet = phase("no scan", splat, link, HOLD_S)
link._start_scan(0, SCAN[0], SCAN[1])
print("scan started %s" % (SCAN,))
scanning = phase("with scan", splat, link, HOLD_S)
link._stop_scan()
print("RESULT: no-scan drops %d, with-scan drops %d -> %s"
      % (quiet, scanning, "scan drops the link" if scanning > quiet
         else "scan did not drop the link"))
hub.close_all()
