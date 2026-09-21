"""
pull_bench.py — laptop-side concurrency bench for the multi-client CodeServer.

Standalone CPython (stdlib only). Not device firmware -- not in manifest.js,
does not run on the Dial. Join the Dial's SoftAP from a laptop first (SSID
SP-FILEPUSH, password playground1), put the Dial in SERVE mode, then run
this against it to drive N simultaneous pulls and confirm they actually
overlap instead of queueing.

Speaks the exact wire protocol code_server.py serves and code_puller.py
consumes (see both files' "PEER" comments): 1-byte request length + slug,
then a 4-byte size / 32-byte SHA-256 / 1-byte name-length / name header,
then the raw file body, then a 2-byte OK/NO ack. This script hand-keeps its
own copy of that framing, same as code_puller.py does -- there is no shared
module between the three.

Usage (from BDialFirmware/, laptop already joined to SP-FILEPUSH):
    python3 tools/pull_bench.py --n 4
    python3 tools/pull_bench.py --n 4 --slug melody
    python3 tools/pull_bench.py --n 4 --stall 1     # 1 client goes silent mid-body
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


def pull(label, host, port, slug, stall, results, lock):
    """One connection, one pull. Mirrors code_puller.py's protocol exactly."""
    t_start = time.monotonic()
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(35)  # comfortably past the server's own SOCK_REPLY_TIMEOUT_S
    try:
        s.connect((host, port))
        req = (slug or "").encode("utf-8")
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
        t_end = time.monotonic()
        with lock:
            results[label] = {
                "ok": ok, "name": name, "size": size, "received": received,
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
    args = ap.parse_args()

    results = {}
    lock = threading.Lock()
    threads = []
    for i in range(args.n):
        label = "client-%d%s" % (i, "-STALL" if i < args.stall else "")
        t = threading.Thread(target=pull, args=(
            label, args.host, args.port, args.slug, i < args.stall, results, lock))
        threads.append(t)

    print("# starting %d pull(s) against %s:%d (slug=%r, %d stalled)"
          % (args.n, args.host, args.port, args.slug or "<active>", args.stall))
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
            print("  %-16s OK   %-16s %7d bytes  wall=%.2fs  first_byte=%.2fs in"
                  % (label, r["name"], r["received"], r["wall_s"],
                     (r["first_byte"] - r["start"]) if r["first_byte"] else -1))
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
