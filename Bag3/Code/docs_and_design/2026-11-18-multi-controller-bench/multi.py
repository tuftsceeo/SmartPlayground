"""multi.py LOG label=PORT [label=PORT ...] [--phases a,b,c,d] [--identify-only]

T1: several real controllers scanning, one host clock. A reader thread per
port logs every JSON line with absolute time (ta), controller label (c) and
phase (ph)."""
import json
import random
import sys
import threading
import time

import serial

args = [a for a in sys.argv[1:] if not a.startswith("--")]
flags = [a for a in sys.argv[1:] if a.startswith("--")]
logpath = args[0]
ctrls = dict(a.split("=", 1) for a in args[1:])
phases_on = "a,b,c,d"
for f in flags:
    if f.startswith("--phases="):
        phases_on = f.split("=", 1)[1]
ident_only = "--identify-only" in flags

lock = threading.Lock()
log = open(logpath, "a")
phase = ["init"]
ports = {}
rid = [2000]
stop = threading.Event()


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
            if line.startswith("{"):
                try:
                    obj = json.loads(line)
                except ValueError:
                    mark(c, raw=line[:200])
                    continue
                if obj.get("type") != "heartbeat":
                    mark(c, rx=obj)
                    if ident_only and obj.get("type") in ("identity", "error"):
                        print(c, json.dumps(obj)[:300], flush=True)


def send(c, obj):
    with lock:
        rid[0] += 1
        obj["id"] = rid[0]
    ports[c].write((json.dumps(obj) + "\n").encode())
    ports[c].flush()
    mark(c, sent=obj)


def scan(c):
    mark(c, scan_start=1)
    send(c, {"cmd": "fleet.scan"})


def progress(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


for c, p in ctrls.items():
    s = serial.Serial(p, baudrate=115200, timeout=0.05)
    ports[c] = s
time.sleep(0.3)
for c, s in ports.items():
    s.reset_input_buffer()
    threading.Thread(target=reader, args=(c, s), daemon=True).start()
for c in ports:
    send(c, {"cmd": "identify"})
time.sleep(2.0)
if ident_only:
    stop.set()
    sys.exit(0)

random.seed(11)
labels = list(ports)

if "a" in phases_on:
    phase[0] = "a_turns"
    progress("a: controllers take turns, 10 s apart, 6 rounds")
    for r in range(6):
        for c in labels:
            scan(c)
            time.sleep(10)


def poisson(tag, mean, dur):
    phase[0] = tag
    progress("%s: random scans, mean %.0f s per controller, %d s" % (tag, mean, dur))
    t0 = time.time()
    nxt = {c: t0 + random.expovariate(1.0 / mean) for c in labels}
    while time.time() - t0 < dur:
        now = time.time()
        for c in labels:
            if now >= nxt[c]:
                scan(c)
                nxt[c] = now + random.expovariate(1.0 / mean)
        time.sleep(0.01)
    time.sleep(8)


if "b" in phases_on:
    poisson("b_calm20", 20.0, 240)
if "c" in phases_on:
    poisson("c_busy8", 8.0, 240)
if "d" in phases_on:
    phase[0] = "d_sync"
    progress("d: all scan within 0.5 s, 10 times, 12 s apart")
    for r in range(10):
        offs = sorted((random.uniform(0, 0.5), c) for c in labels)
        t0 = time.time()
        for o, c in offs:
            while time.time() - t0 < o:
                time.sleep(0.005)
            scan(c)
        time.sleep(12)

phase[0] = "end"
time.sleep(2)
stop.set()
progress("done")
