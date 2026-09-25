"""
test_link.py -- EUM bench check, run on the host board
=======================================================
Requires host/lib/ (espnow_manager.py, eum_proto.py) on the board and a
modem running modem/main.py on UART1 (tx=43, rx=44).

Broadcasts ["turnred"] every second, prints every received message, and
prints link counters every 10 s. Ctrl-C to stop.
"""

import time
from espnow_manager import ESPNowManager, get_own_mac

BROADCAST_EVERY_MS = 1000
STATS_EVERY_MS = 10000

mgr = ESPNowManager()
mgr.init()
print("host sees modem MAC", get_own_mac())

next_bcast = time.ticks_ms()
next_stats = time.ticks_add(time.ticks_ms(), STATS_EVERY_MS)
n_sent = 0
while True:
    now = time.ticks_ms()
    if time.ticks_diff(now, next_bcast) >= 0:
        ok = mgr.broadcast(["turnred"])
        n_sent += 1
        print("tx #%d broadcast ok=%s" % (n_sent, ok))
        next_bcast = time.ticks_add(now, BROADCAST_EVERY_MS)
    if time.ticks_diff(now, next_stats) >= 0:
        print("stats", mgr.link_stats())
        next_stats = time.ticks_add(now, STATS_EVERY_MS)
    msg_type, data, mac = mgr.poll()
    if msg_type is not None:
        print("rx", msg_type, data, mac, "rssi", mgr.get_rssi(mac))
    time.sleep_ms(1)
