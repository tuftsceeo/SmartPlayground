"""t2.py LOG CONFIG.json -- distribute vs scan contention across controllers.

CONFIG: {"ports": {label: port}, "A": label, "B": label, "S": label,
         "slugA": slug, "slugB": slug, "wandsA": [mac..], "wandsB": [mac..],
         "phases": "q,c,x"}
q: A distributes slugA to wandsA, nothing else on air (from us).
c: A distributes again while B and S scan at random (mean 8 s each).
x: A -> wandsA and B -> wandsB at the same moment, S scans at random.
"""
import json
import random
import sys
import threading
import time

import serial

logpath, cfgpath = sys.argv[1], sys.argv[2]
cfg = json.load(open(cfgpath))
lock = threading.Lock()
log = open(logpath, "a")
phase = ["init"]
ports = {}
rid = [3000]
stop = threading.Event()
done_evt = {}


def mark(c, **kw):
    kw["ta"] = round(time.time(), 3)
    kw["ph"] = phase[0]
    kw["c"] = c
    with lock:
        log.write(json.dumps(kw) + "\n")
        log.flush()


def reader(c, s):
    buf = b""
    while not stop.is_set():
        try:
            chunk = s.read(4096)
        except Exception as e:
            mark(c, readerr=str(e))
            time.sleep(1)
            continue
        if not chunk:
            continue
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            line = line.decode("utf-8", "replace").strip()
            if not line.startswith("{"):
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if obj.get("type") == "heartbeat":
                continue
            mark(c, rx=obj)
            t = obj.get("type")
            if t in ("dist_progress", "dist_done", "error"):
                print(time.strftime("%H:%M:%S"), c, json.dumps(obj)[:200], flush=True)
            if t == "dist_done" and c in done_evt:
                done_evt[c].set()


def send(c, obj):
    with lock:
        rid[0] += 1
        obj["id"] = rid[0]
    ports[c].write((json.dumps(obj) + "\n").encode())
    ports[c].flush()
    mark(c, sent=obj)


def progress(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


for c, p in cfg["ports"].items():
    ports[c] = serial.Serial(p, baudrate=115200, timeout=0.05)
time.sleep(0.3)
for c, s in ports.items():
    s.reset_input_buffer()
    threading.Thread(target=reader, args=(c, s), daemon=True).start()

A, B, S = cfg["A"], cfg["B"], cfg["S"]
random.seed(5)


def distribute(c, slug, macs):
    done_evt[c] = threading.Event()
    send(c, {"cmd": "fleet.distribute", "slug": slug, "macs": macs})


def wait_done(cs, limit):
    t0 = time.time()
    while time.time() - t0 < limit:
        if all(done_evt[c].is_set() for c in cs):
            return True
        time.sleep(0.1)
    return False


def scan_bg(labels, mean, flag):
    nxt = {c: time.time() + random.expovariate(1.0 / mean) for c in labels}
    while not flag.is_set():
        now = time.time()
        for c in labels:
            if now >= nxt[c]:
                mark(c, scan_start=1)
                send(c, {"cmd": "fleet.scan"})
                nxt[c] = now + random.expovariate(1.0 / mean)
        time.sleep(0.01)


def find_bg(labels, mean, targets, flag):
    """Random directed Find Me from each controller, mean `mean` s apart."""
    nxt = {c: time.time() + random.expovariate(1.0 / mean) for c in labels}
    while not flag.is_set():
        now = time.time()
        for c in labels:
            if now >= nxt[c]:
                mac = random.choice(targets)
                send(c, {"cmd": "fleet.find", "mac": mac})
                nxt[c] = now + random.expovariate(1.0 / mean)
        time.sleep(0.01)


def chaos(tag, dur, with_sends, targets=None, finds=True):
    phase[0] = tag
    progress("%s: finds (mean 6 s per controller) + scans (mean 8 s), sends=%s" % (tag, with_sends))
    flag = threading.Event()
    ths = [threading.Thread(target=scan_bg, args=([A, B, S], 8.0, flag), daemon=True)]
    if finds:
        ths.append(threading.Thread(target=find_bg, args=([A, B, S], 6.0, targets or cfg["all"], flag), daemon=True))
    for th in ths:
        th.start()
    t0 = time.time()
    if with_sends:
        time.sleep(3)
        distribute(A, cfg["slugA"], cfg["wandsA"])
        distribute(B, cfg["slugB"], cfg["wandsB"])
    while time.time() - t0 < dur:
        time.sleep(0.2)
    if with_sends:
        progress("%s sends done=%s" % (tag, wait_done([A, B], 60)))
    flag.set()
    for th in ths:
        th.join()
    time.sleep(15)


ph = set(cfg.get("phases", "q,c,x").split(","))
if "q" in ph:
    phase[0] = "q_quiet"
    progress("q: %s distributes %s to %d wands, quiet" % (A, cfg["slugA"], len(cfg["wandsA"])))
    distribute(A, cfg["slugA"], cfg["wandsA"])
    progress("q done=%s" % wait_done([A], 150))
    time.sleep(15)
if "c" in ph:
    phase[0] = "c_scans"
    progress("c: %s distributes while %s,%s scan (mean 8 s)" % (A, B, S))
    flag = threading.Event()
    th = threading.Thread(target=scan_bg, args=([B, S], 8.0, flag), daemon=True)
    th.start()
    time.sleep(3)
    distribute(A, cfg["slugA"], cfg["wandsA"])
    progress("c done=%s" % wait_done([A], 150))
    time.sleep(10)
    flag.set()
    th.join()
    time.sleep(15)
if "x" in ph:
    phase[0] = "x_two_sends"
    progress("x: %s and %s distribute at once, %s scans" % (A, B, S))
    flag = threading.Event()
    th = threading.Thread(target=scan_bg, args=([S], 8.0, flag), daemon=True)
    th.start()
    time.sleep(3)
    distribute(A, cfg["slugA"], cfg["wandsA"])
    distribute(B, cfg["slugB"], cfg["wandsB"])
    progress("x done=%s" % wait_done([A, B], 180))
    time.sleep(10)
    flag.set()
    th.join()
if "f" in ph:
    time.sleep(15)
    chaos("f_finds_scans", 120, False)
if "z" in ph:
    chaos("z_everything", 180, True)
if "k1" in ph:
    chaos("k1_scans_only", 120, False, finds=False)
if "k2" in ph:
    chaos("k2_finds_nobody", 120, False, targets=["02:00:00:00:00:01"])
if "k3" in ph:
    chaos("k3_finds_real", 120, False)
phase[0] = "end"
time.sleep(2)
stop.set()
progress("done")
