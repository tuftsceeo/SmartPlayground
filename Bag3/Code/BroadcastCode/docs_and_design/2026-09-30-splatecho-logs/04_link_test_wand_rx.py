# Link test receiver: count numbered "lt" broadcasts per condition tag.
import time, json, espnow
e = espnow.ESPNow()
e.active(True)
got = {}
rs = {}
st0 = e.stats()
end = time.ticks_add(time.ticks_ms(), 180000)
while time.ticks_diff(end, time.ticks_ms()) > 0:
    mac, msg = e.irecv(50)
    if msg is None:
        continue
    try:
        d = json.loads(msg)
    except Exception:
        continue
    if not isinstance(d, dict) or d.get("type") != "lt":
        continue
    t = d.get("t")
    if t == "end":
        break
    got.setdefault(t, set()).add(d["n"])
    try:
        rs.setdefault(t, []).append(e.peers_table[mac][0])
    except Exception:
        pass
st1 = e.stats()
for t in sorted(got):
    s = got[t]
    miss = [i for i in range(300) if i not in s]
    r = rs.get(t) or [0]
    print("RESULT", t, "got", len(s), "missing", len(miss), "rssi avg", sum(r) // len(r), "min", min(r))
    print("MISS", t, miss[:80])
print("STATS before", st0, "after", st1)
