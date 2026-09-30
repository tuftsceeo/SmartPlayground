# Link test sender: 300 numbered broadcasts per condition.
#  a: Splats disconnected (no BLE traffic)
#  b: 4 Splats connected; every 5th packet sent right after a color write to all 4
#  c: 4 Splats connected, polled only (keepalive/readSwitches traffic)
import time, espnow_manager
mgr = espnow_manager.ESPNowManager()
mgr.init()
print("LINK0", mgr.link_stats())

def burst(tag, work=None, n=300, gap=20):
    t0 = time.ticks_ms()
    fails = 0
    for i in range(n):
        if work:
            work(i)
        if not mgr.broadcast({"type": "lt", "t": tag, "n": i}):
            fails += 1
        time.sleep_ms(gap)
    print("BURST", tag, "sent", n, "fails", fails, "ms", time.ticks_diff(time.ticks_ms(), t0))

burst("a")
from splat_hub import SplatHub
from splat_api import SplatGroup
hub = SplatHub(4)
sp = SplatGroup(hub)
try:
    t0 = time.ticks_ms()
    while sp.connected_count < 4 and time.ticks_diff(time.ticks_ms(), t0) < 60000:
        sp.poll()
        time.sleep_ms(1)
    print("SPLATS connected", sp.connected_count, "after", time.ticks_diff(time.ticks_ms(), t0))

    def work_b(i):
        sp.poll()
        if i % 5 == 0:
            sp.color("turnred" if (i // 5) % 2 else "turnoff")

    burst("b", work_b)
    burst("c", lambda i: sp.poll())
    sp.off()
finally:
    hub.close_all()
for _ in range(5):
    mgr.broadcast({"type": "lt", "t": "end", "n": 0})
    time.sleep_ms(50)
print("LINK1", mgr.link_stats())
