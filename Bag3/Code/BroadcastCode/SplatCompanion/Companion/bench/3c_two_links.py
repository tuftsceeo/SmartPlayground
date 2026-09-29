"""
3c_two_links.py -- why does a second Splat connection drop the first?
=====================================================================
Run on the hub: mpremote connect $HUB resume run bench/3c_two_links.py
Needs on the hub: the stage-3 files (bench/README.md). BOTH Splats on,
not connected to a phone or web app. /main.py moved aside.

For each entry in VARIANTS (connection interval passed to gap_connect),
builds SplatHub(2), runs RUN_S, and logs with times: every
connect/disconnect event with its handle and address, and every
connection-parameter update (_IRQ_CONNECTION_UPDATE: interval, latency,
supervision timeout, status). Ends each variant with one SUMMARY line.
"""

import time
import ubluetooth

ubluetooth.BLE().active(True)

import splat_link
from splat_hub import SplatHub
from splat_api import SplatGroup

RUN_S = 12
VARIANTS = (None, (50000, 100000), (100000, 200000))   # interval_us (min, max)

_T0 = time.ticks_ms()


def _t():
    return time.ticks_diff(time.ticks_ms(), _T0) / 1000


def _addr(a):
    return ':'.join(['%02X' % b for b in a])


def run(variant):
    splat_link.CONN_INTERVAL_US = variant
    hub = SplatHub(2)
    route = hub._irq
    updates = []

    def spy(event, data):
        if event == 7:
            print("[%6.2f] IRQ connect    handle=%d %s" % (_t(), data[0], _addr(data[2])))
        elif event == 8:
            print("[%6.2f] IRQ disconnect handle=%d %s" % (_t(), data[0], _addr(data[2])))
        elif event == 27:
            h, itvl, lat, sup, st = data
            updates.append((h, itvl, lat, sup, st))
            print("[%6.2f] IRQ conn update handle=%d interval=%d (x1.25 ms) latency=%d "
                  "supervision=%d (x10 ms) status=%d" % (_t(), h, itvl, lat, sup, st))
        route(event, data)

    hub._ble.irq(spy)
    splat = SplatGroup(hub)
    print("[%6.2f] variant interval_us=%s" % (_t(), variant))
    both_at = None
    end = time.ticks_add(time.ticks_ms(), RUN_S * 1000)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        splat.poll()
        if both_at is None and splat.connected_count == 2:
            both_at = _t()
            print("[%6.2f] BOTH READY" % both_at)
        time.sleep_ms(1)
    held = splat.connected_count
    print("SUMMARY interval_us=%s: connects=%s drops=%s both_ready_at=%s "
          "ready_at_end=%d updates=%d"
          % (variant, [l.connects for l in hub.links], [l.drops for l in hub.links],
             both_at, held, len(updates)))
    for link in hub.links:
        link.scan_gate = lambda l: False
        link.close()
    t = time.ticks_add(time.ticks_ms(), 2000)
    while time.ticks_diff(t, time.ticks_ms()) > 0:
        time.sleep_ms(1)


for v in VARIANTS:
    run(v)
print("DONE")
