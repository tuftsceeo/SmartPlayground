"""
coex_bench_m1.py -- ESP-NOW unicast isolation on the C6 (M1, question 2)
=========================================================================
Run on the hub wand after a plain reset, main.py renamed away:
    python3 -m mpremote connect $HUB resume run coex_bench_m1.py
Needs on the hub: /m1/cfg.txt, and for plans that connect Splats /m1/splat_link.py,
splat_hub.py, splat_api.py, ble_splat.py. Peer runs coex_peer_m1.py.

/m1/cfg.txt (space separated key=value):
  setup=raw   channel 1, rxbuf 8192, as coex_bench.py (default)
  setup=mgr   espnow_manager.ESPNowManager().init(), as the wand
  plan=A      a key of PLANS below

Each ping test sends N unicast pings GAP ms apart and logs, per ping, the send-call
time (us), the send result, and the echo arrival (us after the send started), then asks
the peer to print its own per-ping records (PEERPING lines in the peer's log).
RESULT lines keep coex_bench.py's ping format and append the configuration.

Steps:
  ('ping', gap_ms, n, hub_sync, echo_sync)
  ('bulk',)
  ('pm', 'read' | 'none' | 'perf')       WLAN power management, both boards
  ('peer_ble', 0|1)                      BLE active on the peer
  ('hub_ble', 0|1)                       BLE active on the hub (no links)
  ('splats', n, 'default'|'fixed30'|'fixed100')   n connected Splats; 0 disconnects
  ('mem',)
"""

import sys
sys.path.insert(0, '/m1')

import gc
import time
import struct
import network
import espnow
import esp32
from array import array

BCAST = b'\xff' * 6
CHUNK = 245
BULK_BYTES = 36 * 1024
N_FAST = 300
N_SLOW = 100
ECHO_WAIT_MS = 10000
PEER_DUMP_MS = 3000
CONNECT_WAIT_S = 90
SPLAT_MACS = None            # None = first Splats found by name, or a list of MAC strings
INTERVALS = {'default': None, 'fixed30': (30000, 30000), 'fixed100': (100000, 100000)}

# XIAO ESP32-C6: GPIO3 = 0 enables the RF switch, GPIO14 selects onboard (0) or
# external (1). Both bench wands have u.FL antennas fitted.
EXTERNAL_ANTENNA = True


def ping(gap, hs=True, es=True):
    return ('ping', gap, N_FAST if gap <= 50 else N_SLOW, hs, es)


PLANS = {
    # BLE never activated on either board
    'A': [('mem',), ('pm', 'read'),
          ping(20), ping(20, True, False), ping(20, False, True),
          ping(200), ping(200, True, False), ping(200, False, True), ('bulk',),
          ('pm', 'none'), ping(20), ping(200), ('bulk',)],
    # BLE active on the peer only
    'B': [('mem',), ('peer_ble', 1), ('pm', 'read'),
          ping(20), ping(200), ('bulk',)],
    # BLE and 2 Splats on the hub; peer BLE off, then on
    'C': [('mem',), ('hub_ble', 1), ('splats', 2, 'default'),
          ping(20), ping(200), ping(20, True, False), ('bulk',),
          ('splats', 2, 'fixed30'), ping(20), ping(200), ('bulk',),
          ('splats', 2, 'fixed100'), ping(20), ping(200),
          ('splats', 2, 'default'), ('peer_ble', 1), ping(20), ping(200), ('bulk',),
          ('splats', 0), ping(20), ping(200),
          ('hub_ble', 0), ping(20), ping(200)],
}

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


def _cfg():
    d = {}
    try:
        with open('/m1/cfg.txt') as f:
            for kv in f.read().split():
                if '=' in kv:
                    k, v = kv.split('=')
                    d[k] = v
    except OSError:
        pass
    return d


CFG = _cfg()
SETUP = CFG.get('setup', 'raw')
PLAN = CFG.get('plan', 'A')


def _antenna():
    from machine import Pin
    Pin(3, Pin.OUT).value(0)
    time.sleep_ms(100)
    Pin(14, Pin.OUT).value(1 if EXTERNAL_ANTENNA else 0)


# ─── ESP-NOW first ─────────────────────────────

mem("start")
if SETUP == 'mgr':
    import espnow_manager
    mgr = espnow_manager.ESPNowManager()
    mgr.init()
    e = mgr.enow
    sta = network.WLAN(network.STA_IF)
else:
    _antenna()
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    sta.disconnect()
    sta.config(channel=1)
    e = espnow.ESPNow()
    e.config(rxbuf=8192)
    e.active(True)
try:
    e.add_peer(BCAST)
except OSError:
    pass


def pm_now():
    try:
        return sta.config('pm')
    except Exception:
        return -1


log("ESP-NOW up: setup=%s plan=%s MAC %s channel %d pm=%s"
    % (SETUP, PLAN, ':'.join('%02X' % b for b in sta.config('mac')),
       sta.config('channel'), pm_now()))
mem("espnow")

