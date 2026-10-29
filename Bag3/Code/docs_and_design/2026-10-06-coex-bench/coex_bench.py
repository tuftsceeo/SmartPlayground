"""
coex_bench.py -- BLE (Splat hub) + ESP-NOW on one ESP32, measured
==================================================================
Run on the single-chip hub (StickS3):
    python3 -m mpremote connect $HUB resume run coex_bench.py
Needs on the hub, in /flash/coex/: splat_link.py, splat_hub.py,
splat_api.py, ble_splat.py (from SplatCompanion/Companion). Needs a peer
running coex_peer.py, and all Splats switched on and advertising.

Order: ESP-NOW up first, then BLE. Phases: SPLAT_COUNTS connected Splats
(each a fresh SplatHub, polled as the hub's game loop does, plus a color
write to every Splat each second), a soak at the largest count, BLE on
with no links, BLE off. Each phase runs the same ESP-NOW tests:

  ping   N unicast pings, GAP_MS apart; ACK at our end, echo received back
  brx    the peer broadcasts N frames GAP_MS apart; how many we receive
  btx    we broadcast N frames GAP_MS apart; how many the peer counted
  bulk   BULK_BYTES as 245-byte unicast chunks, up to 3 tries each; KB/s
"""

import sys
sys.path.insert(0, '/flash/coex')

import gc
import time
import struct
import network
import espnow
import esp32

N = 300
GAP_MS = 20
BULK_BYTES = 36 * 1024
CHUNK = 245
SPLAT_COUNTS = (1, 2, 4)
SOAK_S = 300
CONNECT_WAIT_S = 90
CONN_INTERVAL_US = None      # None = stack default, or (min_us, max_us)
BCAST = b'\xff' * 6

_T0 = time.ticks_ms()


def t_s():
    return time.ticks_diff(time.ticks_ms(), _T0) / 1000


def log(s):
    print("[%7.2f] %s" % (t_s(), s))


def mem(tag):
    gc.collect()
    internal = [h for h in esp32.idf_heap_info(esp32.HEAP_DATA) if h[0] < 1000000]
    log("MEM %s: gc_free=%d idf_free=%d idf_largest=%d"
        % (tag, gc.mem_free(), sum(h[1] for h in internal), max(h[2] for h in internal)))


def pct(vals, p):
    if not vals:
        return -1
    v = sorted(vals)
    return v[min(len(v) - 1, int(len(v) * p / 100))]


# ─── ESP-NOW first ─────────────────────────────

mem("start")
sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.disconnect()
sta.config(channel=1)
e = espnow.ESPNow()
e.config(rxbuf=8192)
e.active(True)
e.add_peer(BCAST)
log("ESP-NOW up: MAC %s channel %d"
    % (':'.join('%02X' % b for b in sta.config('mac')), sta.config('channel')))
mem("espnow")

group = None        # SplatGroup while a phase has Splats
hub = None
bstats = {}


def service():
    if group is not None:
        group.poll()


def wait_ms(ms, on_rx=None):
    end = time.ticks_add(time.ticks_ms(), ms)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        drain(on_rx)
        service()
        time.sleep_ms(1)


def drain(on_rx=None):
    while True:
        mac, msg = e.irecv(0)
        if not msg:
            return
        if on_rx is not None:
            on_rx(bytes(mac), bytes(msg))


def send(mac, msg, sync=True):
    """Returns (acked_or_None, ms spent in send())."""
    t = time.ticks_us()
    for _ in range(20):
        try:
            r = e.send(mac, msg, sync)
            return r, time.ticks_diff(time.ticks_us(), t) / 1000
        except OSError:
            drain()
            time.sleep_ms(2)
    return None, time.ticks_diff(time.ticks_us(), t) / 1000


# ─── Find the peer ─────────────────────────────

peer = None
found = []


def _hello_rx(mac, msg):
    if msg[:1] == b'h' and not found:
        found.append(mac)


for _ in range(50):
    send(BCAST, b'H', False)
    wait_ms(200, _hello_rx)
    if found:
        break
if not found:
    log("FAIL: no peer answered (is coex_peer.py running?)")
    raise SystemExit
peer = found[0]
e.add_peer(peer)
log("peer %s" % ':'.join('%02X' % b for b in peer))


def peer_stats():
    got = []

    def rx(mac, msg):
        if mac == peer and msg[:1] == b'S':
            got.append(msg[1:].decode())
    for _ in range(5):
        send(peer, b'S')
        wait_ms(300, rx)
        if got:
            d = {}
            for kv in got[0].split(','):
                k, v = kv.split('=')
                d[k] = int(v)
            return d
    return None


