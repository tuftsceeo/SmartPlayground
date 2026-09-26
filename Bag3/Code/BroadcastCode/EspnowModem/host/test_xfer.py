"""
test_xfer.py -- file transfer over ESP-NOW: speed and memory baseline
======================================================================
Sends a real file from SENDER to RECEIVER as ESP-NOW frames and reports
elapsed time, throughput, loss, SHA-256 match, and heap figures. Both roles
use the espnow_manager API, so either side may be an EUM host+modem pair or
a board with the built-in espnow_manager.py (e.g. a MockWand).

Set ROLE (and PEER_MAC on the sender), copy to the board as main.py, start
the RECEIVER first, then the SENDER.

Frames:
    {"type":"xfer_begin","size":N,"sha":hex,"chunks":K,"mode":m}   JSON
    b"XF" + seq(u16 BE) + data(<= CHUNK)                           binary
    {"type":"xfer_end","sent":K}                                   JSON
    {"type":"xfer_result", ...}                   receiver -> sender JSON

MODE "unicast": sync unicast per chunk (ESP-NOW ACK is the flow control).
MODE "broadcast": async broadcast, no ACK; shows raw loss under load.
Use an EUM host as SENDER: the built-in manager's send_raw() sends
broadcasts sync and gets ETIMEDOUT.
"""

import gc
import os
import time
import json
import hashlib
from binascii import hexlify

from espnow_manager import ESPNowManager, mac_bytes_to_str, BROADCAST_MAC

ROLE = "SENDER"                  # or "RECEIVER"
PEER_MAC = "A0:F2:62:87:92:CC"   # sender: receiver's MAC (as it prints it)
SRC_PATH = None                  # sender: file to send; None = main.py (this script)
MODE = "unicast"                 # or "broadcast"
CHUNK = 246                      # 250 B ESP-NOW max minus 4 B header
WRITE_FILE = True                # receiver: write to flash like a real pull
WRITE_BUF = 0                    # receiver: 0 = write each chunk; N = batch N bytes
RX_BUF = 0                       # receiver: 0 = driver default (526 B); N = set
                                 # ESP-NOW rxbuf (built-in espnow_manager only)
BEGIN_GAP_MS = 50
RESULT_WAIT_MS = 5000
IDLE_TIMEOUT_MS = 5000           # receiver: give up if chunks stop arriving

FS_ROOT = "/flash" if "flash" in os.listdir("/") else ""
DEST_PATH = FS_ROOT + "/xfer_test.bin"
DEFAULT_SRC = FS_ROOT + "/main.py"


PSRAM_REGION_MIN = 1024 * 1024   # same split as eum_proto.idf_heap()


def _heap():
    """gc free and internal-RAM IDF figures (PSRAM regions excluded)."""
    gc.collect()
    out = {"gc_free": gc.mem_free()}
    try:
        import esp32
    except ImportError:
        return out
    regions = [r for r in esp32.idf_heap_info(esp32.HEAP_DATA)
               if r[0] < PSRAM_REGION_MIN]
    out["idf_largest"] = max(r[2] for r in regions)
    out["idf_free"] = sum(r[1] for r in regions)
    return out


def _set_rxbuf(mgr, size):
    """Restart the built-in manager's ESPNow object with a larger rxbuf.

    rxbuf takes effect on active(True). The EUM variant has no local radio
    (mgr.enow is None); its modem already uses 8 KB.
    """
    if mgr.enow is None:
        print("xfer: RX_BUF ignored (EUM manager; modem rxbuf is fixed)")
        return
    mgr.enow.active(False)
    mgr.enow.config(rxbuf=size)
    mgr.enow.active(True)
    try:
        mgr.enow.add_peer(BROADCAST_MAC)
    except OSError as e:
        print("xfer: re-adding broadcast peer: %s" % e)
    print("xfer: ESP-NOW rxbuf set to %d" % mgr.enow.config("rxbuf"))


def _mem_snapshot(mgr, label):
    if hasattr(mgr, "mem_stats"):
        print("mem %s" % label, mgr.mem_stats())
    else:
        print("mem %s" % label, _heap())


