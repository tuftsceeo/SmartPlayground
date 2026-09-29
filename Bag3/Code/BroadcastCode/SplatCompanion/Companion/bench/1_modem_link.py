"""
1_modem_link.py -- bench stage 1: hub <-> ESPNowModem UART link
================================================================
Run on the hub: mpremote connect $HUB resume run bench/1_modem_link.py
Needs on the hub: /hubtype.txt, /lib/hubtype.py, /lib/espnow_manager.py,
/lib/eum_proto.py. The modem must be flashed and powered.

Sets the UART pins from hubtype.py, brings the link up, broadcasts
["turnred"] every second, prints every received message, and prints the
link counters every 10 s. PASS after 10 broadcasts the modem accepted.
Ctrl-C to stop.
"""

import time
import espnow_manager
from hubtype import HUB_CONFIG

BROADCAST_EVERY_MS = 1000
STATS_EVERY_MS = 10000
PASS_AFTER = 10

espnow_manager.UART_TX = HUB_CONFIG["modem_uart_tx"]
espnow_manager.UART_RX = HUB_CONFIG["modem_uart_rx"]
print("bench 1: UART%d tx=%d rx=%d @%d" % (espnow_manager.UART_ID,
      espnow_manager.UART_TX, espnow_manager.UART_RX, espnow_manager.UART_BAUD))

mgr = espnow_manager.ESPNowManager()
try:
    mgr.init()
except OSError as e:
    print("FAIL: no reply from the modem (%s) -- check TX/RX are crossed,"
          " GND shared, and the modem is running ESPNowModem/main.py" % e)
    raise
print("modem MAC", espnow_manager.get_own_mac())

next_bcast = time.ticks_ms()
next_stats = time.ticks_add(time.ticks_ms(), STATS_EVERY_MS)
sent = ok_count = 0
passed = False
while True:
    now = time.ticks_ms()
    if time.ticks_diff(now, next_bcast) >= 0:
        ok = mgr.broadcast(["turnred"])
        sent += 1
        if ok:
            ok_count += 1
        print("tx #%d ok=%s" % (sent, ok))
        next_bcast = time.ticks_add(now, BROADCAST_EVERY_MS)
        if not passed and sent == PASS_AFTER:
            passed = True
            if ok_count == sent:
                print("PASS: %d/%d broadcasts accepted by the modem" % (ok_count, sent))
            else:
                print("FAIL: only %d/%d broadcasts accepted" % (ok_count, sent))
    if time.ticks_diff(now, next_stats) >= 0:
        print("stats", mgr.link_stats())
        next_stats = time.ticks_add(now, STATS_EVERY_MS)
    msg_type, data, mac = mgr.poll()
    if msg_type is not None:
        print("rx", msg_type, data, mac)
    time.sleep_ms(1)