def peer_reset():
    send(peer, b'Z')
    wait_ms(50)


# ─── Tests ─────────────────────────────────────

def color_tick(state):
    """Game-like load: a color write to every Splat once a second."""
    if group is None:
        return
    now = time.ticks_ms()
    if time.ticks_diff(now, state[0]) >= 1000:
        state[0] = now
        state[1] = (state[1] + 1) % 2
        group.color("turnblue" if state[1] else "turngreen")


def test_ping(label, n=N, gap=GAP_MS):
    peer_reset()
    acked = 0
    nack = 0
    err = 0
    sent_at = {}
    echoes = set()
    rtts = []
    send_ms = []

    def rx(mac, msg):
        if mac == peer and msg[:1] == b'R':
            s = struct.unpack('<H', msg[1:3])[0]
            if s not in echoes and s in sent_at:
                echoes.add(s)
                rtts.append(time.ticks_diff(time.ticks_ms(), sent_at[s]))

    cs = [time.ticks_ms(), 0]
    t = time.ticks_ms()
    for i in range(n):
        sent_at[i] = time.ticks_ms()
        r, ms = send(peer, b'P' + struct.pack('<H', i))
        send_ms.append(ms)
        if r is None:
            err += 1
        elif r:
            acked += 1
        else:
            nack += 1
        color_tick(cs)
        t = time.ticks_add(t, gap)
        while time.ticks_diff(t, time.ticks_ms()) > 0:
            drain(rx)
            service()
            time.sleep_ms(1)
    wait_ms(500, rx)
    ps = peer_stats() or {}
    log("RESULT %s ping: sent=%d acked=%d nack=%d err=%d | peer got=%d echo_ok=%d "
        "echo_fail=%d | echoes back=%d | send ms p50=%.1f p95=%.1f max=%.1f | "
        "rtt ms p50=%d p95=%d max=%d"
        % (label, n, acked, nack, err, ps.get('ping', -1), ps.get('echo_ok', -1),
           ps.get('echo_fail', -1), len(echoes), pct(send_ms, 50), pct(send_ms, 95),
           max(send_ms), pct(rtts, 50), pct(rtts, 95), max(rtts) if rtts else -1))


def test_brx(label, n=N, gap=GAP_MS):
    seen = set()

    def rx(mac, msg):
        if mac == peer and msg[:1] == b'b':
            seen.add(struct.unpack('<H', msg[1:3])[0])

    r = None
    for _ in range(5):
        r, _ms = send(peer, b'B' + struct.pack('<H', n) + bytes([gap]))
        if r:
            break
    if not r:
        log("RESULT %s brx: could not start the peer burst" % label)
        return
    cs = [time.ticks_ms(), 0]
    end = time.ticks_add(time.ticks_ms(), 200 + n * gap + 1500)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        drain(rx)
        service()
        color_tick(cs)
        time.sleep_ms(1)
    # longest run of consecutive misses
    run = 0
    worst = 0
    for i in range(n):
        if i in seen:
            run = 0
        else:
            run += 1
            worst = max(worst, run)
    ps = peer_stats() or {}
    log("RESULT %s brx: peer sent=%d err=%d | received=%d (%.1f%%) | longest gap=%d frames"
        % (label, ps.get('burst_sent', -1), ps.get('burst_err', -1), len(seen),
           100 * len(seen) / n, worst))


def test_btx(label, n=N, gap=GAP_MS):
    peer_reset()
    err = 0
    cs = [time.ticks_ms(), 0]
    t = time.ticks_ms()
    for i in range(n):
        r, _ms = send(BCAST, b'X' + struct.pack('<H', i), False)
        if r is None:
            err += 1
        color_tick(cs)
        t = time.ticks_add(t, gap)
        while time.ticks_diff(t, time.ticks_ms()) > 0:
            drain()
            service()
            time.sleep_ms(1)
    wait_ms(500)
    ps = peer_stats() or {}
    log("RESULT %s btx: sent=%d err=%d | peer counted=%d (%.1f%%)"
        % (label, n, err, ps.get('x', -1), 100 * ps.get('x', -1) / n))


def test_bulk(label, nbytes=BULK_BYTES):
    peer_reset()
    chunks = (nbytes + CHUNK - 1) // CHUNK
    pad = bytes(CHUNK)
    first = 0
    retried = 0
    failed = 0
    cs = [time.ticks_ms(), 0]
    t0 = time.ticks_ms()
    for i in range(chunks):
        msg = b'D' + struct.pack('<H', i) + pad
        ok = False
        for attempt in range(3):
            r, _ms = send(peer, msg)
            if r:
                ok = True
                if attempt == 0:
                    first += 1
                else:
                    retried += 1
                break
        if not ok:
            failed += 1
        drain()
        service()
        color_tick(cs)
    dt = time.ticks_diff(time.ticks_ms(), t0)
    wait_ms(300)
    ps = peer_stats() or {}
    log("RESULT %s bulk: %d chunks in %d ms = %.1f KB/s | first-try=%d retried=%d "
        "failed=%d | peer distinct=%d"
        % (label, chunks, dt, nbytes / 1024 / (dt / 1000), first, retried, failed,
           ps.get('d', -1)))


