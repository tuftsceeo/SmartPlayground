"""Status scan, find-device and staggered code distribution (adapted from the Dial's fleet.py).

Events go to emit(dict), with the same shapes the Dial sent over serial:
status_report, status_done, dist_progress, dist_done. Import after the radio is up.
"""

import time
from code_link import HOST_ID

SCAN_MS = 6000
POLL_REPEAT = 3
POLL_GAP_MS = 60
STAGGER_MS = 2500
MAX_INFLIGHT = 3
PUSH_TIMEOUT_MS = 30000


def _norm(mac):
    return (mac or "").replace(":", "").upper()


class Fleet:
    def __init__(self, emit, send_unicast):
        self.emit = emit
        self.send_unicast = send_unicast    # (mac, msg) -> acked
        self.mgr = None
        self.paused = False
        self.slug = None
        self._scan_until = None
        self._seen = {}
        self._queue = []
        self._inflight = {}
        self._next_at = 0
        self._done = 0
        self._ok = 0
        self._total = 0

    @property
    def busy(self):
        return self._scan_until is not None or self._total > 0

    @property
    def scanning(self):
        return self._scan_until is not None

    def _repeat(self, msg):
        for i in range(POLL_REPEAT):
            if i:
                time.sleep_ms(POLL_GAP_MS)
            self.mgr.broadcast(msg)

    def scan(self, mgr):
        self.mgr = mgr
        self._seen = {}
        self._scan_until = time.ticks_add(time.ticks_ms(), SCAN_MS)
        self._repeat({"type": "status_poll"})

    def find(self, mgr, mac):
        self.mgr = mgr
        self._repeat({"type": "find_device", "mac": mac})

    def distribute(self, mgr, slug, macs):
        self.mgr = mgr
        self.slug = slug
        self.paused = False
        self._queue = list(macs)
        self._inflight = {}
        self._next_at = time.ticks_ms()
        self._done = 0
        self._ok = 0
        self._total = len(self._queue)

    def cancel(self, why="cancelled"):
        if self._scan_until is not None:
            self._scan_until = None
            self.emit({"type": "status_done", "n": len(self._seen)})
        if not self._total:
            return
        for mac, _ in list(self._inflight.values()):
            self._finish(mac, False, why)
        for mac in list(self._queue):
            self._finish(mac, False, why)

    def retry(self, mac):
        """Push once more to one device (after a finished run)."""
        if self._total:
            if mac not in self._queue and _norm(mac) not in self._inflight:
                self._queue.append(mac)
                self._total += 1
            return
        self._queue = [mac]
        self._inflight = {}
        self._next_at = time.ticks_ms()
        self._done = self._ok = 0
        self._total = 1

    def on_msg(self, data, mac):
        if data.get("type") != "status_report" or self._scan_until is None:
            return
        self._seen[_norm(mac)] = True

    def on_pull(self, result):
        entry = self._inflight.get(_norm(result.get("mac")))
        if entry is not None:
            self._finish(entry[0], result.get("ok"), result.get("why"))

    def step(self):
        now = time.ticks_ms()
        if self._scan_until is not None and time.ticks_diff(now, self._scan_until) >= 0:
            self._scan_until = None
            self.emit({"type": "status_done", "n": len(self._seen)})
        if not self._total:
            return
        for key in list(self._inflight):
            mac, deadline = self._inflight[key]
            if time.ticks_diff(now, deadline) >= 0:
                self._finish(mac, False, "timeout")
        if (self._queue and not self.paused and len(self._inflight) < MAX_INFLIGHT
                and time.ticks_diff(now, self._next_at) >= 0):
            self._push(self._queue.pop(0), now)

    def _push(self, mac, now):
        self._next_at = time.ticks_add(now, STAGGER_MS)
        msg = {"type": "code_push", "mac": mac, "slug": self.slug, "host": HOST_ID}
        if not self.send_unicast(mac, msg):
            self._finish(mac, False, "no_ack")
            return
        self._inflight[_norm(mac)] = (mac, time.ticks_add(now, PUSH_TIMEOUT_MS))
        self.emit({"type": "dist_progress", "done": self._done, "total": self._total,
                   "mac": mac, "ok": None, "why": "pushed"})

    def _finish(self, mac, ok, why):
        self._inflight.pop(_norm(mac), None)
        if mac in self._queue:
            self._queue.remove(mac)
        self._done += 1
        if ok:
            self._ok += 1
        self.emit({"type": "dist_progress", "done": self._done, "total": self._total,
                   "mac": mac, "ok": bool(ok), "why": why or None})
        if self._done >= self._total:
            self.emit({"type": "dist_done", "done": self._done, "total": self._total, "ok": self._ok})
            self._total = 0
