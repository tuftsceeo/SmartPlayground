"""
wand_breakin.py -- get into a running Bag3 wand and copy files, in ONE port session.

Host-side tool. Not firmware; never upload this to a device.

Why: opening a wand's port resets it (rst:0x15), and main.py then counts down
GRACE_S before taking the board. mpremote's raw-REPL entry sends a few Ctrl-C
while the chip is still resetting and gives up. This opens the port once,
waits for the "# booting -- Ctrl-C within" countdown line, then sends Ctrl-C every
200 ms until ">>>" or the countdown ends (45 s limit), then does every
operation over raw REPL in the same session, checks each copied file's size,
and finishes with a plain reset (machine.reset()) unless --no-reset.

Usage (all paths on the device are absolute, e.g. :/lib/x.py or /lib/x.py):
    python3 wand_breakin.py PORT [--log FILE]
        [--cp LOCAL:/REMOTE ...] [--manifest flash_manifest.json]
        [--get /REMOTE:LOCAL ...] [--rm /REMOTE ...] [--rm-stale-mpy]
        [--write /REMOTE=TEXT ...] [--exec CODE ...] [--no-reset]

Everything received is appended to --log (default: stdout) with wall time.
On a failed break-in it prints the last 20 lines received and exits 2.
"""

import argparse
import binascii
import json
import os
import sys
import time

import serial

BREAK_LIMIT_S = 45  # reset + GRACE_S (30) countdown + margin
COUNTDOWN = b"# booting -- Ctrl-C within"  # main.py _boot_grace()
CHUNK = 256

_log = None
_tail = []


def L(msg):
    line = "%s %s" % (time.strftime("%H:%M:%S"), msg)
    _tail.append(line)
    del _tail[:-20]
    print(line, file=_log, flush=True)


def _lines(buf):
    for ln in buf.decode("utf-8", "replace").splitlines():
        if ln.strip():
            L("< " + ln.rstrip())


def open_port(port):
    t0 = time.time()
    while time.time() - t0 < 10:
        try:
            s = serial.Serial()
            s.port, s.baudrate, s.timeout = port, 115200, 0.05
            s.dtr = False
            s.rts = False
            s.open()
            if DTR:
                s.dtr = True
            return s
        except (serial.SerialException, OSError):
            time.sleep(0.2)
    raise SystemExit("could not open %s" % port)


DTR = False


def break_in(port, rts_reset=False):
    """Open the port; during the boot countdown, Ctrl-C every 200 ms until '>>>'. Returns the open port."""
    s = open_port(port)
    L("# breakin: port opened (dtr=%s)" % DTR)
    if rts_reset:
        s.rts = True
        time.sleep(0.1)
        s.rts = False
        L("# breakin: RTS reset pulse")
    # Ctrl-C outside the GRACE_S countdown is lost or crashes the wand
    # (2026-11-17 11:08 Load access fault right after "ESPNow: active").
    # Send nothing until main.py prints its countdown line, then one Ctrl-C
    # every 200 ms, and stop when the countdown reaches "# 1..." so no Ctrl-C
    # lands in _boot(). No countdown line means no Ctrl-C at all.
    t0 = time.time()
    buf = b""
    seen = b""
    go = False
    done = False
    last = 0
    while time.time() - t0 < BREAK_LIMIT_S:
        try:
            now = time.time()
            if not go and COUNTDOWN in seen:
                go = True
                L("# breakin: countdown seen (%.1f s); Ctrl-C every 200 ms" % (now - t0))
            if go and not done and b"# 1..." in seen:
                done = True
                L("# breakin: countdown ended without REPL; no more Ctrl-C")
            if go and not done and now - last >= 0.2:
                s.write(b"\x03")
                last = now
            d = s.read(4096)
        except (serial.SerialException, OSError) as e:
            # The open-triggered reset drops USB; reopen and keep going.
            L("# breakin: port dropped (%s); reopening" % e)
            try:
                s.close()
            except Exception:
                pass
            time.sleep(0.3)
            s = open_port(port)
            continue
        if d:
            buf += d
            seen = (seen + d)[-2000:]
            if b"\n" in buf:
                head, buf = buf.rsplit(b"\n", 1)
                _lines(head)
            if go and b">>>" in seen[-300:]:
                L("# breakin: REPL after %.1f s" % (time.time() - t0))
                return s
        time.sleep(0.01)
    _lines(buf)
    print("BREAK-IN FAILED after %d s. Last 20 lines:" % BREAK_LIMIT_S, file=sys.stderr)
    for ln in _tail:
        print(ln, file=sys.stderr)
    sys.exit(2)


_pending = b""


def _read_until(s, marker, timeout):
    """Return bytes up to and including marker; keep anything after it for the next call."""
    global _pending
    t0 = time.time()
    buf = _pending
    _pending = b""
    while True:
        i = buf.find(marker)
        if i >= 0:
            _pending = buf[i + len(marker):]
            return buf[:i + len(marker)]
        if time.time() - t0 > timeout:
            raise RuntimeError("timeout waiting for %r; got %r" % (marker, buf[-200:]))
        buf += s.read(4096)


def raw_enter(s):
    global _pending
    s.write(b"\r\x03\x03\x01")
    time.sleep(0.2)
    s.reset_input_buffer()
    _pending = b""
    s.write(b"\x01")
    _read_until(s, b"raw REPL; CTRL-B to exit\r\n>", 5)


