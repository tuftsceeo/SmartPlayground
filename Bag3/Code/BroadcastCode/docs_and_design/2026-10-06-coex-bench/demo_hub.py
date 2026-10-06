"""
demo_hub.py -- single-chip Splat hub demo (BLE Splats + ESP-NOW wand, one ESP32)
=================================================================================
Run on the StickS3: python3 -m mpremote connect $HUB resume run demo_hub.py
Needs /flash/coex/ (splat_link, splat_hub, splat_api, ble_splat). Wand runs
demo_wand.py. Splats on.

One Splat is lit in its unit colour, the rest are off.
Wand b'N'          -> light the next connected Splat, tell the wand b'L' idx
Lit Splat pressed  -> wand b'S' 'h' idx (hit); other Splat -> b'S' 'm' (miss)
All hub -> wand messages are ACKed unicast with up to 3 tries.
"""

import sys
sys.path.insert(0, '/flash/coex')

import time
import network
import espnow
import ubluetooth

DEMO_S = 900
SPLATS = 4
BCAST = b'\xff' * 6
UNIT_COLOUR = ("turnred", "turngreen", "turnblue", "turnyellow")

_T0 = time.ticks_ms()


def log(s):
    print("[%7.2f] %s" % (time.ticks_diff(time.ticks_ms(), _T0) / 1000, s))


sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.disconnect()
sta.config(channel=1)
e = espnow.ESPNow()
e.active(False)
e.config(rxbuf=16384)
e.active(True)
e.add_peer(BCAST)

ble = ubluetooth.BLE()
if not ble.active():
    ble.active(True)
from splat_hub import SplatHub
from splat_api import SplatGroup

hub = SplatHub(SPLATS)
group = SplatGroup(hub)
wand = None
lit = None
up_was = [False] * SPLATS


def send(msg):
    t = time.ticks_ms()
    for attempt in range(3):
        try:
            if e.send(wand, msg, True):
                return attempt + 1, time.ticks_diff(time.ticks_ms(), t)
        except OSError:
            time.sleep_ms(5)
    return 0, time.ticks_diff(time.ticks_ms(), t)


def next_up(start):
    for k in range(1, SPLATS + 1):
        i = (start + k) % SPLATS
        if group.unit(i).connected:
            return i
    return None


def light(i):
    global lit
    old = lit
    lit = i
    if old is not None and old != i and group.unit(old).connected:
        group.unit(old).color("turnoff")
    if i is not None:
        group.unit(i).color(UNIT_COLOUR[i])
        if wand is not None:
            tries, ms = send(b'L' + bytes([i]))
            log("lit Splat %d, wand told (tries=%d, %d ms)" % (i, tries, ms))


try:
    hello_t = time.ticks_ms()
    pending = [None] * SPLATS
    end = time.ticks_add(time.ticks_ms(), DEMO_S * 1000)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        now = time.ticks_ms()
        if wand is None and time.ticks_diff(now, hello_t) >= 0:
            hello_t = time.ticks_add(now, 300)
            try:
                e.send(BCAST, b'H', False)
            except OSError:
                pass

        while True:
            mac, msg = e.irecv(0)
            if not msg:
                break
            mac = bytes(mac)
            if msg[:1] == b'h' and wand is None:
                wand = mac
                e.add_peer(wand)
                log("wand %s" % ':'.join('%02X' % b for b in wand))
                if lit is not None:
                    light(lit)
            elif mac == wand and msg[:1] == b'N':
                t = time.ticks_ms()
                nxt = next_up(lit if lit is not None else -1)
                log("wand button -> next")
                light(nxt)
                log("  next handled in %d ms" % time.ticks_diff(time.ticks_ms(), t))

        for i in range(SPLATS):
            up = group.unit(i).connected
            if up and not up_was[i]:
                log("Splat %d connected" % i)
                if lit is None or not group.unit(lit).connected:
                    light(i)
                elif i != lit:
                    group.unit(i).color("turnoff")
            if not up and up_was[i]:
                log("Splat %d DISCONNECTED" % i)
                if i == lit:
                    light(next_up(i))
            up_was[i] = up
            if pending[i] is None:
                for ts, pr in hub.links[i]._raw_q:
                    if pr:
                        pending[i] = ts
                        break

        ev = group.poll()
        if ev == "press":
            i = group.last_index
            t0 = pending[i]
            if wand is not None:
                if i == lit:
                    tries, ms = send(b'Sh' + bytes([i]))
                    kind = "HIT"
                else:
                    tries, ms = send(b'Sm')
                    kind = "miss"
                since = time.ticks_diff(time.ticks_ms(), t0) if t0 is not None else -1
                log("Splat %d pressed: %s -> wand ACK tries=%d send %d ms, "
                    "press IRQ to ACK %d ms" % (i, kind, tries, ms, since))
            pending[i] = None
        elif ev == "release":
            pending[group.last_index] = None
        time.sleep_ms(1)
finally:
    hub.close_all()
    end = time.ticks_add(time.ticks_ms(), 2000)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        time.sleep_ms(1)
    log("DONE")