def sender():
    mgr = ESPNowManager()
    mgr.init()
    path = SRC_PATH or DEFAULT_SRC
    size = os.stat(path)[6]
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(512)
            if not b:
                break
            h.update(b)
    sha = hexlify(h.digest()).decode()
    chunks = (size + CHUNK - 1) // CHUNK
    print("xfer: %s %d bytes, %d chunks of %d, mode=%s -> %s"
          % (path, size, chunks, CHUNK, MODE, PEER_MAC))

    peer = BROADCAST_MAC
    if MODE == "unicast":
        mgr.add_peer(PEER_MAC)
        peer = None
    _mem_snapshot(mgr, "before")

    def send_json(obj):
        if peer is None:
            return mgr.send_to(PEER_MAC, obj)
        return mgr.broadcast(obj)

    buf = bytearray(4 + CHUNK)
    mv = memoryview(buf)
    buf[0:2] = b"XF"
    fails = 0
    t0 = time.ticks_ms()
    if not send_json({"type": "xfer_begin", "size": size, "sha": sha,
                      "chunks": chunks, "mode": MODE}):
        print("xfer: begin frame not delivered")
    time.sleep_ms(BEGIN_GAP_MS)
    with open(path, "rb") as f:
        for seq in range(chunks):
            n = f.readinto(mv[4:])
            buf[2] = seq >> 8
            buf[3] = seq & 0xFF
            data = bytes(mv[:4 + n])
            if peer is None:
                ok = mgr.send_raw(mgr._peers[PEER_MAC], data)
            else:
                ok = mgr.send_raw(BROADCAST_MAC, data)
            if not ok:
                fails += 1
    send_json({"type": "xfer_end", "sent": chunks})
    t_send = time.ticks_diff(time.ticks_ms(), t0)
    print("xfer: sender done in %d ms (%.1f KB/s), %d send failures"
          % (t_send, size / 1024 / (t_send / 1000), fails))
    _mem_snapshot(mgr, "after")

    deadline = time.ticks_add(time.ticks_ms(), RESULT_WAIT_MS)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        t, d, m = mgr.poll(50)
        if t == "raw" and isinstance(d, dict) and d.get("type") == "xfer_result":
            print("xfer: receiver result", d)
            break
    else:
        print("xfer: no result from receiver within %d ms" % RESULT_WAIT_MS)
    if hasattr(mgr, "link_stats"):
        print("stats", mgr.link_stats())


def receiver():
    mgr = ESPNowManager()
    mgr.init()
    if RX_BUF:
        _set_rxbuf(mgr, RX_BUF)
    print("xfer receiver ready (write_file=%s write_buf=%d rx_buf=%d); "
          "waiting for xfer_begin" % (WRITE_FILE, WRITE_BUF, RX_BUF))
    _mem_snapshot(mgr, "idle")
    while True:
        t, d, sender_mac = mgr.poll(100)
        if t == "raw" and isinstance(d, dict) and d.get("type") == "xfer_begin":
            break
        time.sleep_ms(1)
    size, chunks, sha = d["size"], d["chunks"], d["sha"]
    print("xfer: begin %d bytes, %d chunks from %s" % (size, chunks, sender_mac))
    t0 = time.ticks_ms()
    h = hashlib.sha256()
    got = bytearray((chunks + 7) // 8)
    n_got = 0
    dup = 0
    out_of_order = 0
    next_seq = 0
    min_free = gc.mem_free()
    fh = open(DEST_PATH, "wb") if WRITE_FILE else None
    wbuf = bytearray(WRITE_BUF) if (fh and WRITE_BUF) else None
    wlen = 0
    write_ms = 0
    last_rx = time.ticks_ms()
    ended = False
    while not ended:
        t, d, m = mgr.poll(20)
        now = time.ticks_ms()
        if t is None:
            if time.ticks_diff(now, last_rx) > IDLE_TIMEOUT_MS:
                print("xfer: idle timeout")
                break
            time.sleep_ms(1)
            continue
        last_rx = now
        if t == "raw" and isinstance(d, (bytes, bytearray)) and d[:2] == b"XF":
            seq = (d[2] << 8) | d[3]
            if seq >= chunks:
                continue
            if got[seq >> 3] & (1 << (seq & 7)):
                dup += 1
                continue
            got[seq >> 3] |= 1 << (seq & 7)
            n_got += 1
            if seq == next_seq:
                data = d[4:]
                h.update(data)
                if fh:
                    tw = time.ticks_ms()
                    if wbuf is None:
                        fh.write(data)
                    else:
                        if wlen + len(data) > WRITE_BUF:
                            fh.write(memoryview(wbuf)[:wlen])
                            wlen = 0
                        wbuf[wlen:wlen + len(data)] = data
                        wlen += len(data)
                    write_ms += time.ticks_diff(time.ticks_ms(), tw)
            else:
                out_of_order += 1
            next_seq = seq + 1
            free = gc.mem_free()
            if free < min_free:
                min_free = free
        elif t == "raw" and isinstance(d, dict) and d.get("type") == "xfer_end":
            ended = True
        time.sleep_ms(1)
    if fh:
        if wlen:
            fh.write(memoryview(wbuf)[:wlen])
        fh.close()
    elapsed = time.ticks_diff(time.ticks_ms(), t0)
    ok = n_got == chunks and out_of_order == 0 and \
        hexlify(h.digest()).decode() == sha
    result = {"type": "xfer_result", "ok": ok, "chunks": chunks,
              "got": n_got, "dup": dup, "out_of_order": out_of_order,
              "ms": elapsed, "bytes": size, "min_gc_free": min_free,
              "write_ms": write_ms, "write_file": WRITE_FILE,
              "write_buf": WRITE_BUF, "rx_buf": RX_BUF}
    print("xfer: %s %d/%d chunks in %d ms (%.1f KB/s) dup=%d ooo=%d "
          "min_gc_free=%d write_ms=%d" % ("OK" if ok else "FAIL", n_got,
                                          chunks, elapsed,
                                          size / 1024 / max(elapsed, 1) * 1000,
                                          dup, out_of_order, min_free,
                                          write_ms))
    _mem_snapshot(mgr, "after")
    mgr.add_peer(sender_mac)
    mgr.send_to(sender_mac, result)


if ROLE == "SENDER":
    sender()
else:
    receiver()
