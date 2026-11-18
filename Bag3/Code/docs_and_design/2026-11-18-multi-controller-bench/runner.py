"""runner.py PORT LOG -- unattended scan/find timing series on the Dial.
Logs every rx line and every send with absolute time (ta) and phase."""
import json
import sys
import time

import serial

USB_WANDS = ["A0:F2:62:85:F0:6C", "A0:F2:62:86:DF:E4"]

port, logpath = sys.argv[1], sys.argv[2]
s = serial.Serial(port, baudrate=115200, timeout=0.05)
time.sleep(0.3)
s.reset_input_buffer()
log = open(logpath, "w")
buf = b""
rid = [1000]
phase = ["init"]


def mark(**kw):
    kw["ta"] = round(time.time(), 3)
    kw["ph"] = phase[0]
    log.write(json.dumps(kw) + "\n")
    log.flush()


def send(obj):
    rid[0] += 1
    obj["id"] = rid[0]
    s.write((json.dumps(obj) + "\n").encode())
    s.flush()
    mark(sent=obj)


def pump(secs):
    global buf
    end = time.time() + secs
    while time.time() < end:
        chunk = s.read(4096)
        if chunk:
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.decode("utf-8", "replace").strip()
                if line.startswith("{"):
                    try:
                        mark(rx=json.loads(line))
                    except ValueError:
                        mark(raw=line[:200])
                elif line:
                    mark(raw=line[:200])
        time.sleep(0.001)


def baseline(n, gap, tag):
    phase[0] = tag
    for i in range(n):
        mark(scan_start=i)
        send({"cmd": "fleet.scan"})
        pump(gap)


def storm(period_ms, dur, rest, tag):
    phase[0] = tag
    t0 = time.time()
    while time.time() - t0 < dur:
        send({"cmd": "fleet.scan"})
        pump(period_ms / 1000.0)
    mark(storm_end=True)
    pump(rest)


def finds(rounds, wait, tag):
    phase[0] = tag
    for r in range(rounds):
        for mac in USB_WANDS:
            send({"cmd": "fleet.find", "mac": mac})
            pump(wait)


def progress(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


send({"cmd": "identify"})
pump(1.5)
progress("A baseline 20x10s")
baseline(20, 10.0, "A_base10")
progress("B storms")
for rep in range(2):
    for p in (3000, 2000, 1000, 500):
        storm(p, 15, 12, "B_storm%d_r%d" % (p, rep))
progress("C finds")
finds(3, 20.0, "C_find")
progress("D rescan spam 20x6.5s")
baseline(20, 6.5, "D_base6")
progress("E baseline 20x10s")
baseline(20, 10.0, "E_base10")
phase[0] = "end"
mark(done=True)
progress("done")
