"""
code_host.py -- ESP-NOW code server bench script (EUM host)
===========================================================
Install as main.py on the EUM host, with host/lib/ and code_sender.py.
Serves <fs_root>/games/<slug>.py to wands running MockWandEUM firmware.

TRIGGER_SLUG set: after STARTUP_MS, broadcasts {"type":"getcode"} (the
MockWandEUM REMOTE_GETCODE bench hook) TRIGGER_RUNS times, one after each
finished transfer, then prints a summary. Before each trigger after the
first it broadcasts stop, so the game launched by the previous transfer
exits and the wand is back in its idle loop. None: serve on request only
(real getcode taps).
"""

import time
from espnow_manager import ESPNowManager
from code_sender import CodeSender

TRIGGER_SLUG = None          # e.g. "bigtest"
TRIGGER_RUNS = 3
STARTUP_MS = 3000
RUN_GAP_MS = 4000            # after a result, before the next trigger
# A successful transfer launches the game, which holds the wand's main loop
# until it exits. Games exit on "stop", so one is broadcast this long before
# each trigger after the first.
STOP_LEAD_MS = 1500
RUN_TIMEOUT_MS = 60000
STATS_EVERY_MS = 30000

mgr = ESPNowManager()
mgr.init()
sender = CodeSender(mgr)
print("code_host: serving %s" % sender.games_dir)
print("mem", mgr.mem_stats())

results = []
next_trigger = time.ticks_add(time.ticks_ms(), STARTUP_MS) if TRIGGER_SLUG else None
waiting_since = None
next_stats = time.ticks_add(time.ticks_ms(), STATS_EVERY_MS)
last_seen = None

while True:
    now = time.ticks_ms()
    mt, data, mac = mgr.poll()
    if mt is not None and not sender.handle(mt, data, mac):
        if mt == "raw" and isinstance(data, dict) and data.get("type") == "enx_result":
            print("wand result", data)
    if sender.last_result is not None and sender.last_result is not last_seen:
        last_seen = sender.last_result
        results.append(last_seen)
        print("mem after run %d" % len(results), mgr.mem_stats())
        waiting_since = None
        if TRIGGER_SLUG and len(results) < TRIGGER_RUNS:
            next_trigger = time.ticks_add(now, RUN_GAP_MS)
        elif TRIGGER_SLUG:
            next_trigger = None
            print("code_host: %d runs done" % len(results))
            for i, r in enumerate(results):
                print("  run %d: ok=%s %d B %d ms (%.1f KB/s) gets=%d "
                      "frames=%d send_fail=%d %s"
                      % (i + 1, r["ok"], r["bytes"], r["ms"],
                         r["bytes"] / 1024 / max(r["ms"], 1) * 1000,
                         r["gets"], r["frames"], r["send_fail"], r["why"]))
            print("stats", mgr.link_stats())
    if next_trigger is not None and time.ticks_diff(now, next_trigger) >= 0:
        if results:
            mgr.broadcast_stop()
            time.sleep_ms(STOP_LEAD_MS)
        print("code_host: trigger run %d getcode %r"
              % (len(results) + 1, TRIGGER_SLUG))
        mgr.broadcast({"type": "getcode", "slug": TRIGGER_SLUG})
        next_trigger = None
        waiting_since = now
    if waiting_since is not None and time.ticks_diff(now, waiting_since) > RUN_TIMEOUT_MS:
        print("code_host: run %d timed out waiting for the wand" % (len(results) + 1))
        # Recorded by the result branch above on the next pass.
        sender.last_result = {"ok": False, "bytes": 0, "ms": RUN_TIMEOUT_MS,
                              "gets": 0, "frames": 0, "send_fail": 0,
                              "why": "host timeout"}
        waiting_since = None
    if time.ticks_diff(now, next_stats) >= 0:
        print("stats", mgr.link_stats())
        next_stats = time.ticks_add(now, STATS_EVERY_MS)
    time.sleep_ms(1)
