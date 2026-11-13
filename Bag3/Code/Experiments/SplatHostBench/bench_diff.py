"""4-Splat connect bench: the working run (bench_ble_conns.py variant "em"),
plus STEP to add what wand_main does before the host loop.

Libraries load from /benchmpy (lib_mpy copies) ahead of /lib.
STEP 0  ESP-NOW, BLE, hub modules, connect (the run that got 4 of 4)
STEP 1  as 0, plus every module wand_main imports, imported after BLE
STEP 2  as 1, plus Leds(), PN532 and a wand_main-sized GC load
STEP 3  as 2, with splatpair.SplatPairing (needs /role.txt, /pairing.json) and
        the host loop's ESP-NOW poll, glow and LED writes

Run after unplugging the wand: Ctrl-C in the stub's grace, then run this
file from Thonny. MEM lines print each IDF data region (total, free, largest).
"""

STEP = 0

import sys
sys.path.insert(0, "/benchmpy")
import gc
import time
import esp32
from machine import Pin

MACS = ["AB:42:00:00:64:3F", "AB:42:00:00:62:2F", "AB:42:00:00:80:B4", "AB:42:00:00:B2:16"]
CONNECT_MS = 45000
T0 = time.ticks_ms()


def mem(tag):
    gc.collect()
    r = esp32.idf_heap_info(esp32.HEAP_DATA)
    print("MEM %-14s t=%6d gcf=%6d %s" % (tag, time.ticks_diff(time.ticks_ms(), T0),
          gc.mem_free(), " ".join("%d/%d/%d" % (x[0], x[1], x[2]) for x in r)))


def main():
    print("STEP %d" % STEP)
    Pin(3, Pin.OUT).value(0)
    time.sleep_ms(100)
    Pin(14, Pin.OUT).value(1)
    mem("start")
    from espnow_manager import ESPNowManager
    en = ESPNowManager()
    en.init()
    mem("espnow")
    import ubluetooth
    ubluetooth.BLE().active(True)
    mem("ble")
    keep = []
    if STEP >= 1:
        import hubtype, pn532, lis2dw12, max17048, leds, power_led, buzzer
        import nfc_reader, actions, battery, game_tags, brightness, game_store
        import pairing, splatpair, splat_host, lobby_game
        mem("imports")
    if STEP >= 2:
        from leds import Leds
        from hubtype import HUB_CONFIG
        keep.append(Leds())
        try:
            from machine import I2C
            from pn532 import PN532
            keep.append(PN532(I2C(0)))
        except Exception as e:
            print("pn532 skipped:", e)
        keep.append(bytearray(110000))
        mem("objects")
    ctl = None
    if STEP >= 3:
        import splatpair
        from buzzer import Buzzer
        from hubtype import HUB_CONFIG
        ctl = splatpair.SplatPairing(MACS, en, keep[0], Buzzer(HUB_CONFIG["buzzer_pin"]))
        hub = ctl.hub
        print("host=%s" % ctl.host)
        mem("pairing built")
    else:
        from splat_hub import SplatHub
        from splat_api import SplatGroup
        mem("hub mods")
        hub = SplatHub(count=len(MACS), macs=MACS)
        group = SplatGroup(hub)
        mem("hub built")
    ready = [False] * len(MACS)
    fails = [0] * len(MACS)
    try:
        end = time.ticks_add(time.ticks_ms(), CONNECT_MS)
        while time.ticks_diff(end, time.ticks_ms()) > 0:
            if ctl is None:
                group.poll()
            else:
                ctl.poll()
                ctl.refresh_glow()
                en.poll()
            for i, link in enumerate(hub.links):
                if link.ready and not ready[i]:
                    ready[i] = True
                    mem("ready %d" % sum(ready))
                f = link.failed_attempts
                if f != fails[i]:
                    fails[i] = f
                    if f == 1:
                        mem("fail " + MACS[i][-5:])
            if all(ready):
                break
            time.sleep_ms(1)
        print("RESULT step %d connected %d of %d" % (STEP, sum(ready), len(MACS)))
        mem("end")
    finally:
        hub.close_all()


main()
