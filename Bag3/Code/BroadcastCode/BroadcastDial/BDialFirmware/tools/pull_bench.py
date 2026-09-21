"""
pull_bench.py — laptop-side concurrency bench for the multi-client CodeServer.

Standalone CPython (stdlib only). Not device firmware -- not in manifest.js,
does not run on the device. Works against either the Dial or the Box: they
run the same multi-client CodeServer. Join the device's SoftAP from a laptop
first (SSID SP-FILEPUSH, password playground1), put it in SERVE mode, then
run this against it to drive N simultaneous pulls and confirm they actually
overlap instead of queueing.

Speaks the exact wire protocol code_server.py serves and code_puller.py
consumes (see both files' "PEER" comments): a request frame, then a 4-byte
size / 32-byte SHA-256 / 1-byte name-length / name header, then the raw file
body, then a 2-byte OK/NO ack. A requester naming a hubtype sends the v2
frame instead and, for a role whose ROLE_FILES entry takes icons, reads one
more leg after its ack: a 1-byte count, then that many header/body/ack
files. This script hand-keeps its own copy of that framing, same as
code_puller.py does -- there is no shared module between the three.

Usage (from BDialFirmware/, laptop already joined to SP-FILEPUSH):
    python3 tools/pull_bench.py --n 4
    python3 tools/pull_bench.py --n 4 --slug melody
    python3 tools/pull_bench.py --n 4 --stall 1     # 1 client goes silent mid-body
    python3 tools/pull_bench.py --n 2 --hubtype icon_display --slug goalrace
"""

import argparse
import hashlib
import socket
import threading
import time

HOST = '192.168.4.1'
PORT = 8266


