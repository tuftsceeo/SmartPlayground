"""
demo_c6_hub.py -- single-chip Splat hub demo on a MockWand (BLE Splats + ESP-NOW wand)
======================================================================================
C6 port of ../2026-10-06-coex-bench/demo_hub.py. Run on a MockWand acting as
the hub, from a clean boot with main.py disabled (README.md):
    python3 -m mpremote connect $HUB resume run demo_c6_hub.py
Needs /coex/ (splat_link, splat_hub, splat_api, ble_splat). The player's
wand runs ../2026-10-06-coex-bench/demo_wand.py unchanged. Splats on.

One Splat is lit in its unit colour, the rest are off.
Wand b'N'          -> light the next connected Splat, tell the wand b'L' idx
Lit Splat pressed  -> wand b'S' 'h' idx (hit); other Splat -> b'S' 'm' (miss)
All hub -> wand messages are ACKed unicast with up to 3 tries.

Differences from the S3 script: antenna selected first, /coex path, a clean
boot check, memory logged after each bring-up step and every MEM_EVERY_S,
and the longest game-loop stall logged with it.
"""

import time
from machine import Pin

# MockWands have a u.FL antenna fitted (MockWand/lib/espnow_manager.py
# EXTERNAL_ANTENNA). Set False on a board without one.
EXTERNAL_ANTENNA = True

Pin(3, Pin.OUT).value(0)                    # RF switch enable, active low
time.sleep_ms(100)
Pin(14, Pin.OUT).value(1 if EXTERNAL_ANTENNA else 0)

import sys
sys.path.insert(0, '/coex')

import gc
import network
import espnow
import esp32
import ubluetooth

DEMO_S = 900
SPLATS = 4
RXBUF = 16384
MEM_EVERY_S = 60
CLEAN_BOOT_MIN_LARGEST = 150000   # 0 = run on any boot
BCAST = b'\xff' * 6
UNIT_COLOUR = ("turnred", "turngreen", "turnblue", "turnyellow")

_T0 = time.ticks_ms()


def log(s):
    print("[%7.2f] %s" % (time.ticks_diff(time.ticks_ms(), _T0) / 1000, s))


def mem(tag):
    """Log GC and internal IDF heap; return the largest free IDF block."""
    gc.collect()
    internal = [h for h in esp32.idf_heap_info(esp32.HEAP_DATA) if h[0] < 1000000]
    largest = max(h[2] for h in internal)
    log("MEM %s: gc_free=%d gc_alloc=%d idf_free=%d idf_largest=%d"
        % (tag, gc.mem_free(), gc.mem_alloc(), sum(h[1] for h in internal), largest))
    return largest


if mem("start") < CLEAN_BOOT_MIN_LARGEST:
    log("FAIL: largest free IDF block is below CLEAN_BOOT_MIN_LARGEST=%d. "
        "Not a clean boot: disable main.py, hard reset, run with 'resume' (README.md)."
        % CLEAN_BOOT_MIN_LARGEST)
    raise SystemExit

sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.disconnect()
sta.config(channel=1)
e = espnow.ESPNow()
e.active(False)
e.config(rxbuf=RXBUF)
e.active(True)
e.add_peer(BCAST)
mem("espnow")

ble = ubluetooth.BLE()
if not ble.active():
    ble.active(True)
mem("ble active")
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
    mem_t = time.ticks_add(time.ticks_ms(), MEM_EVERY_S * 1000)
    last = time.ticks_ms()
    stall = 0
    pending = [None] * SPLATS
    end = time.ticks_add(time.ticks_ms(), DEMO_S * 1000)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        now = time.ticks_ms()
        stall = max(stall, time.ticks_diff(now, last))
        last = now
        if time.ticks_diff(now, mem_t) >= 0:
            mem_t = time.ticks_add(now, MEM_EVERY_S * 1000)
            log("loop stall max=%d ms since last report | connected=%d/%d"
                % (stall, group.connected_count, SPLATS))
            mem("demo")
            stall = 0
            last = time.ticks_ms()
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
    mem("end")
    log("DONE")
