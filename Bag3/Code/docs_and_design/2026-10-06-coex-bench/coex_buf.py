"""
coex_buf.py -- ESP-NOW receive buffer and Splat button timing, one ESP32
=========================================================================
Run on the single-chip hub (StickS3) after coex_bench.py's setup:
    python3 -m mpremote connect $HUB resume run coex_buf.py
Peer runs coex_peer.py. All 4 Splats on.

1. Buffer, 4 Splats connected and polled, for each RXBUF:
   stall   the peer broadcasts N 250-byte frames 20 ms apart; the loop reads
           ESP-NOW for 20 ms, then blocks STALL ms without reading, repeated
   burst   the peer sends BURST_N 250-byte frames back to back while the
           loop blocks; then it reads -- how many frames the buffer holds
   Reports received, driver rx_dropped delta, most frames read in one drain.

2. Buttons (needs a person). Splats GREEN: quiet radio, press each Splat
   about 5 times. Splats PURPLE: the peer broadcasts 250-byte frames every
   20 ms, press each about 5 times again. WHITE: done. A press turns that
   Splat red until release. Reports presses per Splat, IRQ-to-game-loop
   latency, and readSwitches write-to-notify round trip per phase.
"""

import sys
sys.path.insert(0, '/flash/coex')

import gc
import time
import struct
import network
import espnow
import ubluetooth

RXBUFS = (16384, 30000)
STALLS = (0, 50, 100, 200, 500, 1000)
N = 100
GAP_MS = 20
SIZE = 250
BURST_N = 150
BUTTON_S = 30
RUN_BUFFER = True
RUN_BUTTONS = True
BCAST = b'\xff' * 6

_T0 = time.ticks_ms()


def t_s():
    return time.ticks_diff(time.ticks_ms(), _T0) / 1000


def log(s):
    print("[%7.2f] %s" % (t_s(), s))


def pct(vals, p):
    if not vals:
        return -1
    v = sorted(vals)
    return v[min(len(v) - 1, int(len(v) * p / 100))]


sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.disconnect()
sta.config(channel=1)
e = espnow.ESPNow()
peer = None


def enow_up(rxbuf):
    e.active(False)
    e.config(rxbuf=rxbuf)
    e.active(True)
    e.add_peer(BCAST)
    if peer is not None:
        e.add_peer(peer)
    log("ESP-NOW rxbuf=%d" % rxbuf)


group = None
hub = None


def service():
    if group is not None:
        group.poll()


def drain(on_rx=None):
    n = 0
    while True:
        mac, msg = e.irecv(0)
        if not msg:
            return n
        n += 1
        if on_rx is not None:
            on_rx(bytes(mac), bytes(msg))


def wait_ms(ms, on_rx=None):
    end = time.ticks_add(time.ticks_ms(), ms)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        drain(on_rx)
        service()
        time.sleep_ms(1)


def send(mac, msg, sync=True):
    for _ in range(20):
        try:
            return e.send(mac, msg, sync)
        except OSError:
            drain()
            time.sleep_ms(2)
    return None


def burst_cmd(n, gap, size):
    for _ in range(5):
        if send(peer, b'B' + struct.pack('<H', n) + bytes([gap, size])):
            return True
    return False


enow_up(RXBUFS[0])
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
log("peer %s" % ':'.join('%02X' % b for b in peer))

ble = ubluetooth.BLE()
if not ble.active():
    ble.active(True)
import splat_link
from splat_hub import SplatHub
from splat_api import SplatGroup

notify_rtt = {}       # phase -> [ms]
rs_sent = [None] * 4
phase = ["setup"]


def connect(count):
    global hub, group
    hub = SplatHub(count)
    group = SplatGroup(hub)
    route = hub._irq

    def spy(event, data):
        if event == 18:
            for i, l in enumerate(hub.links):
                if l._conn_handle == data[0] and rs_sent[i] is not None:
                    notify_rtt.setdefault(phase[0], []).append(
                        time.ticks_diff(time.ticks_us(), rs_sent[i]) / 1000)
                    rs_sent[i] = None
        route(event, data)
    hub._ble.irq(spy)

    for i, link in enumerate(hub.links):
        def make(link=link, i=i):
            orig = link.readSwitches

            def rs(*a):
                rs_sent[i] = time.ticks_us()
                return orig()
            return rs
        link.readSwitches = make()

    end = time.ticks_add(time.ticks_ms(), 90000)
    while group.connected_count < count and time.ticks_diff(end, time.ticks_ms()) > 0:
        group.poll()
        drain()
        time.sleep_ms(1)
    log("connected %d/%d Splats" % (group.connected_count, count))
    wait_ms(1000)


def splat_line(label):
    log("SPLATS %s: connected=%d/%d drops=%s write_failures=%d"
        % (label, group.connected_count, group.count,
           [l.drops for l in hub.links], group.write_failures))


# ─── 1. Buffer ─────────────────────────────────

