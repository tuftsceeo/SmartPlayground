"""
coex_peer_m1.py -- ESP-NOW responder for coex_bench_m1.py
==========================================================
Run on a MockWand:
    python3 -m mpremote connect $PEER resume run coex_peer_m1.py
Reads /m1/cfg.txt if present: "setup=raw" (default; channel 1, rxbuf 4096, as
coex_peer.py) or "setup=mgr" (espnow_manager.ESPNowManager().init(), as the wand).

Frames as coex_peer.py (H P B X D Z S), plus:
  P seq(2)       ping; echo 'R' seq sent sync or async per the E setting.
                 Per ping the peer records: pickup ms, echo send-call us, ACK.
  E mode         0 = echo with sync send (default), 1 = async send
  L on           BLE active(on); answers 'l' + '0'/'1' (BLE active state, -1 on error)
  M pm           WLAN power-management value; 255 = read only. Answers 'm' + value
  Q label        print the per-ping records as PEERPING lines
"""

import time
import struct
import network
import espnow
from array import array

try:
    import espnow_manager
    espnow_manager._configure_antenna()
    print("peer: antenna from espnow_manager, EXTERNAL_ANTENNA=%s"
          % espnow_manager.EXTERNAL_ANTENNA)
except Exception as ex:
    print("peer: antenna left as is (%r)" % ex)

BCAST = b'\xff' * 6
PMAX = 400


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

mgr = None
if SETUP == 'mgr':
    mgr = espnow_manager.ESPNowManager()
    mgr.init()
    e = mgr.enow
    sta = network.WLAN(network.STA_IF)
else:
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


def _pm():
    try:
        return sta.config('pm')
    except Exception as ex:
        return -1


print("peer: setup=%s MAC %s channel %d pm=%s"
      % (SETUP, ':'.join('%02X' % b for b in sta.config('mac')),
         sta.config('channel'), _pm()))

peers = set()
seen_x = bytearray(512)
seen_d = bytearray(512)
c = {}
p_seq = array('H', bytes(2 * PMAX))
p_rx = array('I', bytes(4 * PMAX))
p_us = array('I', bytes(4 * PMAX))
p_ack = array('b', bytes(PMAX))
pn = 0
t_first = 0
echo_sync = True
ble = None


def reset():
    global pn
    for i in range(512):
        seen_x[i] = 0
        seen_d[i] = 0
    for k in ('ping', 'echo_ok', 'echo_fail', 'x', 'x_dup', 'd', 'd_dup',
              'burst_sent', 'burst_err'):
        c[k] = 0
    pn = 0


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


def dump(label):
    print("PEERPING-BEGIN %s n=%d" % (label, pn))
    for i in range(pn):
        print("PEERPING %s %d rx_ms=%d echo_us=%d ack=%d"
              % (label, p_seq[i], p_rx[i], p_us[i], p_ack[i]))
        time.sleep_ms(1)
    print("PEERPING-END %s" % label)


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
            seq = struct.unpack('<H', msg[1:3])[0]
            now = time.ticks_ms()
            if pn == 0:
                t_first = now
            u0 = time.ticks_us()
            r = send_retry(mac, b'R' + bytes(msg[1:3]), echo_sync)
            us = time.ticks_diff(time.ticks_us(), u0)
            if r:
                c['echo_ok'] += 1
            else:
                c['echo_fail'] += 1
            if pn < PMAX:
                p_seq[pn] = seq
                p_rx[pn] = time.ticks_diff(now, t_first)
                p_us[pn] = us
                p_ack[pn] = -1 if r is None else (1 if r else 0)
                pn += 1
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
        elif k == 0x45:                                 # E
            echo_sync = msg[1] == 0
            print("peer: echo sync=%s" % echo_sync)
            send_retry(mac, b'e' + bytes([msg[1]]), True)
        elif k == 0x4C:                                 # L
            res = -1
            try:
                if ble is None:
                    import ubluetooth
                    ble = ubluetooth.BLE()
                ble.active(bool(msg[1]))
                res = 1 if ble.active() else 0
            except Exception as ex:
                print("peer: BLE error %r" % ex)
            print("peer: BLE active=%d" % res)
            send_retry(mac, b'l' + bytes([res & 0xFF]), True)
        elif k == 0x4D:                                 # M
            if msg[1] != 255:
                try:
                    sta.config(pm=msg[1])
                except Exception as ex:
                    print("peer: pm set error %r" % ex)
            v = _pm()
            print("peer: pm=%s" % v)
            send_retry(mac, b'm' + bytes([v & 0xFF]), True)
        elif k == 0x51:                                 # Q
            dump(bytes(msg[1:]).decode())
    time.sleep_ms(1)
