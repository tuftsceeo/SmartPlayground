"""
xfer_bench.py -- host-side driver for the three-way transfer bench.

Host-side tool (CPython + pyserial). Never upload to a device.

Every mode ends at the same point: wand B's {"type": "game_start"} line.
All lines are stamped with host milliseconds since the phase started, so one
clock times every mode, and the reboots of the WiFi path are inside it.

  wifi    Wand B runs stock MockWand firmware. Per run: Ctrl-C, then
          pull_flag.set_pending(slug, host) and machine.reset() typed at the
          REPL (the same flag a getcode tap writes). T0 = the reset line sent.
  espnow  Wand B runs MockWandEUM. Starts tools/devtests/xfer_host.py on wand
  nfc     A (`mpremote resume run`), with MODE patched in, and logs both
          wands until A prints "XFER all done". T0 = B's "# getcode via".
  report  Parse one or more phase logs into per-size tables.

Usage (from BroadcastCode/):
  python3 tools/devtests/xfer_bench.py wifi   --b PORT_B --host 5094 [--runs 5]
  python3 tools/devtests/xfer_bench.py espnow --a PORT_A --b PORT_B
  python3 tools/devtests/xfer_bench.py nfc    --a PORT_A --b PORT_B
  python3 tools/devtests/xfer_bench.py report tools/devtests/out/xfer/*.log

Logs go to tools/devtests/out/xfer/<mode>.log (not committed).
"""

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
import threading
import time

import serial

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "xfer")
SLUGS = ["speed05", "speed20", "speed28", "speed32", "speed36", "speed40"]
BAUD = 115200
WIFI_CAP_S = 60
WIFI_PAUSE_S = 3


class Log:
    """One phase log: '<ms> <src> <line>', ms from phase start."""

    def __init__(self, mode):
        os.makedirs(OUT, exist_ok=True)
        self.path = os.path.join(OUT, "%s.log" % mode)
        self.f = open(self.path, "w")
        self.t0 = time.monotonic()
        self.lock = threading.Lock()
        self.write("H", "# phase %s" % mode)

    def write(self, src, line):
        ms = int((time.monotonic() - self.t0) * 1000)
        with self.lock:
            self.f.write("%d %s %s\n" % (ms, src, line))
            self.f.flush()
        return ms


class Port:
    """Serial reader that survives the USB drop of a board reset."""

    def __init__(self, port):
        self.port = port
        self.ser = None

    def _open(self):
        while self.ser is None:
            try:
                self.ser = serial.Serial(self.port, BAUD, timeout=0.2,
                                         dsrdtr=False, rtscts=False)
            except serial.SerialException:
                time.sleep(0.2)

    def readline(self):
        self._open()
        try:
            b = self.ser.readline()
        except (serial.SerialException, OSError):
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
            return None
        return b.decode("utf-8", "replace").rstrip() if b else None

    def write(self, data):
        self._open()
        self.ser.write(data)
        self.ser.flush()

    def close(self):
        if self.ser:
            self.ser.close()


def run_wifi(args):
    log = Log("wifi")
    b = Port(args.b)
    settle = re.compile(r'"type": "game_end"|attempt budget spent')
    for slug in SLUGS:
        for run in range(1, args.runs + 1):
            b.write(b"\r\x03\x03")
            time.sleep(0.3)
            b.write(("import pull_flag; pull_flag.set_pending(%r, %r)\r"
                     % (slug, args.host)).encode())
            time.sleep(0.3)
            while b.readline() is not None:
                pass
            log.write("H", "BENCH trigger mode=wifi slug=%s run=%d" % (slug, run))
            b.write(b"import machine; machine.reset()\r")
            start = time.monotonic()
            while time.monotonic() - start < WIFI_CAP_S:
                line = b.readline()
                if line is None:
                    continue
                log.write("B", line)
                if settle.search(line):
                    break
            else:
                log.write("H", "BENCH timeout slug=%s run=%d" % (slug, run))
            print("wifi %s run %d done" % (slug, run))
            time.sleep(WIFI_PAUSE_S)
    b.close()
    print("log:", log.path)


def run_wand_to_wand(args, mode):
    log = Log(mode)
    src = open(os.path.join(HERE, "xfer_host.py")).read()
    src = src.replace('MODE = "espnow"', 'MODE = %r' % mode, 1)
    if args.runs != 5:
        src = src.replace("RUNS = 5", "RUNS = %d" % args.runs, 1)
    tmp = tempfile.NamedTemporaryFile("w", suffix="_xfer_host.py", delete=False)
    tmp.write(src)
    tmp.close()
    b = Port(args.b)
    stop = threading.Event()

    def read_b():
        while not stop.is_set():
            line = b.readline()
            if line is not None:
                log.write("B", line)

    t = threading.Thread(target=read_b, daemon=True)
    t.start()
    cmd = [sys.executable, "-m", "mpremote", "connect", args.a, "resume", "run", tmp.name]
    log.write("H", "# " + " ".join(cmd))
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, env=env)
    try:
        for line in p.stdout:
            line = line.rstrip()
            log.write("A", line)
            if line.startswith("XFER "):
                print(line)
            if line.startswith("XFER all done"):
                break
    finally:
        time.sleep(3)          # wand B's last launch lines
        p.terminate()
        stop.set()
        t.join(1)
        b.close()
        os.unlink(tmp.name)
    print("log:", log.path)


