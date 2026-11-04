"""
coex_peer.py -- ESP-NOW responder for coex_bench.py
====================================================
Run on a MockWand (or any ESP32 with espnow):
    python3 -m mpremote connect $PEER resume run coex_peer.py
Uses the board's own antenna setting (espnow_manager._configure_antenna()).

Frames (first byte is the kind):
  H            broadcast hello        -> unicast 'h'
  P seq(2)     ping                   -> unicast 'R' seq (sync, ACK counted)
  B n(2) gap [size]  broadcast burst  -> n broadcasts 'b' seq, gap ms apart,
                                         padded to size bytes (default 3)
  X seq(2)     bench broadcast        counted (distinct seqs)
  D seq(2) ..  bulk chunk             counted (distinct seqs)
  Z            reset counters
  S            stats request          -> unicast 'S' + "k=v,..." text
"""

import time
import struct
import network
import espnow

try:
    import espnow_manager
    espnow_manager._configure_antenna()
    print("peer: antenna from espnow_manager, EXTERNAL_ANTENNA=%s"
          % espnow_manager.EXTERNAL_ANTENNA)
except Exception as ex:
    print("peer: antenna left as is (%r)" % ex)

BCAST = b'\xff' * 6

sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.disconnect()
sta.config(channel=1)
e = espnow.ESPNow()
e.active(False)
e.config(rxbuf=4096)
e.active(True)
try:
    e.add_peer(BCAST)
except OSError:
    pass
print("peer: MAC %s channel %d" % (':'.join('%02X' % b for b in sta.config('mac')),
                                   sta.config('channel')))

peers = set()
seen_x = bytearray(512)      # bitmaps, 4096 seqs
seen_d = bytearray(512)
c = {}


def reset():
    for i in range(512):
        seen_x[i] = 0
        seen_d[i] = 0
    for k in ('ping', 'echo_ok', 'echo_fail', 'x', 'x_dup', 'd', 'd_dup',
              'burst_sent', 'burst_err'):
        c[k] = 0


def mark(bm, seq):
    i = seq & 4095
    b = 1 << (i & 7)
    if bm[i >> 3] & b:
        return False
    bm[i >> 3] |= b
    return True


def send_retry(mac, msg, sync):
    for _ in range(20):
        try:
            return e.send(mac, msg, sync)
        except OSError:
            time.sleep_ms(2)
    return None


reset()
while True:
    mac, msg = e.irecv(0)
    if msg:
        mac = bytes(mac)
        if mac not in peers:
            try:
                e.add_peer(mac)
            except OSError:
                pass
            peers.add(mac)
        k = msg[0]
        if k == 0x50:                                   # P
            c['ping'] += 1
            if send_retry(mac, b'R' + bytes(msg[1:3]), True):
                c['echo_ok'] += 1
            else:
                c['echo_fail'] += 1
        elif k == 0x58:                                 # X
            if mark(seen_x, struct.unpack('<H', msg[1:3])[0]):
                c['x'] += 1
            else:
                c['x_dup'] += 1
        elif k == 0x44:                                 # D
            if mark(seen_d, struct.unpack('<H', msg[1:3])[0]):
                c['d'] += 1
            else:
                c['d_dup'] += 1
        elif k == 0x42:                                 # B
            n = struct.unpack('<H', msg[1:3])[0]
            gap = msg[3]
            pad = bytes(max(0, (msg[4] if len(msg) > 4 else 3) - 3))
            time.sleep_ms(200)
            t = time.ticks_ms()
            for i in range(n):
                if send_retry(BCAST, b'b' + struct.pack('<H', i) + pad, False) is None:
                    c['burst_err'] += 1
                else:
                    c['burst_sent'] += 1
                t = time.ticks_add(t, gap)
                d = time.ticks_diff(t, time.ticks_ms())
                if d > 0:
                    time.sleep_ms(d)
        elif k == 0x48:                                 # H
            send_retry(mac, b'h', True)
        elif k == 0x5A:                                 # Z
            reset()
        elif k == 0x53:                                 # S
            s = ','.join('%s=%d' % (kk, c[kk]) for kk in sorted(c))
            send_retry(mac, b'S' + s.encode(), True)
    time.sleep_ms(1)
