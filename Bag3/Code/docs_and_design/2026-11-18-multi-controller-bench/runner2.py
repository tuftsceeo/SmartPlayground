import random, time, sys
sys.argv = [sys.argv[0], sys.argv[1], sys.argv[2]]
exec(open("runner.py").read().split("send({\"cmd\": \"identify\"})")[0])
random.seed(7)

def poisson(mean_gap, dur, rest, tag):
    phase[0] = tag
    t0 = time.time()
    while time.time() - t0 < dur:
        mark(scan_start=0)
        send({"cmd": "fleet.scan"})
        pump(min(random.expovariate(1.0 / mean_gap), 8.0))
    mark(storm_end=True)
    pump(rest)

send({"cmd": "identify"}); pump(1.5)
for rep in range(2):
    for p in (2500, 1500):
        progress("F storm %d r%d" % (p, rep)); storm(p, 15, 12, "F_storm%d_r%d" % (p, rep))
progress("G poisson 2.5s"); poisson(2.5, 180, 10, "G_pois2500")
progress("H poisson 1.25s"); poisson(1.25, 180, 10, "H_pois1250")
phase[0] = "end"; mark(done=True); progress("done")
