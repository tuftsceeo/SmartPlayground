"""
demo_wand.py -- wand half of the single-chip Splat hub demo
============================================================
Run on a MockWand: python3 -m mpremote connect $WAND resume run demo_wand.py
Uses the wand's /lib (buzzer, leds, hubtype, espnow_manager antenna).

Button press  -> ACKed unicast b'N' (next Splat) to the hub
Hub b'L' idx  -> LEDs take that Splat's colour
Hub b'S' h idx -> hit sound (tone per Splat + success)
Hub b'S' m    -> miss sound (low buzz)
"""

import time
import network
import espnow
from machine import Pin

from hubtype import HUB_CONFIG
from buzzer import Buzzer
from leds import Leds

try:
    import espnow_manager
    espnow_manager._configure_antenna()
except Exception as ex:
    print("wand: antenna left as is (%r)" % ex)

DEMO_S = 900
BCAST = b'\xff' * 6
UNIT_RGB = ((60, 0, 0), (0, 60, 0), (0, 0, 60), (60, 40, 0))
UNIT_TONE = (523, 659, 784, 1047)

buz = Buzzer(HUB_CONFIG["buzzer_pin"])
leds = Leds()
btn = Pin(HUB_CONFIG["button_pin"], Pin.IN, Pin.PULL_UP)

sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.disconnect()
sta.config(channel=1)
e = espnow.ESPNow()
e.active(False)
e.config(rxbuf=2048)
e.active(True)
try:
    e.add_peer(BCAST)
except OSError:
    pass

hub = None
leds.solid(10, 10, 10)
print("wand: waiting for hub")


def send(msg):
    for _ in range(3):
        try:
            if e.send(hub, msg, True):
                return True
        except OSError:
            time.sleep_ms(5)
    return False


btn_was = False
btn_t = 0
end = time.ticks_add(time.ticks_ms(), DEMO_S * 1000)
try:
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        mac, msg = e.irecv(0)
        if msg:
            mac = bytes(mac)
            k = msg[0]
            if k == 0x48:                                   # H from hub
                if hub is None:
                    hub = mac
                    try:
                        e.add_peer(hub)
                    except OSError:
                        pass
                    print("wand: hub %s" % ':'.join('%02X' % b for b in hub))
                    buz.beep(1319, 40)
                send(b'h')
            elif mac == hub and k == 0x4C:                  # L idx
                i = msg[1]
                leds.solid(*UNIT_RGB[i % 4])
                print("wand: lit Splat %d" % i)
            elif mac == hub and k == 0x53:                  # S
                if msg[1:2] == b'h':
                    i = msg[2]
                    print("wand: HIT Splat %d" % i)
                    buz.beep(UNIT_TONE[i % 4], 120)
                    buz.success()
                else:
                    print("wand: miss")
                    buz.beep(196, 180)
        now = time.ticks_ms()
        down = btn.value() == 0
        if down and not btn_was and time.ticks_diff(now, btn_t) > 60 and hub is not None:
            btn_t = now
            ok = send(b'N')
            print("wand: button -> next, ACK=%s" % ok)
            if not ok:
                buz.beep(110, 60)
        btn_was = down
        time.sleep_ms(1)
finally:
    leds.off()
    print("wand: DONE")