color_state = [time.ticks_ms(), 0]
ble = None
hub = None
group = None
splat_mods = None
ctx = {'hb': 0, 'pb': 0, 's': 0, 'iv': 'na'}


def service():
    if group is not None:
        group.poll()
        color_service()


def drain(on_rx=None):
    while True:
        mac, msg = e.irecv(0)
        if not msg:
            return
        if on_rx is not None:
            on_rx(bytes(mac), bytes(msg))


def wait_ms(ms, on_rx=None):
    end = time.ticks_add(time.ticks_ms(), ms)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        drain(on_rx)
        service()
        time.sleep_ms(1)


def send(mac, msg, sync=True):
    """Returns (result, us spent in send()); result None after 20 OSErrors."""
    t = time.ticks_us()
    for _ in range(20):
        try:
            r = e.send(mac, msg, sync)
            return r, time.ticks_diff(time.ticks_us(), t)
        except OSError:
            drain()
            time.sleep_ms(2)
    return None, time.ticks_diff(time.ticks_us(), t)


# ─── Find the peer ─────────────────────────────

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
    log("FAIL: no peer answered (is coex_peer_m1.py running?)")
    raise SystemExit
peer = found[0]
e.add_peer(peer)
log("peer %s" % ':'.join('%02X' % b for b in peer))


def peer_cmd(msg, kind):
    """Send a control frame, return the reply payload (bytes) or None."""
    got = []

    def rx(mac, m):
        if mac == peer and m[:1] == kind:
            got.append(m[1:])
    for _ in range(5):
        send(peer, msg)
        wait_ms(400, rx)
        if got:
            return got[0]
    return None


def peer_stats():
    r = peer_cmd(b'S', b'S')
    if r is None:
        return None
    d = {}
    for kv in r.decode().split(','):
        k, v = kv.split('=')
        d[k] = int(v)
    return d


def peer_reset():
    send(peer, b'Z')
    wait_ms(50)


# ─── Ping test ─────────────────────────────────

def test_ping(gap, n, hs, es):
    label = "hb%d_pb%d_s%d_%s_pm%s_g%d_h%s_e%s" % (
        ctx['hb'], ctx['pb'], ctx['s'], ctx['iv'], pm_now(), gap,
        'S' if hs else 'A', 'S' if es else 'A')
    log("=== ping %s" % label)
    peer_cmd(b'E' + bytes([0 if es else 1]), b'e')
    peer_reset()
    sent_us = array('i', bytes(4 * n))
    ack = array('b', bytes(n))
    echo_us = array('i', bytes(4 * n))
    for i in range(n):
        echo_us[i] = -1
    start_ticks = array('i', bytes(4 * n))
    got = [0]

    def rx(mac, msg):
        if mac == peer and msg[:1] == b'R':
            s = struct.unpack('<H', msg[1:3])[0]
            if s < n and echo_us[s] < 0 and start_ticks[s]:
                echo_us[s] = time.ticks_diff(time.ticks_us(), start_ticks[s])
                got[0] += 1

    try:
        before = e.stats()
    except Exception:
        before = None
    t = time.ticks_ms()
    for i in range(n):
        start_ticks[i] = time.ticks_us() | 1
        r, us = send(peer, b'P' + struct.pack('<H', i), hs)
        sent_us[i] = us
        ack[i] = -1 if r is None else (1 if r else 0)
        if not hs and r:
            ack[i] = 2
        drain(rx)
        t = time.ticks_add(t, gap)
        while time.ticks_diff(t, time.ticks_ms()) > 0:
            drain(rx)
            service()
            time.sleep_ms(1)
    end = time.ticks_add(time.ticks_ms(), ECHO_WAIT_MS)
    while got[0] < n and time.ticks_diff(end, time.ticks_ms()) > 0:
        drain(rx)
        service()
        time.sleep_ms(1)
    try:
        after = e.stats()
    except Exception:
        after = None
    send(peer, b'Q' + label.encode())
    ps = peer_stats() or {}
    for i in range(n):
        log("PING %s %d send_us=%d ack=%d echo_us=%d" % (label, i, sent_us[i], ack[i], echo_us[i]))
        time.sleep_ms(1)
    wait_ms(PEER_DUMP_MS)
    send_ms = [sent_us[i] / 1000 for i in range(n)]
    rtts = [echo_us[i] / 1000 for i in range(n) if echo_us[i] >= 0]
    acked = sum(1 for i in range(n) if ack[i] == 1)
    nack = sum(1 for i in range(n) if ack[i] == 0)
    err = sum(1 for i in range(n) if ack[i] == -1)
    queued = sum(1 for i in range(n) if ack[i] == 2)
    log("RESULT %s ping: sent=%d acked=%d nack=%d err=%d queued=%d | peer got=%d echo_ok=%d "
        "echo_fail=%d | echoes back=%d | send ms p50=%.1f p95=%.1f max=%.1f | "
        "rtt ms p50=%d p95=%d max=%d | stats before=%s after=%s"
        % (label, n, acked, nack, err, queued, ps.get('ping', -1), ps.get('echo_ok', -1),
           ps.get('echo_fail', -1), got[0], pct(send_ms, 50), pct(send_ms, 95),
           max(send_ms), pct(rtts, 50), pct(rtts, 95), max(rtts) if rtts else -1,
           before, after))


