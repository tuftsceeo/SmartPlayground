"""
coex_c6_one.py -- one Splat: BLE alone vs BLE + ESP-NOW, on one ESP32-C6
=========================================================================
C6 port of ../2026-10-06-coex-bench/coex_one.py. Run on a MockWand acting as
the single-chip hub, from a clean boot with main.py disabled (README.md):
    python3 -m mpremote connect $HUB resume run coex_c6_one.py
Peer: a second MockWand running ../2026-10-06-coex-bench/coex_peer.py.
Exactly one Splat on.

BLE comes up first and WiFi/ESP-NOW only after phase A, so this script is
also the ble_first bring-up test (MicroPython #18859 reports C6 failing
here). A failed bring-up logs FAIL with memory numbers and stops.

Differences from the S3 script: antenna selected first, /coex path, a clean
boot check, memory logged around each bring-up step, and the longest
game-loop stall per phase.

Phases, PHASE_S each, a person pressing the Splat about 10 times in each:
  A BLUE    BLE only -- WiFi/ESP-NOW never started
  B GREEN   ESP-NOW active, no traffic
  C PURPLE  peer broadcasts 250-byte frames every 20 ms, we ping it every 100 ms
A press turns the Splat red until release. WHITE: done.
Per phase: presses, BLE IRQ -> game loop, press -> red write returned,
readSwitches write -> notify round trip.
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
import struct
import esp32
import ubluetooth

PHASE_S = 30
GAP_MS = 20
SIZE = 250
RXBUF = 16384
CLEAN_BOOT_MIN_LARGEST = 150000   # 0 = run on any boot
BCAST = b'\xff' * 6

_T0 = time.ticks_ms()


def t_s():
    return time.ticks_diff(time.ticks_ms(), _T0) / 1000


def log(s):
    print("[%7.2f] %s" % (t_s(), s))


def mem(tag):
    """Log GC and internal IDF heap; return the largest free IDF block."""
    gc.collect()
    internal = [h for h in esp32.idf_heap_info(esp32.HEAP_DATA) if h[0] < 1000000]
    largest = max(h[2] for h in internal)
    log("MEM %s: gc_free=%d gc_alloc=%d idf_free=%d idf_largest=%d"
        % (tag, gc.mem_free(), gc.mem_alloc(), sum(h[1] for h in internal), largest))
    return largest


def pct(vals, p):
    if not vals:
        return -1
    v = sorted(vals)
    return v[min(len(v) - 1, int(len(v) * p / 100))]


if mem("start") < CLEAN_BOOT_MIN_LARGEST:
    log("FAIL: largest free IDF block is below CLEAN_BOOT_MIN_LARGEST=%d. "
        "Not a clean boot: disable main.py, hard reset, run with 'resume' (README.md)."
        % CLEAN_BOOT_MIN_LARGEST)
    raise SystemExit

ble = ubluetooth.BLE()
try:
    ble.active(True)
except OSError as ex:
    mem("ble FAILED")
    log("FAIL: BLE().active(True) raised %r" % ex)
    raise
mem("ble active")
import splat_link
from splat_hub import SplatHub
from splat_api import SplatGroup

phase = ["setup"]
notify_rtt = {}
rs_sent = [None]
e = None
peer = None

hub = SplatHub(1)
group = SplatGroup(hub)
_route = hub._irq


def _spy(event, data):
    if event == 18:
        l = hub.links[0]
        if l._conn_handle == data[0] and rs_sent[0] is not None:
            notify_rtt.setdefault(phase[0], []).append(
                time.ticks_diff(time.ticks_us(), rs_sent[0]) / 1000)
            rs_sent[0] = None
    elif event == 27:
        h, itvl, lat, sup, st = data
        log("BLE conn update interval=%.2f ms latency=%d supervision=%d ms"
            % (itvl * 1.25, lat, sup * 10))
    _route(event, data)


hub._ble.irq(_spy)
_orig_rs = hub.links[0].readSwitches


def _rs(*a):
    rs_sent[0] = time.ticks_us()
    return _orig_rs()


hub.links[0].readSwitches = _rs


def drain(on_rx=None):
    if e is None:
        return
    while True:
        mac, msg = e.irecv(0)
        if not msg:
            return
        if on_rx is not None:
            on_rx(bytes(mac), bytes(msg))


def send(mac, msg, sync=True):
    for _ in range(20):
        try:
            return e.send(mac, msg, sync)
        except OSError:
            drain()
            time.sleep_ms(2)
    return None


def wait_ms(ms, on_rx=None):
    end = time.ticks_add(time.ticks_ms(), ms)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        drain(on_rx)
        group.poll()
        time.sleep_ms(1)


def enow_start():
    global e, peer
    import network
    import espnow
    mem("pre-enow")
    try:
        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        sta.disconnect()
        sta.config(channel=1)
        e = espnow.ESPNow()
        e.config(rxbuf=RXBUF)
        e.active(True)
        e.add_peer(BCAST)
    except OSError as ex:
        mem("enow FAILED")
        log("FAIL: ESP-NOW bring-up after BLE raised %r" % ex)
        raise
    mem("post-enow")
    found = []
    for _ in range(50):
        send(BCAST, b'H', False)
        wait_ms(200, lambda mac, msg: found.append(mac) if msg[:1] == b'h' else None)
        if found:
            break
    if not found:
        log("FAIL: no peer answered")
        raise SystemExit
    peer = found[0]
    e.add_peer(peer)
    log("ESP-NOW up, peer %s" % ':'.join('%02X' % b for b in peer))


def run_phase(label, colour, loaded):
    phase[0] = label
    unit = group.unit(0)
    unit.color(colour)
    presses = 0
    lat = []
    to_red = []
    pending = None
    seen = set()
    pings = [0, 0]
    stall = 0

    def rx(mac, msg):
        if mac == peer and msg[:1] == b'b':
            seen.add(struct.unpack('<H', msg[1:3])[0])

    n_frames = PHASE_S * 1000 // GAP_MS
    if loaded:
        for _ in range(5):
            if send(peer, b'B' + struct.pack('<H', n_frames) + bytes([GAP_MS, SIZE])):
                break
    log("=== %s: Splat %s, press about 10 times (%d s)" % (label, colour, PHASE_S))
    end = time.ticks_add(time.ticks_ms(), PHASE_S * 1000)
    nxt_ping = time.ticks_ms()
    link = hub.links[0]
    last = time.ticks_ms()
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        now = time.ticks_ms()
        stall = max(stall, time.ticks_diff(now, last))
        last = now
        drain(rx)
        if loaded and time.ticks_diff(time.ticks_ms(), nxt_ping) >= 0:
            nxt_ping = time.ticks_add(nxt_ping, 100)
            pings[0] += 1
            if send(peer, b'P' + struct.pack('<H', pings[0] & 0xFFFF)):
                pings[1] += 1
        if pending is None:
            for ts, pr in link._raw_q:
                if pr:
                    pending = ts
                    break
        ev = group.poll()
        if ev == "press":
            presses += 1
            if pending is not None:
                lat.append(time.ticks_diff(time.ticks_ms(), pending))
            unit.color("turnred")
            if pending is not None:
                to_red.append(time.ticks_diff(time.ticks_ms(), pending))
            pending = None
        elif ev == "release":
            unit.color(colour)
            pending = None
        time.sleep_ms(1)
    wait_ms(800, rx)
    rt = notify_rtt.get(label, [])
    extra = ""
    if loaded:
        extra = (" | ESP-NOW bcast received %d/%d (%.1f%%), pings ACKed %d/%d"
                 % (len(seen), n_frames, 100 * len(seen) / n_frames, pings[1], pings[0]))
    log("RESULT %s: presses=%d | IRQ-to-loop ms p50=%d p95=%d max=%d | "
        "IRQ-to-red-write-returned ms p50=%d max=%d | readSwitches->notify ms n=%d "
        "p50=%.1f p95=%.1f max=%.1f | loop stall max=%d ms%s"
        % (label, presses, pct(lat, 50), pct(lat, 95), max(lat) if lat else -1,
           pct(to_red, 50), max(to_red) if to_red else -1,
           len(rt), pct(rt, 50), pct(rt, 95), max(rt) if rt else -1, stall, extra))
    log("SPLAT %s: connected=%s drops=%d write_failures=%d"
        % (label, group.connected, link.drops, group.write_failures))


try:
    end = time.ticks_add(time.ticks_ms(), 90000)
    while not group.connected and time.ticks_diff(end, time.ticks_ms()) > 0:
        group.poll()
        time.sleep_ms(1)
    log("connected=%s" % group.connected)
    mem("splat connected")
    wait_ms(1000)
    run_phase("A-ble-only", "turnblue", False)
    enow_start()
    wait_ms(1000)
    run_phase("B-enow-idle", "turngreen", False)
    run_phase("C-enow-loaded", "turnpurple", True)
    group.unit(0).color("turnwhite")
    wait_ms(500)
    mem("end")
finally:
    hub.close_all()
    end = time.ticks_add(time.ticks_ms(), 2000)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        time.sleep_ms(1)
    log("DONE")
