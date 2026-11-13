"""STEP 5: connect 4 Splats right after BLE, then do STEP 2's imports and
objects, then keep polling to see the links hold. Fixed length: CONNECT_MS
+ HOLD_MS. Compare with bench_step3.py (connect after imports)."""

import sys
sys.path.insert(0, "/benchmpy")
import gc
import time
import esp32
from machine import Pin

MACS = ["AB:42:00:00:64:3F", "AB:42:00:00:62:2F", "AB:42:00:00:80:B4", "AB:42:00:00:B2:16"]
CONNECT_MS = 30000
HOLD_MS = 20000
T0 = time.ticks_ms()


def mem(tag):
    gc.collect()
    r = esp32.idf_heap_info(esp32.HEAP_DATA)
    print("MEM %-14s t=%6d gcf=%6d %s" % (tag, time.ticks_diff(time.ticks_ms(), T0),
          gc.mem_free(), " ".join("%d/%d/%d" % (x[0], x[1], x[2]) for x in r)))


def run(group, hub, ms, ready):
    end = time.ticks_add(time.ticks_ms(), ms)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        group.poll()
        for i, link in enumerate(hub.links):
            if link.ready != ready[i]:
                ready[i] = link.ready
                mem("%s %s" % ("up" if link.ready else "DOWN", MACS[i][-5:]))
        if ms == CONNECT_MS and all(ready):
            break
        time.sleep_ms(1)


def main():
    Pin(3, Pin.OUT).value(0)
    time.sleep_ms(100)
    Pin(14, Pin.OUT).value(1)
    mem("start")
    from espnow_manager import ESPNowManager
    en = ESPNowManager()
    en.init()
    import ubluetooth
    ubluetooth.BLE().active(True)
    mem("ble")
    from splat_hub import SplatHub
    from splat_api import SplatGroup
    hub = SplatHub(count=len(MACS), macs=MACS)
    group = SplatGroup(hub)
    ready = [False] * len(MACS)
    try:
        run(group, hub, CONNECT_MS, ready)
        print("CONNECTED %d of 4" % sum(ready))
        import hubtype, pn532, lis2dw12, max17048, leds, power_led, buzzer
        import nfc_reader, actions, battery, game_tags, brightness, game_store
        import pairing, splatpair, lobby_game
        mem("imports")
        from leds import Leds
        keep = [Leds()]
        try:
            from machine import I2C
            from pn532 import PN532
            keep.append(PN532(I2C(0)))
        except Exception as e:
            print("pn532 skipped:", e)
        keep.append(bytearray(110000))
        mem("objects")
        run(group, hub, HOLD_MS, ready)
        print("RESULT step 5 held %d of 4" % sum(ready))
        mem("end")
    finally:
        hub.close_all()


main()