def splat_line(label):
    if group is None:
        return
    log("SPLATS %s: connected=%d/%d connects=%s drops=%s write_failures=%d"
        % (label, group.connected_count, group.count,
           [l.connects for l in hub.links], [l.drops for l in hub.links],
           group.write_failures))


def enow_line(label):
    try:
        log("ENOW %s: stats(tx_pkts, tx_responses, tx_failures, rx_packets, rx_dropped)=%s"
            % (label, e.stats()))
    except Exception as ex:
        log("ENOW %s: %r" % (label, ex))


def run_tests(label):
    log("=== phase %s" % label)
    enow_line(label + " before")
    test_ping(label)
    test_brx(label)
    test_btx(label)
    test_bulk(label)
    splat_line(label)
    enow_line(label + " after")
    mem(label)


def soak(label, secs):
    log("=== soak %s: %d s, ping every 100 ms + color each second" % (label, secs))
    peer_reset()
    sent = 0
    acked = 0
    echoes = set()

    def rx(mac, msg):
        if mac == peer and msg[:1] == b'R':
            echoes.add(struct.unpack('<H', msg[1:3])[0])

    cs = [time.ticks_ms(), 0]
    end = time.ticks_add(time.ticks_ms(), secs * 1000)
    nxt = time.ticks_ms()
    report = time.ticks_add(time.ticks_ms(), 60000)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        now = time.ticks_ms()
        if time.ticks_diff(now, nxt) >= 0:
            r, _ms = send(peer, b'P' + struct.pack('<H', sent & 0xFFFF))
            sent += 1
            if r:
                acked += 1
            nxt = time.ticks_add(nxt, 100)
        if time.ticks_diff(now, report) >= 0:
            report = time.ticks_add(report, 60000)
            log("soak: sent=%d acked=%d echoes=%d" % (sent, acked, len(echoes)))
            splat_line("soak")
        drain(rx)
        service()
        color_tick(cs)
        time.sleep_ms(1)
    wait_ms(500, rx)
    log("RESULT %s soak: pings=%d acked=%d (%.1f%%) echoes back=%d (%.1f%%)"
        % (label, sent, acked, 100 * acked / max(sent, 1), len(echoes),
           100 * len(echoes) / max(sent, 1)))
    splat_line(label + " soak end")
    mem(label + " soak")


# ─── BLE ───────────────────────────────────────

import ubluetooth
ble = ubluetooth.BLE()
ble.active(True)
mem("ble active")
import splat_link
from splat_hub import SplatHub
from splat_api import SplatGroup
splat_link.CONN_INTERVAL_US = CONN_INTERVAL_US
mem("splat modules")


def connect(count):
    global hub, group
    hub = SplatHub(count)
    group = SplatGroup(hub)
    route = hub._irq

    def spy(event, data):
        if event == 27:
            h, itvl, lat, sup, st = data
            log("BLE conn update handle=%d interval=%.2f ms latency=%d supervision=%d ms"
                % (h, itvl * 1.25, lat, sup * 10))
        route(event, data)
    hub._ble.irq(spy)
    end = time.ticks_add(time.ticks_ms(), CONNECT_WAIT_S * 1000)
    while group.connected_count < count and time.ticks_diff(end, time.ticks_ms()) > 0:
        group.poll()
        drain()
        time.sleep_ms(1)
    log("connected %d/%d Splats" % (group.connected_count, count))
    wait_ms(1000)


def disconnect():
    global hub, group
    if hub is not None:
        hub.close_all()
        h = hub
        hub = None
        group = None
        end = time.ticks_add(time.ticks_ms(), 2000)
        while time.ticks_diff(end, time.ticks_ms()) > 0:
            drain()
            time.sleep_ms(1)
        del h
        gc.collect()


try:
    for n in SPLAT_COUNTS:
        connect(n)
        run_tests("splats=%d" % n)
        if n == SPLAT_COUNTS[-1] and SOAK_S:
            soak("splats=%d" % n, SOAK_S)
        disconnect()
    run_tests("ble-idle")
    ble.active(False)
    wait_ms(500)
    mem("ble off")
    run_tests("ble-off")
finally:
    disconnect()
    log("DONE")
