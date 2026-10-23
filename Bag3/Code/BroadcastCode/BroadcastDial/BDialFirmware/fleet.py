"""
fleet.py -- status scan, find-device and staggered code distribution to
wands and stations over the Dial's ESP-NOW radio (code_link.NativeManager).

Imported on the first fleet.* command, after the radio is up
(docs_and_design/2026-09-23-ap-memory-order.md).

Serial events (to the app):
    {"type":"status_report","mac","kind","battery","rssi"}   per reply
    {"type":"status_done","n"}                                scan window over
    {"type":"dist_progress","done","total","mac","ok","why"}  per device
    {"type":"dist_done","done","total","ok"}                  distribution over

ESP-NOW messages (to devices):
    status_poll, find_device {mac}, code_push {mac, slug, host}

A device answers code_push with the normal getcode pull (code_req ...
code_done); its code_done is the completion signal, reported by
CodeLink as last_result and passed in through on_pull().
"""

import time
from code_link import HOST_ID

SCAN_MS = 6000           # status replies are slotted over ~0.4-3.1 s
POLL_REPEAT = 3          # status_poll / find_device sends, POLL_GAP_MS apart
POLL_GAP_MS = 60
STAGGER_MS = 2500        # minimum gap between code_push sends
MAX_INFLIGHT = 3         # pushed but not finished; half of MAX_SESSIONS
PUSH_TIMEOUT_MS = 30000  # no code_done by then -> failed
PROGRESS_HOLD_MS = 3000  # final count stays on screen this long


def _norm(mac):
    return (mac or "").replace(":", "").upper()


class Fleet:
    def __init__(self, link, ui):
        self.link = link          # JsonLink
        self.ui = ui              # StationUI
        self.mgr = None           # NativeManager, set on each command
        self._scan_until = None
        self._seen = {}           # norm mac -> True during a scan
        self._slug = None
        self._queue = []          # macs not yet pushed
        self._inflight = {}       # norm mac -> (mac, deadline)
        self._next_at = 0
        self._done = 0
        self._ok = 0
        self._total = 0
        self._hide_at = None

    @property
    def busy(self):
        return self._scan_until is not None or self._total > 0

    def _repeat(self, msg):
        for i in range(POLL_REPEAT):
            if i:
                time.sleep_ms(POLL_GAP_MS)
            self.mgr.broadcast(msg)

    # -- commands ------------------------------------------------------

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
        self._slug = slug
        self._queue = list(macs)
        self._inflight = {}
        self._next_at = time.ticks_ms()
        self._done = 0
        self._ok = 0
        self._total = len(self._queue)
        self._hide_at = None
        self.ui.show_progress(0, self._total)

    def cancel(self, why="cancelled"):
        """Fail everything not finished. Called when the radio goes down."""
        if self._scan_until is not None:
            self._scan_until = None
            self.link.send({"type": "status_done", "n": len(self._seen)})
        if not self._total:
            return
        for mac, _ in list(self._inflight.values()):
            self._finish(mac, False, why)
        for mac in list(self._queue):
            self._finish(mac, False, why)

    # -- radio input -----------------------------------------------------

    def on_msg(self, data, mac):
        """Non-code JSON from code_link: status replies during a scan."""
        if data.get("type") != "status_report" or self._scan_until is None:
            return
        self._seen[_norm(mac)] = True
        self.link.send({"type": "status_report", "mac": mac,
                        "kind": data.get("kind"),
                        "battery": data.get("battery"),
                        "rssi": data.get("rssi")})

    def on_pull(self, result):
        """CodeLink last_result for a finished game-file transfer."""
        entry = self._inflight.get(_norm(result.get("mac")))
        if entry is None:
            return
        self._finish(entry[0], result.get("ok"), result.get("why"))

    # -- per loop ------------------------------------------------------

    def step(self):
        now = time.ticks_ms()
        if self._hide_at is not None and time.ticks_diff(now, self._hide_at) >= 0:
            self._hide_at = None
            self.ui.show_progress(0, 0)
        if self._scan_until is not None and time.ticks_diff(now, self._scan_until) >= 0:
            self._scan_until = None
            self.link.send({"type": "status_done", "n": len(self._seen)})
        if not self._total:
            return
        for key in list(self._inflight):
            mac, deadline = self._inflight[key]
            if time.ticks_diff(now, deadline) >= 0:
                self._finish(mac, False, "timeout")
        if (self._queue and len(self._inflight) < MAX_INFLIGHT
                and time.ticks_diff(now, self._next_at) >= 0):
            self._push(self._queue.pop(0), now)

    def _push(self, mac, now):
        self._next_at = time.ticks_add(now, STAGGER_MS)
        msg = {"type": "code_push", "mac": mac, "slug": self._slug, "host": HOST_ID}
        # Unicast for a MAC-layer ack; peer added only for this send, and
        # left alone if a code session already holds it.
        temp = mac not in self.mgr._peers
        if temp:
            self.mgr.add_peer(mac)
        acked = self.mgr.send_to(mac, msg)
        if temp:
            self.mgr.remove_peer(mac)
        if not acked:
            self._finish(mac, False, "no_ack")
            return
        self._inflight[_norm(mac)] = (mac, time.ticks_add(now, PUSH_TIMEOUT_MS))
        self.link.send({"type": "dist_progress", "done": self._done,
                        "total": self._total, "mac": mac, "ok": None,
                        "why": "pushed"})

    def _finish(self, mac, ok, why):
        self._inflight.pop(_norm(mac), None)
        if mac in self._queue:
            self._queue.remove(mac)
        self._done += 1
        if ok:
            self._ok += 1
        self.link.send({"type": "dist_progress", "done": self._done,
                        "total": self._total, "mac": mac, "ok": bool(ok),
                        "why": why or None})
        self.ui.show_progress(self._done, self._total)
        if self._done >= self._total:
            self.link.send({"type": "dist_done", "done": self._done,
                            "total": self._total, "ok": self._ok})
            self._total = 0
            self._hide_at = time.ticks_add(time.ticks_ms(), PROGRESS_HOLD_MS)