# ─── report ───

LINE = re.compile(r"^(\d+) ([HAB]) (.*)$")
SIZE_OF = {"speed%02d" % k: k * 1024 for k in (5, 10, 20, 24, 28, 32, 36, 40)}


def _json(text):
    i = text.find("{")
    if i < 0:
        return None
    try:
        return json.loads(text[i:])
    except ValueError:
        return None


def parse(path):
    """Return a list of run dicts from one phase log."""
    runs = []
    cur = None
    mode = None
    for raw in open(path):
        m = LINE.match(raw.rstrip("\n"))
        if not m:
            continue
        ms, src, text = int(m.group(1)), m.group(2), m.group(3)
        if src == "H" and text.startswith("# phase "):
            mode = text.split()[-1]
        if src == "H" and text.startswith("BENCH trigger"):
            kv = dict(x.split("=") for x in text.split()[2:])
            cur = {"mode": mode, "slug": kv["slug"], "run": int(kv["run"]), "t0": ms}
            runs.append(cur)
            continue
        # Wand-to-wand runs start at wand B's own line: A's lines come
        # through mpremote and can arrive late.
        if src == "B" and text.startswith("# getcode via"):
            mm = re.search(r"slug='([^']*)'", text)
            cur = {"mode": mode, "slug": mm.group(1) if mm else "?", "t0": ms}
            runs.append(cur)
            continue
        if cur is None or src != "B":
            continue
        if re.match(r"\[(XFER|ENX|NFX)\] receiving", text):
            cur["t_recv"] = ms
        elif "# DBG body done" in text:
            mm = re.search(r"ms=(\d+)", text)
            if mm:
                cur["body_ms"] = int(mm.group(1))
            cur["t_body_end"] = ms
        elif text.startswith("[XFER] OK:"):
            cur["t_ok"] = ms
            cur["ok"] = True
        elif text.startswith("[XFER] rejected"):
            cur["ok"] = False
            cur["why"] = text.split(": ", 2)[-1][:60]
        elif '"enx_result"' in text:
            j = _json(text) or {}
            cur["ok"] = j.get("result") == "True"
            cur["body_ms"] = j.get("body_ms")
            cur["t_ok"] = ms
            if not cur["ok"]:
                cur["why"] = str(j.get("why") or j.get("result"))[:60]
        elif '"game_start"' in text and "t_end" not in cur:
            cur["t_end"] = ms
        elif "attempt budget spent" in text:
            cur.setdefault("ok", False)
    return runs


def _span(r, a, b):
    if a in r and b in r:
        return (r[b] - r[a]) / 1000.0
    return None


def _med(xs, fmt):
    xs = [x for x in xs if x is not None]
    if not xs:
        return "--"
    if len(xs) == 1:
        return fmt % xs[0]
    return (fmt + " [" + fmt + "-" + fmt + "]") % (statistics.median(xs), min(xs), max(xs))


def report(paths):
    for path in paths:
        runs = parse(path)
        if not runs:
            continue
        mode = runs[0]["mode"]
        print("\n## %s (%s)\n" % (mode, os.path.basename(path)))
        print("| Size | Passed | setup_s | body_ms | KB/s | launch_s | total_s | Failures |")
        print("|---|---|---|---|---|---|---|---|")
        for slug in [s for s in SLUGS if any(r["slug"] == s for r in runs)]:
            rs = [r for r in runs if r["slug"] == slug]
            good = [r for r in rs if r.get("ok") and "t_end" in r]
            size = SIZE_OF.get(slug, 0)
            kbs = [size / 1024 / (r["body_ms"] / 1000.0) for r in good if r.get("body_ms")]
            whys = sorted(set(r.get("why", "no result") for r in rs if r not in good))
            print("| %d B | %d/%d | %s | %s | %s | %s | %s | %s |" % (
                size, len(good), len(rs),
                _med([_span(r, "t0", "t_recv") for r in good], "%.2f"),
                _med([r.get("body_ms") for r in good], "%d"),
                _med(kbs, "%.1f"),
                _med([_span(r, "t_ok", "t_end") for r in good], "%.2f"),
                _med([_span(r, "t0", "t_end") for r in good], "%.2f"),
                "; ".join(whys) or ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["wifi", "espnow", "nfc", "report"])
    ap.add_argument("logs", nargs="*")
    ap.add_argument("--a")
    ap.add_argument("--b")
    ap.add_argument("--host", default="")
    ap.add_argument("--runs", type=int, default=5)
    args = ap.parse_args()
    if args.mode == "report":
        report(args.logs)
    elif args.mode == "wifi":
        run_wifi(args)
    else:
        run_wand_to_wand(args, args.mode)


if __name__ == "__main__":
    main()
