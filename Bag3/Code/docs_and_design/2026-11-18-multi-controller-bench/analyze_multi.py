"""analyze_multi.py LOG -- per controller, per scan: devices heard in the 6 s after it."""
import json
import sys
from collections import OrderedDict, defaultdict

rows = [json.loads(l) for l in open(sys.argv[1])]


def slot(mac):
    return int(mac[-2:], 16) % 16


def is_rep(r):
    return "rx" in r and r["rx"].get("type") == "status_report"


allmacs = sorted({r["rx"]["mac"] for r in rows if is_rep(r)}, key=slot)
print("devices seen overall:", len(allmacs))
for r in rows:
    if "rx" in r and r["rx"].get("type") in ("identity", "error"):
        print(" ", r["c"], r["ph"], json.dumps(r["rx"])[:160])

phases = OrderedDict()
for r in rows:
    phases.setdefault(r["ph"], []).append(r)
for ph, rs in phases.items():
    if ph in ("init", "end"):
        continue
    reps = defaultdict(list)    # controller -> [(ta, mac)]
    starts = defaultdict(list)  # controller -> [ta]
    for r in rs:
        if is_rep(r):
            reps[r["c"]].append((r["ta"], r["rx"]["mac"]))
        elif "scan_start" in r:
            starts[r["c"]].append(r["ta"])
    allstarts = sorted(t for v in starts.values() for t in v)
    print("\n== %s: %d scans total" % (ph, len(allstarts)))
    for c in sorted(starts):
        counts = []
        own_slot = defaultdict(lambda: [0, 0])
        for t in starts[c]:
            seen = {m for ta, m in reps[c] if t <= ta < t + 6.0}
            counts.append(len(seen))
            for m in allmacs:
                own_slot[slot(m)][1] += 1
                own_slot[slot(m)][0] += m in seen
        cs = sorted(counts)
        print("  %-6s %2d scans: min %2d median %2d max %2d  %s" % (
            c, len(counts), cs[0], cs[len(cs) // 2], cs[-1], counts))
        print("         per-slot listed:", {k: "%.0f%%" % (100.0 * a / b) for k, (a, b) in sorted(own_slot.items())})
    # do controllers hear replies to other controllers' polls? fraction of
    # reports heard by c that came while c had no scan of its own in the last 6 s
    for c in sorted(reps):
        foreign = sum(1 for ta, m in reps[c] if not any(t <= ta < t + 6.0 for t in starts[c]))
        print("  %-6s reports outside its own windows (forwarded? should be 0): %d" % (c, foreign))
