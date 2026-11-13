"""
bench_ble_conns.py -- how many Splats one wand connects, and why it stops (not deployed)
=======================================================================================
Run on a wand whose main.py is renamed to main.py.bak, right after a hard reset
(a soft reset keeps the IDF heap's fragmentation; 2026-09-23-ap-memory-order.md):
    python -m mpremote connect COM7 reset
    python -m mpremote connect COM7 resume run "utilities/bench_ble_conns.py"
Set VARIANT below (or copy the file with another value) before a run:

  "a"  BLE only, first thing; default connection interval
  "e"  ESP-NOW first (espnow_manager.init(), as main.py does), then BLE: the
       Splat host's real order
  "c"  hub modules, Leds() and a 4 KB Python ballast, then BLE; no ESP-NOW
  "b"  as "e", with a long connection interval (INTERVAL_B)
A trailing "m" (e.g. "am") imports the libraries from /benchmpy/, compiled on
the computer with mpy-cross, instead of compiling lib/*.py on the wand.

The external antenna is selected first in every variant (the wands have u.FL
antennas; espnow_manager.EXTERNAL_ANTENNA). Each run pins the four bench
Splats (MACS), connects for CONNECT_MS, then disconnects. MEM lines give
gc.mem_free() and the IDF data heap's total free and largest free block.
"""

VARIANT = "a"

import sys
if VARIANT.endswith("m"):
    sys.path.insert(0, "/benchmpy")
import gc
import time
import esp32
from machine import Pin

MACS = ["AB:42:00:00:64:3F", "AB:42:00:00:62:2F", "AB:42:00:00:80:B4", "AB:42:00:00:B2:16"]
CONNECT_MS = 45000
INTERVAL_B = (50000, 100000)
T0 = time.ticks_ms()


def mem(tag):
    gc.collect()
    total = 0
    largest = 0
    for r in esp32.idf_heap_info(esp32.HEAP_DATA):
        total += r[1]
        if r[2] > largest:
            largest = r[2]
    print("MEM %-22s t=%6d gc_free=%6d idf_free=%6d idf_largest=%6d"
          % (tag, time.ticks_diff(time.ticks_ms(), T0), gc.mem_free(), total, largest))


def main():
    print("VARIANT %s" % VARIANT)
    Pin(3, Pin.OUT).value(0)
    time.sleep_ms(100)
    Pin(14, Pin.OUT).value(1)
    mem("start")
    keep = None
    if VARIANT[0] in "eb":
        from espnow_manager import ESPNowManager
        keep = ESPNowManager()
        keep.init()
        mem("espnow active")
    if VARIANT[0] == "c":
        import splat_hub, splat_api, splat_link
        from leds import Leds
        keep = (Leds(), bytearray(4096))
        mem("after leds+ballast")
    import ubluetooth
    ubluetooth.BLE().active(True)
    mem("ble active")
    import splat_link
    if VARIANT[0] == "b":
        splat_link.CONN_INTERVAL_US = INTERVAL_B
        print("interval %s" % (INTERVAL_B,))
    from splat_hub import SplatHub
    from splat_api import SplatGroup
    mem("hub modules")
    hub = SplatHub(count=len(MACS), macs=MACS)
    group = SplatGroup(hub)
    mem("hub built")
    ready = [False] * len(MACS)
    fails = [0] * len(MACS)
    try:
        end = time.ticks_add(time.ticks_ms(), CONNECT_MS)
        while time.ticks_diff(end, time.ticks_ms()) > 0:
            group.poll()
            for i, link in enumerate(hub.links):
                if link.ready and not ready[i]:
                    ready[i] = True
                    print("RESULT ready %d %s" % (sum(ready), MACS[i]))
                    mem("ready %d" % sum(ready))
                f = link.failed_attempts
                if f != fails[i]:
                    fails[i] = f
                    if f <= 2:
                        mem("fail %s #%d" % (MACS[i][-5:], f))
            if all(ready):
                break
            time.sleep_ms(1)
        print("RESULT variant %s connected %d of %d (discovering=%s)"
              % (VARIANT, sum(ready), len(MACS), hub.discovering))
        mem("end")
    finally:
        hub.close_all()
        keep = None


main()