def stall_test(rxbuf, stall):
    seen = set()

    def rx(mac, msg):
        if mac == peer and msg[:1] == b'b':
            seen.add(struct.unpack('<H', msg[1:3])[0])

    d0 = e.stats()[4]
    if not burst_cmd(N, GAP_MS, SIZE):
        log("RESULT rxbuf=%d stall=%d: could not start burst" % (rxbuf, stall))
        return
    most = 0
    end = time.ticks_add(time.ticks_ms(), 200 + N * GAP_MS + 1500)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        r_end = time.ticks_add(time.ticks_ms(), 20)
        while time.ticks_diff(r_end, time.ticks_ms()) > 0:
            most = max(most, drain(rx))
            service()
            time.sleep_ms(1)
        if stall:
            time.sleep_ms(stall)          # blocked: no ESP-NOW read, no Splat poll
    most = max(most, drain(rx))
    log("RESULT rxbuf=%d stall=%4d ms: received=%d/%d (%.1f%%) rx_dropped=+%d "
        "most in one drain=%d"
        % (rxbuf, stall, len(seen), N, 100 * len(seen) / N, e.stats()[4] - d0, most))


def burst_test(rxbuf):
    seen = set()
    d0 = e.stats()[4]
    if not burst_cmd(BURST_N, 0, SIZE):
        log("RESULT rxbuf=%d burst: could not start burst" % rxbuf)
        return
    time.sleep_ms(2500)                   # blocked while the whole burst lands
    n = 0
    while True:
        mac, msg = e.irecv(0)
        if not msg:
            break
        n += 1
        if bytes(mac) == peer and msg[:1] == b'b':
            seen.add(struct.unpack('<H', msg[1:3])[0])
    wait_ms(300)
    log("RESULT rxbuf=%d burst: %d x %d B back to back, loop blocked | buffered=%d "
        "rx_dropped=+%d (holds about %d frames of %d B)"
        % (rxbuf, BURST_N, SIZE, len(seen), e.stats()[4] - d0, len(seen), SIZE))


try:
    connect(4)
    for rxbuf in (RXBUFS if RUN_BUFFER else ()):
        enow_up(rxbuf)
        try:
            for st in STALLS:
                stall_test(rxbuf, st)
            burst_test(rxbuf)
        except ValueError as ex:
            log("RESULT rxbuf=%d: FAILED %r" % (rxbuf, ex))
        splat_line("rxbuf=%d" % rxbuf)

    # ─── 2. Buttons ────────────────────────────

    enow_up(8192)

    def button_phase(label, colour, loaded):
        phase[0] = label
        group.color(colour)
        presses = [0] * group.count
        lat = []
        pending = [None] * group.count
        seen = set()

        def rx(mac, msg):
            if mac == peer and msg[:1] == b'b':
                seen.add(struct.unpack('<H', msg[1:3])[0])

        n_frames = BUTTON_S * 1000 // GAP_MS
        if loaded:
            burst_cmd(n_frames, GAP_MS, SIZE)
        log("=== buttons %s: Splats %s, press each about 5 times (%d s)"
            % (label, colour, BUTTON_S))
        end = time.ticks_add(time.ticks_ms(), BUTTON_S * 1000)
        while time.ticks_diff(end, time.ticks_ms()) > 0:
            drain(rx)
            for i, link in enumerate(hub.links):
                if pending[i] is None:
                    for ts, pr in link._raw_q:
                        if pr:
                            pending[i] = ts
                            break
            ev = group.poll()
            if ev is not None:
                i = group.last_index
                if ev == "press":
                    presses[i] += 1
                    if pending[i] is not None:
                        lat.append(time.ticks_diff(time.ticks_ms(), pending[i]))
                    group.unit(i).color("turnred")
                else:
                    group.unit(i).color(colour)
                pending[i] = None
            time.sleep_ms(1)
        wait_ms(800, rx)
        rt = notify_rtt.get(label, [])
        log("RESULT buttons %s: presses per Splat=%s | IRQ-to-loop ms p50=%d p95=%d max=%d | "
            "readSwitches->notify ms n=%d p50=%.1f p95=%.1f max=%.1f%s"
            % (label, presses, pct(lat, 50), pct(lat, 95), max(lat) if lat else -1,
               len(rt), pct(rt, 50), pct(rt, 95), max(rt) if rt else -1,
               (" | ESP-NOW received %d/%d (%.1f%%)"
                % (len(seen), n_frames, 100 * len(seen) / n_frames)) if loaded else ""))
        splat_line(label)

    if RUN_BUTTONS:
        button_phase("quiet", "turngreen", False)
        button_phase("loaded", "turnpurple", True)
    group.color("turnwhite")
    wait_ms(500)
finally:
    if hub is not None:
        hub.close_all()
        end = time.ticks_add(time.ticks_ms(), 2000)
        while time.ticks_diff(end, time.ticks_ms()) > 0:
            time.sleep_ms(1)
    log("DONE")
