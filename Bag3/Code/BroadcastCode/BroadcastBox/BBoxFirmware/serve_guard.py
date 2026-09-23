# PEER: Bag3/Code/BroadcastCode/BroadcastDial/BDialFirmware/serve_guard.py — keep in sync.
"""
serve_guard.py — keep enough IDF heap free for the SoftAP to serve.

The WiFi driver allocates its per-station and per-packet buffers at run time
from the IDF heap. With too little free, a wand associates but its WPA2
handshake or DHCP never completes, or a transfer stalls mid-body with the
link still up. On the bench (2026-09-23, Dial 2) every failing window had
12-17 KB free and every passing one ~28 KB; a reset restored it, and one
stalled transfer lowered it by ~5 KB that did not come back.

Guard samples free IDF heap whenever the server is idle (no clients, no
associated stations). A reading below MIN_IDF_FREE on two consecutive
samples writes FLAG_PATH and calls machine.reset(); bbox_server.run() sees
the flag on the next boot and goes straight back into SERVE on a fresh heap.
The flag holds the count of consecutive guard reboots. A successful pull or
a teacher leaving SERVE removes it. After MAX_REBOOTS reboots with no
successful pull in between, the guard stops rebooting and prints a warning
on every sample, so a board that cannot reach the floor keeps serving and
says so rather than boot-looping.

Imported only after arm() has returned, like serve_probe.py: nothing in this
file may be allocated before the AP has claimed its memory.
"""

import gc
import os
import machine
from time import ticks_ms, ticks_diff

try:
    import esp32
except ImportError:
    esp32 = None

FLAG_PATH = '/flash/serve_guard.txt'

# Floor for idle free IDF heap. Bench readings are from the Dial (failing
# 12-17 KB, passing ~28 KB); the Box's own level is unmeasured. If the Box
# reboots straight after arming, its normal level is below this -- read the
# "# serve_guard: armed" line and lower the floor.
MIN_IDF_FREE = 22000

MAX_REBOOTS = 2
SAMPLE_MS = 5000     # between idle samples
SETTLE_MS = 5000     # after arm and after the last client, before sampling


def idf_heap():
    """(total free, largest free block) across IDF HEAP_DATA, or (None, None)."""
    if esp32 is None:
        return None, None
    regions = esp32.idf_heap_info(esp32.HEAP_DATA)
    total = 0
    largest = 0
    for r in regions:
        total += r[1]
        if r[2] > largest:
            largest = r[2]
    return total, largest


def _read_count():
    try:
        with open(FLAG_PATH, 'r') as f:
            return int(f.read().strip() or '0')
    except (OSError, ValueError):
        return 0


def clear():
    try:
        os.remove(FLAG_PATH)
    except OSError:
        pass


class Guard:
    def __init__(self, server):
        self.srv = server
        self.count = _read_count()
        self.pickups = server.pickups
        self.low = 0
        self.quiet_since = ticks_ms()
        self.last_ms = ticks_ms()
        total, largest = idf_heap()
        print("# serve_guard: armed idf_free=%s idf_largest=%s floor=%d reboots=%d/%d"
              % (total, largest, MIN_IDF_FREE, self.count, MAX_REBOOTS))

    def _stations(self):
        ap = self.srv._ap
        if ap is None:
            return 0
        return len(ap.status('stations'))

    def stop(self):
        """SERVE is ending by the teacher's choice: forget the reboot count."""
        clear()

    def poll(self):
        """Call once per main-loop tick in SERVE. May not return (reset)."""
        now = ticks_ms()
        if self.srv.pickups != self.pickups:
            # A pull succeeded: the serve is healthy, start the count over.
            self.pickups = self.srv.pickups
            if self.count:
                self.count = 0
                clear()
        if self.srv.serving_count or self._stations():
            self.quiet_since = now
            self.low = 0
            return
        if ticks_diff(now, self.quiet_since) < SETTLE_MS:
            return
        if ticks_diff(now, self.last_ms) < SAMPLE_MS:
            return
        self.last_ms = now
        total, largest = idf_heap()
        if total is None or total >= MIN_IDF_FREE:
            self.low = 0
            return
        self.low += 1
        if self.low < 2:
            return
        if self.count >= MAX_REBOOTS:
            print("# serve_guard: WARNING idf_free=%d idf_largest=%d below floor %d "
                  "after %d reboots -- serving anyway"
                  % (total, largest, MIN_IDF_FREE, self.count))
            return
        print("# serve_guard: idf_free=%d idf_largest=%d below floor %d -- "
              "rebooting into SERVE (%d/%d)"
              % (total, largest, MIN_IDF_FREE, self.count + 1, MAX_REBOOTS))
        with open(FLAG_PATH, 'w') as f:
            f.write('%d' % (self.count + 1))
        gc.collect()
        machine.reset()