def _read_exact(sock, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise EOFError("connection closed after %d/%d bytes" % (len(buf), n))
        buf.extend(chunk)
    return bytes(buf)


REQ_V2 = 0xFF   # version sentinel; see code_server.py's REQ_V2


def _read_header(sock):
    """One file header: 4-byte size, then (unless refused) digest + name."""
    size = int.from_bytes(_read_exact(sock, 4), "big")
    if size == 0:
        return 0, b"", ""
    rest = _read_exact(sock, 32 + 1)
    name = _read_exact(sock, rest[32]).decode("utf-8")
    return size, rest[:32], name


def _recv_and_ack(sock, size, digest):
    """Read one body, hash it, send the 2-byte ack. Returns (ok, received)."""
    h = hashlib.sha256()
    received = 0
    while received < size:
        chunk = sock.recv(min(4096, size - received))
        if not chunk:
            break
        h.update(chunk)
        received += len(chunk)
    ok = (received == size) and (h.digest() == digest)
    sock.sendall(b"OK" if ok else b"NO")
    return ok, received


def _pull_icons(sock):
    """Read the icon leg: a 1-byte count, then that many files. Returns how
    many arrived intact. Mirrors code_puller.py's _pull_icons()."""
    head = sock.recv(1)
    if not head:
        return 0
    promoted = 0
    for _ in range(head[0]):
        size, digest, _name = _read_header(sock)
        if size == 0:
            continue
        ok, _received = _recv_and_ack(sock, size, digest)
        if ok:
            promoted += 1
    return promoted


def pull(label, host, port, slug, stall, results, lock, hubtype=""):
    """One connection, one pull. Mirrors code_puller.py's protocol exactly."""
    t_start = time.monotonic()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(35)  # comfortably past the server's own SOCK_REPLY_TIMEOUT_S
    try:
        s.connect((host, port))
        req = (slug or "").encode("utf-8")
        if hubtype:
            hub = hubtype.encode("utf-8")
            s.sendall(bytes([REQ_V2, len(req)]) + req + bytes([len(hub)]) + hub)
        else:
            s.sendall(bytes([len(req)]) + req)

        size = int.from_bytes(_read_exact(s, 4), "big")
        if size == 0:
            with lock:
                results[label] = {"ok": False, "start": t_start,
                                   "reason": "norequest (no such game/nothing active)"}
            return

        rest = _read_exact(s, 32 + 1)
        digest = rest[:32]
        name_len = rest[32]
        name = _read_exact(s, name_len).decode("utf-8")

        h = hashlib.sha256()
        received = 0
        t_first_byte = None
        while received < size:
            if stall:
                # Simulate a dead/frozen wand: read nothing further, never ack.
                # The server must drop this connection on its own deadline
                # rather than let it block anyone else.
                time.sleep(60)
                continue
            chunk = s.recv(min(4096, size - received))
            if not chunk:
                break
            if t_first_byte is None:
                t_first_byte = time.monotonic()
            h.update(chunk)
            received += len(chunk)

        ok = (received == size) and (h.digest() == digest)
        s.sendall(b'OK' if ok else b'NO')
        # A role whose ROLE_FILES entry takes icons gets one more leg after
        # the game file's ack; reading it is what keeps the socket in step.
        icons = _pull_icons(s) if (ok and hubtype == "icon_display") else None
        t_end = time.monotonic()
        with lock:
            results[label] = {
                "ok": ok, "name": name, "size": size, "received": received,
                "icons": icons,
                "start": t_start, "first_byte": t_first_byte, "end": t_end,
                "wall_s": t_end - t_start,
            }
    except Exception as e:
        with lock:
            results[label] = {"ok": False, "start": t_start,
                               "reason": "%s: %s" % (type(e).__name__, e)}
    finally:
        s.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default=HOST)
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--slug", default="", help="game slug, or empty for the active game")
    ap.add_argument("--n", type=int, default=4, help="number of concurrent pulls")
    ap.add_argument("--stall", type=int, default=0,
                     help="this many of the N clients go silent mid-body, to prove "
                          "a stalled wand doesn't block the rest")
    ap.add_argument("--hubtype", default="",
                     help="send the v2 request frame naming this role (e.g. "
                          "icon_display); empty sends the v1 frame a wand sends. "
                          "icon_display also reads the icon leg after the ack")
    args = ap.parse_args()

    results = {}
    lock = threading.Lock()
    threads = []
    for i in range(args.n):
        label = "client-%d%s" % (i, "-STALL" if i < args.stall else "")
        t = threading.Thread(target=pull, args=(
            label, args.host, args.port, args.slug, i < args.stall, results, lock,
            args.hubtype))
        threads.append(t)

    print("# starting %d pull(s) against %s:%d (slug=%r, role=%s, %d stalled)"
          % (args.n, args.host, args.port, args.slug or "<active>",
             args.hubtype or "<v1 wand>", args.stall))
    for t in threads:
        t.start()
    for t in threads:
        # Stalled clients never finish on their own; join() just returns once
        # the server's own timeout has forced their socket closed.
        t.join(timeout=45)

    non_stalled = [r for label, r in results.items() if not label.endswith("-STALL")]
    print("\n# results:")
    for label in sorted(results):
        r = results[label]
        if r.get("ok"):
            icons = "" if r.get("icons") is None else "  icons=%d" % r["icons"]
            print("  %-16s OK   %-16s %7d bytes  wall=%.2fs  first_byte=%.2fs in%s"
                  % (label, r["name"], r["received"], r["wall_s"],
                     (r["first_byte"] - r["start"]) if r["first_byte"] else -1,
                     icons))
        else:
            print("  %-16s FAIL %s" % (label, r.get("reason", "unknown")))

    # Only a completed pull has an "end" (set right after the ack is sent);
    # a failure -- including "every pull in this run failed" -- has "start"
    # but no window to compare, so the overlap check must not assume every
    # non-stalled result has both keys.
    timed = [r for r in non_stalled if r.get("end") is not None]
    if timed:
        starts = [r["start"] for r in timed]
        ends = [r["end"] for r in timed]
        # Overlap check: any two completed pulls whose windows intersect is
        # direct evidence the server served them concurrently, not serially.
        overlapping = any(
            a["start"] < b["end"] and b["start"] < a["end"]
            for i, a in enumerate(timed)
            for b in timed[i + 1:]
        )
        print("\n# window: first start=%.2f last end=%.2f span=%.2fs, overlap detected: %s"
              % (min(starts), max(ends), max(ends) - min(starts), overlapping))
        if len(timed) > 1 and not overlapping:
            print("# WARNING: no overlap between any two pulls -- looks serial, not concurrent")
    elif non_stalled:
        print("\n# no completed pulls -- every non-stalled client failed, see results above")

    ok_count = sum(1 for r in non_stalled if r.get("ok"))
    print("\n# %d/%d non-stalled pulls OK" % (ok_count, len(non_stalled)))


if __name__ == "__main__":
    main()
