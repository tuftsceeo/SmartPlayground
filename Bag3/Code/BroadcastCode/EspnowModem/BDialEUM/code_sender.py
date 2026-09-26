"""
code_sender.py -- serve game files over ESP-NOW (host side)
============================================================
ESP-NOW counterpart of BroadcastDial/BDialFirmware/code_server.py. Answers
code_req from wands running MockWandEUM/lib/espnow_code.py. The wand drives
the transfer (code_get windows); this side only reads and sends what it is
asked for, so it holds one open file per in-flight wand and nothing else.

File lookup follows code_server.py: <games_dir>/<slug><suffix>.py, an empty
slug meaning the slug in <fs_root>/active.txt, and an unknown hubtype refused
with a zero-size offer.

Host pinning: a code_req carrying "host" (the "@<id>" suffix of a getcode
card) is answered only by the sender whose host_id matches; other senders
stay silent, so a wand in a room with several hosts cannot take a refusal
or a game from the wrong one. A sender built with host_id=None answers
every request (bench use).

Copies: BDialEUM/code_sender.py is a byte-identical copy of this file
(tests/test_bdial_eum.py checks it).

PEER: MockWandEUM/lib/espnow_code.py holds a hand-kept copy of the message
names and frame layout. Change both in the same commit.

Usage (inside the host's poll loop):
    sender = CodeSender(mgr)
    mt, data, mac = mgr.poll()
    if sender.handle(mt, data, mac):
        continue

on_event(kind, info), if set, is called for:
    "serving"  a session started      info: mac, slug, bytes
    "done"     the wand sent code_done info: last_result (ok, slug, why, ...)
    "dropped"  a session went idle     info: mac, slug, why
"""

import os
import time
import hashlib
from binascii import hexlify

from espnow_manager import mac_str_to_bytes

FS_ROOT = "/flash" if "flash" in os.listdir("/") else ""
GAMES_DIR = FS_ROOT + "/games"
ACTIVE_PATH = FS_ROOT + "/active.txt"

FRAME_TAG = b"CX"
FRAME_HDR = 5                # tag(2) id(1) seq(2)
CHUNK = 245                  # 250 B ESP-NOW max minus FRAME_HDR
MAX_WINDOW = 16              # largest code_get honoured
# Wands served at once. They share the link (each frame costs one modem
# round trip), so more sessions do not raise total throughput; the cap keeps
# the ESP-NOW peer table (~20 entries) well clear of full. Wands over the cap
# get a "busy" offer and retry after BUSY_RETRY_MS plus random jitter.
MAX_SESSIONS = 6
SESSION_IDLE_MS = 15000
BUSY_RETRY_MS = 2000

# Same roles as code_server.ROLE_FILES (icon leg not implemented here).
ROLE_SUFFIX = {"wand": "", "": ""}


def _sha256_hex(path):
    h = hashlib.sha256()
    buf = bytearray(512)
    mv = memoryview(buf)
    with open(path, "rb") as f:
        while True:
            n = f.readinto(buf)
            if not n:
                break
            h.update(mv[:n])
    return hexlify(h.digest()).decode()


class _Session:
    def __init__(self, rid, mac_str, slug, path, size):
        self.rid = rid
        self.mac_str = mac_str
        self.slug = slug
        self.mac = mac_str_to_bytes(mac_str)
        self.path = path
        self.size = size
        self.chunks = (size + CHUNK - 1) // CHUNK
        self.fh = open(path, "rb")
        self.t_start = time.ticks_ms()
        self.t_last = self.t_start
        self.frames = 0
        self.gets = 0
        self.send_fail = 0

    def close(self):
        if self.fh is not None:
            self.fh.close()
            self.fh = None


