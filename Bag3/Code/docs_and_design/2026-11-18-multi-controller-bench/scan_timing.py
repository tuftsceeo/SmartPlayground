"""scan_timing.py -- time Dial fleet.scan status replies over the JSON link.

  python3 scan_timing.py PORT baseline N GAP_S  LOG
  python3 scan_timing.py PORT storm PERIOD_MS DURATION_S LOG

Every line read is logged to LOG as JSON with t (s since start). Prints a
per-MAC summary: slot (last MAC byte % 16), expected delay, replies seen.
"""
import json
import sys
import time

import serial

BASE_MS, SLOT_MS, N_SLOTS = 400, 180, 16


def slot_of(mac):
    b = int(mac.replace(":", "")[-2:], 16)
    return b % N_SLOTS


class Run:
    def __init__(self, port, logpath):
        self.s = serial.Serial(port, baudrate=115200, timeout=0.05)
        time.sleep(0.3)
        self.s.reset_input_buffer()
        self.t0 = time.time()
        self.log = open(logpath, "w")
        self.buf = b""
        self.rid = 100

    def now(self):
        return time.time() - self.t0

    def mark(self, **kw):
        kw["t"] = round(self.now(), 3)
        self.log.write(json.dumps(kw) + "\n")
        self.log.flush()
        return kw

    def send(self, obj):
        self.rid += 1
        obj["id"] = self.rid
        self.s.write((json.dumps(obj) + "\n").encode())
        self.s.flush()
        self.mark(sent=obj)

    def pump(self, secs):
        out = []
        end = time.time() + secs
        while time.time() < end:
            chunk = self.s.read(4096)
            if chunk:
                self.buf += chunk
                while b"\n" in self.buf:
                    line, self.buf = self.buf.split(b"\n", 1)
                    line = line.decode("utf-8", "replace").strip()
                    if not line.startswith("{"):
                        continue
                    try:
                        obj = json.loads(line)
                    except ValueError:
                        continue
                    out.append(self.mark(rx=obj))
            time.sleep(0.001)
        return out


def summarize(scans):
    """scans: list of (t_sent, [rx marks])."""
    seen = {}
    for i, (ts, rxs) in enumerate(scans):
        for m in rxs:
            o = m["rx"]
            if o.get("type") != "status_report":
                continue
            mac = o["mac"]
            d = seen.setdefault(mac, {"kind": o.get("kind"), "role": o.get("role"),
                                      "scans": set(), "copies": 0, "lat": []})
            d["scans"].add(i)
            d["copies"] += 1
            d["lat"].append(round(m["t"] - ts, 2))
    print("\nper-scan unique counts:", [
        len({m["rx"]["mac"] for m in rxs if m["rx"].get("type") == "status_report"})
        for _, rxs in scans])
    print("%-18s %-14s %4s %6s %5s %6s  %s" % ("mac", "kind/role", "slot", "exp_s", "hits", "copies", "latencies(s)"))
    for mac, d in sorted(seen.items(), key=lambda kv: slot_of(kv[0])):
        sl = slot_of(mac)
        print("%-18s %-14s %4d %6.2f %2d/%-2d %6d  %s" % (
            mac, "%s/%s" % (d["kind"], d["role"]), sl, (BASE_MS + sl * SLOT_MS) / 1000,
            len(d["scans"]), len(scans), d["copies"], d["lat"][:8]))


def main():
    port, mode = sys.argv[1], sys.argv[2]
    a, b, logpath = float(sys.argv[3]), float(sys.argv[4]), sys.argv[5]
    r = Run(port, logpath)
    r.send({"cmd": "identify"})
    for m in r.pump(1.5):
        print("<-", json.dumps(m["rx"])[:200])
    scans = []
    if mode == "baseline":
        for i in range(int(a)):
            ts = r.now()
            r.send({"cmd": "fleet.scan"})
            rxs = r.pump(b)
            scans.append((ts, rxs))
            n = len({m["rx"]["mac"] for m in rxs if m["rx"].get("type") == "status_report"})
            errs = [m["rx"] for m in rxs if m["rx"].get("type") == "error"]
            print("scan %d: %d unique devices %s" % (i, n, errs or ""))
    elif mode == "storm":
        period, dur = a / 1000.0, b
        ts0 = r.now()
        last = ts0
        rxs = []
        while r.now() - ts0 < dur:
            last = r.now()
            r.send({"cmd": "fleet.scan"})
            rxs += r.pump(period)
        r.mark(note="storm_end", last_poll=round(last, 3))
        during = list(rxs)
        after = r.pump(8.0)
        scans = [(ts0, during), (last, after)]
        print("storm: polls every %d ms for %.0f s; last poll at t=%.2f" % (a, dur, last))
        print("  [0] = replies while polling continued (latency from storm start)")
        print("  [1] = replies after polling stopped (latency from last poll)")
    summarize(scans)


if __name__ == "__main__":
    main()
