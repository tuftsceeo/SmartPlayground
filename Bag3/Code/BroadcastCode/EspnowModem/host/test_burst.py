"""
test_burst.py -- burst reception test, two boards
==================================================
RECEIVER: an EUM host+modem pair. SENDER: any board with an
espnow_manager.py (built-in or EUM variant); both expose the same API.

Set ROLE, flash, start the RECEIVER first, then the SENDER. The receiver
sleeps BUSY_MS after the first message arrives, simulating a host busy with
game work, then drains and checks count, order and modem overflow.

With RING_SLOTS = 128 on the modem: BURST_N = 100 should arrive complete;
BURST_N = 200 should report 72 dropped (oldest first). UNICAST_TO, when
set on the receiver, sends sync unicasts during the busy window to show
reception continues while the modem blocks on ACKs.
"""

import time
from espnow_manager import ESPNowManager

ROLE = "RECEIVER"            # or "SENDER"
BURST_N = 100
BUSY_MS = 1000
UNICAST_TO = None            # e.g. "11:22:33:44:55:66" (receiver only)


def sender():
    mgr = ESPNowManager()
    mgr.init()
    time.sleep_ms(500)
    for i in range(BURST_N):
        mgr.broadcast({"type": "burst", "n": i})
    mgr.broadcast({"type": "burst_end", "n": BURST_N})
    print("sent", BURST_N)


def receiver():
    mgr = ESPNowManager()
    mgr.init()
    mgr.drain()
    base = mgr.link_stats()["modem_rx_overflow"]
    print("waiting for burst...")
    first = None
    while first is None:
        t, d, m = mgr.poll(100)
        if t == "raw" and isinstance(d, dict) and d.get("type") == "burst":
            first = d["n"]
    if UNICAST_TO:
        mgr.add_peer(UNICAST_TO)
        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < BUSY_MS:
            mgr.send_to(UNICAST_TO, ["noop"])
            time.sleep_ms(20)
    else:
        time.sleep_ms(BUSY_MS)
    seen = [first]
    while True:
        t, d, m = mgr.poll(500)
        if t is None:
            break
        if t == "raw" and isinstance(d, dict):
            if d.get("type") == "burst":
                seen.append(d["n"])
            elif d.get("type") == "burst_end":
                break
    dropped = mgr.link_stats()["modem_rx_overflow"] - base
    in_order = seen == sorted(seen)
    print("received %d/%d in_order=%s modem_dropped=%d missing=%d"
          % (len(seen), BURST_N, in_order, dropped,
             BURST_N - len(set(seen))))
    print(mgr.link_stats())


if ROLE == "SENDER":
    sender()
else:
    receiver()