def raw_exec(s, code, timeout=20):
    """Run code in raw REPL; return (stdout, stderr) as str."""
    data = code.encode()
    for i in range(0, len(data), CHUNK):
        s.write(data[i:i + CHUNK])
        time.sleep(0.01)
    s.write(b"\x04")
    _read_until(s, b"OK", 5)
    out = _read_until(s, b"\x04", timeout)[:-1]
    err = _read_until(s, b"\x04", timeout)[:-1]
    _read_until(s, b">", 5)
    return out.decode("utf-8", "replace"), err.decode("utf-8", "replace")


def ex(s, code, timeout=20):
    out, err = raw_exec(s, code, timeout)
    if err.strip():
        raise RuntimeError(err.strip())
    return out


def remote_size(s, path):
    out, err = raw_exec(s, "import os\ntry:\n print(os.stat(%r)[6])\nexcept OSError:\n print(-1)" % path)
    return int(out.strip() or -1)


def put(s, local, remote):
    with open(local, "rb") as f:
        data = f.read()
    d = remote.rsplit("/", 1)[0]
    if d:
        ex(s, "import os\np=''\nfor x in %r.strip('/').split('/'):\n p+='/'+x\n try: os.mkdir(p)\n except OSError: pass" % d)
    ex(s, "import binascii\nf=open(%r,'wb')\nw=f.write\nu=binascii.a2b_base64" % remote)
    step = 512
    for i in range(0, len(data), step):
        b64 = binascii.b2a_base64(data[i:i + step]).decode().strip()
        ex(s, "w(u(%r))" % b64)
    ex(s, "f.close()")
    got = remote_size(s, remote)
    ok = got == len(data)
    L("# cp %s -> %s  %d bytes, device %d  %s" % (local, remote, len(data), got, "OK" if ok else "SIZE MISMATCH"))
    return ok


def get(s, remote, local):
    out = ex(s, "import binascii,sys\nf=open(%r,'rb')\nwhile 1:\n b=f.read(512)\n if not b: break\n sys.stdout.write(binascii.b2a_base64(b))\nf.close()" % remote, 30)
    data = b"".join(binascii.a2b_base64(x) for x in out.split() if x)
    with open(local, "wb") as f:
        f.write(data)
    L("# get %s -> %s  %d bytes" % (remote, local, len(data)))


def rm_stale_mpy(s):
    out = ex(s, "import os\nfs=os.listdir('/lib')\nfor n in fs:\n if n.endswith('.mpy') and n[:-4]+'.py' in fs:\n  os.remove('/lib/'+n); print(n)")
    L("# removed stale .mpy: %s" % (" ".join(out.split()) or "none"))


def main():
    global _log
    ap = argparse.ArgumentParser()
    ap.add_argument("port")
    ap.add_argument("--log")
    ap.add_argument("--cp", action="append", default=[])
    ap.add_argument("--manifest")
    ap.add_argument("--get", action="append", default=[])
    ap.add_argument("--rm", action="append", default=[])
    ap.add_argument("--rm-stale-mpy", action="store_true")
    ap.add_argument("--write", action="append", default=[])
    ap.add_argument("--exec", action="append", default=[])
    ap.add_argument("--no-reset", action="store_true")
    ap.add_argument("--dtr", action="store_true", help="assert DTR after opening, as Thonny does")
    ap.add_argument("--rts-reset", action="store_true", help="pulse RTS once after opening (leaves download mode)")
    a = ap.parse_args()
    global DTR
    DTR = a.dtr
    _log = open(a.log, "a") if a.log else sys.stdout

    pairs = [c.rsplit(":", 1) for c in a.cp]
    if a.manifest:
        m = json.load(open(a.manifest))
        root = os.path.abspath(os.path.join(os.path.dirname(a.manifest), "..", "..", "..", ".."))
        pairs += [(os.path.join(root, f["repo"]), "/" + f["device"].lstrip("/")) for f in m["files"]]
        a.rm = list(m.get("remove_before_upload", [])) + a.rm
    for loc, _ in pairs:
        if not os.path.isfile(loc):
            raise SystemExit("missing local file: " + loc)

    s = break_in(a.port, a.rts_reset)
    bad = 0
    try:
        raw_enter(s)
        for g in a.get:
            r, loc = g.split(":", 1)
            get(s, r, loc)
        for r in a.rm:
            r = "/" + r.lstrip("/")
            out, err = raw_exec(s, "import os\ntry:\n os.remove(%r); print('removed')\nexcept OSError as e:\n print('absent', e)" % r)
            L("# rm %s: %s" % (r, out.strip()))
        for w in a.write:
            r, text = w.split("=", 1)
            ex(s, "f=open(%r,'w')\nf.write(%r)\nf.close()" % (r, text))
            L("# write %s = %r (size %d)" % (r, text, remote_size(s, r)))
        t0 = time.time()
        for loc, r in pairs:
            if not put(s, loc, r):
                bad += 1
        if pairs:
            L("# copied %d files in %.0f s, %d size mismatches" % (len(pairs), time.time() - t0, bad))
        if a.rm_stale_mpy:
            rm_stale_mpy(s)
        for c in a.exec:
            out, err = raw_exec(s, c, 30)
            L("# exec %r -> %s %s" % (c, out.strip(), err.strip()))
    finally:
        if not a.no_reset:
            try:
                s.write(b"\x02")
                time.sleep(0.1)
                s.write(b"import machine; machine.reset()\r\n")
                time.sleep(0.3)
                L("# breakin: plain reset sent")
            except (serial.SerialException, OSError):
                pass
        s.close()
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
