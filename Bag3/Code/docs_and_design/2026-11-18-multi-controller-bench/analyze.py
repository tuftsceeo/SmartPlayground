"""analyze.py run.jsonl -- summarize runner.py output."""
import json
import re
import sys
from collections import OrderedDict, defaultdict

BASE, SLOT = 0.4, 0.18
rows = [json.loads(l) for l in open(sys.argv[1])]


def slot(mac):
    return int(mac[-2:], 16) % 16


def is_rep(r):
    return "rx" in r and r["rx"].get("type") == "status_report"


phases = OrderedDict()
for r in rows:
    phases.setdefault(r["ph"], []).append(r)

allmacs = {}
for r in rows:
    if is_rep(r):
        allmacs[r["rx"]["mac"]] = (r["rx"].get("kind"), r["rx"].get("role"))
print("distinct devices seen in whole run:", len(allmacs))
print("last-byte %4 values:", sorted({int(m[-2:], 16) % 4 for m in allmacs}),
      " slots used:", sorted({slot(m) for m in allmacs}))
errs = [r["rx"] for r in rows if "rx" in r and r["rx"].get("type") == "error"]
print("errors:", errs[:5], len(errs))
raws = [r for r in rows if "raw" in r]
print("raw lines:", len(raws), [r["raw"] for r in raws[:5]])

# --- baselines ---------------------------------------------------------
for ph in [p for p in phases if "base" in p]:
    rs = phases[ph]
    scans = []
    cur = None
    for r in rs:
        if "scan_start" in r:
            cur = {"t": r["ta"], "macs": defaultdict(list)}
            scans.append(cur)
        elif cur and is_rep(r):
            cur["macs"][r["rx"]["mac"]].append(round(r["ta"] - cur["t"], 2))
    counts = [len(s["macs"]) for s in scans]
    print("\n== %s: %d scans, unique per scan %s  min %d max %d mean %.1f" % (
        ph, len(scans), counts, min(counts), max(counts), sum(counts) / len(counts)))
    hits = defaultdict(int)
    late = defaultdict(list)
    for s in scans:
        for m, ls in s["macs"].items():
            hits[m] += 1
            late[m].append(ls[0])
    for m in sorted(allmacs, key=slot):
        ls = sorted(late[m])
        med = ls[len(ls) // 2] if ls else None
        print("  %s %-24s slot %2d exp %.2f  hit %2d/%d  first-lat med %s max %s" % (
            m, "%s/%s" % allmacs[m], slot(m), BASE + slot(m) * SLOT, hits[m], len(scans),
            med, ls[-1] if ls else None))
    # per slot hit rate
    by = defaultdict(lambda: [0, 0])
    for m in allmacs:
        by[slot(m)][0] += hits[m]
        by[slot(m)][1] += len(scans)
    print("  hit rate by slot:", {k: "%d/%d=%.0f%%" % (a, b, 100.0 * a / b) for k, (a, b) in sorted(by.items())})

# --- storms ------------------------------------------------------------
print("\n== storms: replies DURING polling vs AFTER the last poll")
for ph in [p for p in phases if "_storm" in p]:
    rs = phases[ph]
    sends = [r["ta"] for r in rs if "sent" in r]
    t_end = [r["ta"] for r in rs if r.get("storm_end")][0]
    last_poll = sends[-1]
    during = defaultdict(int)
    after = {}
    for r in rs:
        if not is_rep(r):
            continue
        m = r["rx"]["mac"]
        if r["ta"] < t_end:
            during[m] += 1
        elif m not in after:
            after[m] = round(r["ta"] - last_poll, 2)
    print("-- %s (%d polls): during %d devices, after %d devices" % (
        ph, len(sends), len(during), len(after)))
    by = defaultdict(lambda: [0, 0, 0])
    for m in allmacs:
        b = by[slot(m)]
        b[0] += 1
        b[1] += 1 if during.get(m) else 0
        b[2] += 1 if m in after else 0
    print("   slot: devices / answered during / answered after:",
          {k: tuple(v) for k, v in sorted(by.items())})

# --- finds -------------------------------------------------------------
print("\n== finds sent")
for r in phases.get("C_find", []):
    if "sent" in r:
        print("  %.3f find %s" % (r["ta"], r["sent"]["mac"]))
    elif "rx" in r and r["rx"].get("type") != "status_report":
        print("  %.3f rx %s" % (r["ta"], r["rx"]))

# --- random (poisson) polling: what each scan's 6 s window would list ----
for ph in [p for p in phases if "pois" in p]:
    rs = phases[ph]
    polls = [r["ta"] for r in rs if "sent" in r]
    reps = [(r["ta"], r["rx"]["mac"]) for r in rs if is_rep(r)]
    counts = []
    for t in polls:
        counts.append(len({m for ta, m in reps if t <= ta < t + 6.0}))
    gaps = [b - a for a, b in zip(polls, polls[1:])]
    counts_s = sorted(counts)
    print("\n== %s: %d polls, mean gap %.2f s" % (ph, len(polls), sum(gaps) / len(gaps)))
    print("   devices listed per 6 s window: min %d  median %d  max %d" % (
        counts_s[0], counts_s[len(counts_s) // 2], counts_s[-1]))
    print("   distribution:", {c: counts.count(c) for c in sorted(set(counts))})
    by = defaultdict(lambda: [0, 0])
    for t in polls:
        seen = {m for ta, m in reps if t <= ta < t + 6.0}
        for m in allmacs:
            by[slot(m)][1] += 1
            by[slot(m)][0] += m in seen
    print("   per-slot listed rate:", {k: "%.0f%%" % (100.0 * a / b) for k, (a, b) in sorted(by.items())})
