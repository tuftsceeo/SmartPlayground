"""analyze_t2.py LOG -- per-phase distribution timing and scan completeness."""
import json
import sys
from collections import OrderedDict, defaultdict

rows = [json.loads(l) for l in open(sys.argv[1])]
phases = OrderedDict()
for r in rows:
    phases.setdefault(r["ph"], []).append(r)
for ph, rs in phases.items():
    if ph in ("init", "end"):
        continue
    print("\n==", ph)
    starts = {}
    for r in rs:
        if "sent" in r and r["sent"].get("cmd") == "fleet.distribute":
            starts[r["c"]] = r["ta"]
            print("  %s distribute %s to %d at %.1f" % (r["c"], r["sent"]["slug"], len(r["sent"]["macs"]), r["ta"]))
        if "rx" in r:
            o = r["rx"]
            if o.get("type") == "dist_progress":
                print("    %s %-18s ok=%-5s why=%-12s +%.1f s" % (
                    r["c"], o.get("mac"), o.get("ok"), o.get("why"), r["ta"] - starts.get(r["c"], r["ta"])))
            elif o.get("type") == "dist_done":
                print("    %s DONE %s/%s +%.1f s" % (r["c"], o.get("done"), o.get("total"),
                                                   r["ta"] - starts.get(r["c"], r["ta"])))
            elif o.get("type") == "error":
                print("    %s ERROR %s" % (r["c"], o))
    finds = [r for r in rs if "sent" in r and r["sent"].get("cmd") == "fleet.find"]
    if finds:
        print("  finds sent: %d (%.2f/s)" % (len(finds), len(finds) / max(1, rs[-1]["ta"] - rs[0]["ta"])))
    scans = defaultdict(list)
    reps = defaultdict(list)
    for r in rs:
        if "scan_start" in r:
            scans[r["c"]].append(r["ta"])
        elif "rx" in r and r["rx"].get("type") == "status_report":
            reps[r["c"]].append((r["ta"], r["rx"]["mac"]))
    for c, ts in scans.items():
        counts = [len({m for ta, m in reps[c] if t <= ta < t + 6}) for t in ts]
        print("  %s scans during phase: %s" % (c, counts))