def test_bulk():
    label = "hb%d_pb%d_s%d_%s_pm%s" % (ctx['hb'], ctx['pb'], ctx['s'], ctx['iv'], pm_now())
    log("=== bulk %s" % label)
    peer_cmd(b'E' + bytes([0]), b'e')
    peer_reset()
    chunks = (BULK_BYTES + CHUNK - 1) // CHUNK
    pad = bytes(CHUNK)
    first = 0
    retried = 0
    failed = 0
    send_us = []
    t0 = time.ticks_ms()
    for i in range(chunks):
        msg = b'D' + struct.pack('<H', i) + pad
        ok = False
        for attempt in range(3):
            r, us = send(peer, msg)
            send_us.append(us / 1000)
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
        time.sleep_ms(1)
    dt = time.ticks_diff(time.ticks_ms(), t0)
    wait_ms(300)
    ps = peer_stats() or {}
    log("RESULT %s bulk: %d chunks in %d ms = %.1f KB/s | first-try=%d retried=%d "
        "failed=%d | peer distinct=%d | send ms p50=%.1f p95=%.1f max=%.1f"
        % (label, chunks, dt, BULK_BYTES / 1024 / (dt / 1000), first, retried, failed,
           ps.get('d', -1), pct(send_us, 50), pct(send_us, 95), max(send_us)))


# ─── BLE and Splats ────────────────────────────

def hub_ble(on):
    global ble, splat_mods
    if on:
        if ble is None:
            import ubluetooth
            ble = ubluetooth.BLE()
        ble.active(True)
        mem("hub ble active")
        if splat_mods is None:
            import splat_link
            import splat_hub
            import splat_api
            splat_mods = (splat_link, splat_hub, splat_api)
            mem("splat modules")
    elif ble is not None:
        ble.active(False)
        wait_ms(500)
        mem("hub ble off")
    ctx['hb'] = 1 if on else 0


def disconnect():
    global hub, group
    if hub is not None:
        hub.close_all()
        h = hub
        hub = None
        group = None
        wait_ms(2000)
        del h
        gc.collect()
    ctx['s'] = 0
    ctx['iv'] = 'na'


def connect(count, ivname):
    global hub, group
    disconnect()
    if count == 0:
        return
    splat_link, splat_hub, splat_api = splat_mods
    splat_link.CONN_INTERVAL_US = INTERVALS[ivname]
    if SPLAT_MACS:
        hub = splat_hub.SplatHub(macs=SPLAT_MACS[:count])
    else:
        hub = splat_hub.SplatHub(count)
    group = splat_api.SplatGroup(hub)
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
    log("connected %d/%d Splats interval=%s" % (group.connected_count, count, ivname))
    ctx['s'] = group.connected_count
    ctx['iv'] = ivname
    wait_ms(1000)


def splat_line():
    if group is None:
        return
    log("SPLATS: connected=%d/%d connects=%s drops=%s write_failures=%d"
        % (group.connected_count, group.count,
           [l.connects for l in hub.links], [l.drops for l in hub.links],
           group.write_failures))


def color_service():
    """Game-like load: a color write to every Splat once a second."""
    if group is None:
        return
    now = time.ticks_ms()
    if time.ticks_diff(now, color_state[0]) >= 1000:
        color_state[0] = now
        color_state[1] = (color_state[1] + 1) % 2
        group.color("turnblue" if color_state[1] else "turngreen")


def do_pm(arg):
    if arg != 'read':
        v = network.WLAN.PM_NONE if arg == 'none' else network.WLAN.PM_PERFORMANCE
        try:
            sta.config(pm=v)
        except Exception as ex:
            log("hub pm set error %r" % ex)
        r = peer_cmd(b'M' + bytes([v]), b'm')
    else:
        r = peer_cmd(b'M' + bytes([255]), b'm')
    log("PM hub=%s peer=%s" % (pm_now(), r[0] if r else None))


def run_step(st):
    k = st[0]
    if k == 'ping':
        test_ping(st[1], st[2], st[3], st[4])
    elif k == 'bulk':
        test_bulk()
    elif k == 'pm':
        do_pm(st[1])
    elif k == 'peer_ble':
        r = peer_cmd(b'L' + bytes([st[1]]), b'l')
        log("peer BLE active reply=%s" % (r[0] if r else None))
        ctx['pb'] = st[1]
    elif k == 'hub_ble':
        if st[1] == 0:
            disconnect()
        hub_ble(st[1])
    elif k == 'splats':
        connect(st[1], st[2] if len(st) > 2 else 'default')
        splat_line()
    elif k == 'mem':
        mem("step")


try:
    for st in PLANS[PLAN]:
        log("--- step %s" % (st,))
        run_step(st)
        splat_line()
    mem("end")
finally:
    disconnect()
    log("DONE")