class CodeSender:
    """Serves code_req/code_get/code_done. The wand is a peer only while it
    has a session (or for the one refusal reply), so the peer table never
    holds more than MAX_SESSIONS + 1 wands."""

    def __init__(self, mgr, games_dir=GAMES_DIR, verbose=True, host_id=None,
                 on_event=None):
        self.mgr = mgr
        self.games_dir = games_dir
        self.verbose = verbose
        self.host_id = host_id
        self.on_event = on_event
        self.sessions = {}       # mac_str -> _Session
        self._digest = (None, None, None)   # (path, size, sha)
        self.frame = bytearray(FRAME_HDR + CHUNK)
        self.frame_mv = memoryview(self.frame)
        self.frame[0:2] = FRAME_TAG
        self.served = 0
        self.failed = 0
        self.busy_replies = 0
        self.ignored = 0         # code_req pinned to another host
        # BENCH: answer "busy" to every request until this tick (see
        # code_host.BUSY_FOR_MS), to exercise the wand's retry path with
        # one wand.
        self.busy_until = time.ticks_ms()
        self.last_result = None

    # ─── LOOKUP ──────────────────────────────

    def _lookup(self, slug, hub):
        """Path of the file for (slug, hub), or None to refuse."""
        suffix = ROLE_SUFFIX.get(hub)
        if suffix is None:
            return None
        if not slug:
            try:
                with open(ACTIVE_PATH) as f:
                    slug = f.read().strip()
            except OSError:
                return None
            if not slug:
                return None
        path = "%s/%s%s.py" % (self.games_dir, slug, suffix)
        try:
            if os.stat(path)[6] > 0:
                return slug, path
        except OSError:
            return None
        return None

    def _sha(self, path, size):
        p, s, sha = self._digest
        if p == path and s == size:
            return sha
        sha = _sha256_hex(path)
        self._digest = (path, size, sha)
        return sha

    def _emit(self, kind, info):
        if self.on_event is not None:
            self.on_event(kind, info)

    # ─── MESSAGES ────────────────────────────

    def handle(self, mt, data, mac_str):
        """Process one poll() result. True if it was a code-transfer message."""
        self._expire()
        if mt != "raw" or not isinstance(data, dict):
            return False
        t = data.get("type")
        if t == "code_req":
            self._on_req(data, mac_str)
        elif t == "code_get":
            self._on_get(data, mac_str)
        elif t == "code_done":
            self._on_done(data, mac_str)
        else:
            return False
        return True

    def _on_req(self, data, mac_str):
        rid = data.get("id")
        slug = data.get("slug", "")
        hub = data.get("hub", "")
        want_host = data.get("host", "")
        if want_host and self.host_id is not None and want_host != self.host_id:
            self.ignored += 1
            return
        old = self.sessions.pop(mac_str, None)
        if old is not None:
            old.close()     # the wand restarted its request; peer is reused
        self.mgr.add_peer(mac_str)
        found = self._lookup(slug, hub)
        busy = (len(self.sessions) >= MAX_SESSIONS or
                time.ticks_diff(self.busy_until, time.ticks_ms()) > 0)
        if found is None or busy:
            offer = {"type": "code_offer", "id": rid, "size": 0}
            if found is None:
                offer["why"] = "no such game"
            else:
                offer["why"] = "busy"
                offer["retry_ms"] = BUSY_RETRY_MS
                self.busy_replies += 1
            if self.verbose:
                print("[ENX] refuse %s %r/%r: %s"
                      % (mac_str, slug, hub, offer["why"]))
            self.mgr.send_to(mac_str, offer)
            self.mgr.remove_peer(mac_str)
            return
        slug, path = found
        size = os.stat(path)[6]
        sha = self._sha(path, size)
        s = _Session(rid, mac_str, slug, path, size)
        self.sessions[mac_str] = s
        if self.verbose:
            print("[ENX] offer %s -> %s (%d B, %d chunks)"
                  % (path, mac_str, size, s.chunks))
        self.mgr.send_to(mac_str, {
            "type": "code_offer", "id": rid, "name": slug + ".py",
            "size": size, "sha": sha, "chunks": s.chunks, "chunk": CHUNK})
        self._emit("serving", {"mac": mac_str, "slug": slug, "bytes": size})

    def _on_get(self, data, mac_str):
        s = self.sessions.get(mac_str)
        if s is None or data.get("id") != s.rid:
            return
        base = data.get("from", 0)
        n = min(data.get("n", 1), MAX_WINDOW, s.chunks - base)
        s.gets += 1
        s.t_last = time.ticks_ms()
        f = self.frame
        f[2] = s.rid
        for seq in range(base, base + n):
            s.fh.seek(seq * CHUNK)
            got = s.fh.readinto(self.frame_mv[FRAME_HDR:])
            f[3] = seq >> 8
            f[4] = seq & 0xFF
            if self.mgr.send_raw(s.mac, bytes(self.frame_mv[:FRAME_HDR + got])):
                s.frames += 1
            else:
                s.send_fail += 1

    def _on_done(self, data, mac_str):
        s = self.sessions.pop(mac_str, None)
        if s is None or data.get("id") != s.rid:
            return
        s.close()
        self.mgr.remove_peer(mac_str)
        ms = time.ticks_diff(time.ticks_ms(), s.t_start)
        ok = bool(data.get("ok"))
        if ok:
            self.served += 1
        else:
            self.failed += 1
        self.last_result = {"mac": mac_str, "slug": s.slug, "path": s.path,
                            "ok": ok,
                            "why": data.get("why", ""), "bytes": s.size,
                            "ms": ms, "gets": s.gets, "frames": s.frames,
                            "send_fail": s.send_fail}
        if self.verbose:
            print("[ENX] %s %s -> %s: %d B in %d ms, gets=%d frames=%d "
                  "send_fail=%d %s"
                  % ("DONE" if ok else "FAILED", s.path, mac_str, s.size, ms,
                     s.gets, s.frames, s.send_fail, data.get("why", "")))
        self._emit("done", self.last_result)

    def _expire(self):
        if not self.sessions:
            return
        now = time.ticks_ms()
        for mac_str in list(self.sessions):
            s = self.sessions[mac_str]
            if time.ticks_diff(now, s.t_last) > SESSION_IDLE_MS:
                print("[ENX] session %s idle %d ms, dropped"
                      % (mac_str, SESSION_IDLE_MS))
                s.close()
                del self.sessions[mac_str]
                self.mgr.remove_peer(mac_str)
                self.failed += 1
                self._emit("dropped", {"mac": mac_str, "slug": s.slug,
                                       "why": "idle %d ms" % SESSION_IDLE_MS})
