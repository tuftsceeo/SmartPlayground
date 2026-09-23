# PEER: Bag3/Code/BroadcastCode/BroadcastBox/BBoxFirmware/serve_probe.py — keep in sync.
"""
serve_probe.py — DIAGNOSTIC ONLY. Not part of serving; delete with
code_server.DEBUG_SERVE once the intermittent pull failure is understood.

Why this is a separate module rather than code in code_server.py: the AP
needs one large contiguous block of IDF DRAM and must claim it early,
because nothing later in boot can un-fragment the heap enough to find it
again. code_server.py is imported by bdial_server.py at module scope, so
anything living there -- every docstring, every format string, every
function object -- is allocated before prewarm_ap() and long before arm().
Instrumentation added there once already cost both Dials their AP:
"WiFi Out of Memory" at idf_free=12456 with idf_largest=7680, which is
fragmentation, not exhaustion.

So all the strings live here, and code_server.py imports this module only
when DEBUG_SERVE is set AND only after _start_ap() has returned. With the
flag off, this file is never parsed and costs nothing.

The same rule applies to anything added here later: nothing in this file may
be reachable before the radio has its memory.

Reads as `# DBG ...` lines on serial.
"""

import gc
from time import ticks_ms, ticks_diff

try:
    import esp32
except ImportError:
    esp32 = None

INTERVAL_MS = 2000


def idf_heap():
    """(total IDF free, largest single free block), or (None, None).

    gc.mem_free() is the Python heap and is the wrong number for anything
    the radio does. MicroPython's GC heap is carved out of the same DRAM the
    WiFi driver allocates from, so a large idle Python heap is memory the
    driver cannot have. Total free against largest free block is what
    separates "out of memory" from "out of contiguous memory".

    Same source and shape as MockWand/lib/memprobe.py's _idf_free().
    """
    if esp32 is None:
        return None, None
    try:
        regions = esp32.idf_heap_info(esp32.HEAP_DATA)
    except Exception:
        return None, None
    total = 0
    largest = 0
    for r in regions:
        total += r[1]
        biggest = r[2] if len(r) > 2 else 0
        if biggest > largest:
            largest = biggest
    return total, largest


class Probe:
    """Reports what the server is doing. Holds the server, allocates nothing
    the server would not have allocated anyway."""

    def __init__(self, server):
        self.srv = server
        self.last_ms = 0
        self.polls = 0

    def stations(self):
        """How many stations the SoftAP holds, or -1 if unknown.

        ap.config(max_clients=MAX_CLIENTS) is a hard cap: at the cap the AP
        refuses new associations outright, which a joining device sees as a
        connect that never leaves STAT_CONNECTING. A device that dies
        mid-transfer and resets never sends a clean deauth, so its entry can
        linger. Whether those accumulate is the question this answers.
        """
        ap = self.srv._ap
        if ap is None:
            return -1
        try:
            return len(ap.status('stations'))
        except (OSError, ValueError, AttributeError, TypeError):
            return -1

    def tick(self):
        """Periodic summary. Called every poll(), including with no clients.

        The no-client case is the point: a station count that stays high
        after every transfer has ended is the signature of entries lingering
        after devices that reset without deauthenticating.

        polls is how many poll() calls happened since the last report. Far
        fewer than INTERVAL_MS allows means the main loop, not the socket, is
        setting the transfer rate -- _step_body() moves at most one CHUNK per
        poll() per client.
        """
        self.polls += 1
        now = ticks_ms()
        if ticks_diff(now, self.last_ms) < INTERVAL_MS:
            return
        total, largest = idf_heap()
        print("# DBG serve: clients=%d stations=%d gc_free=%d idf_free=%s "
              "idf_largest=%s polls=%d"
              % (len(self.srv._clients), self.stations(), gc.mem_free(),
                 total, largest, self.polls))
        for c in self.srv._clients:
            # sel rising while sent does not means the socket says writable
            # and refuses anyway -- the peer has stopped acking. sel flat
            # means select() never offered it, which points at the loop or
            # the driver rather than the peer.
            print("# DBG   client state=%s sent=%d/%d ms_to_deadline=%d "
                  "sel=%d blocked=%d"
                  % (c.state, c.sent, c.size, ticks_diff(c.deadline, now),
                     c.sel, c.blocked))
        self.last_ms = now
        self.polls = 0

    def accepted(self):
        print("# DBG accepted: clients=%d stations=%d gc_free=%d"
              % (len(self.srv._clients), self.stations(), gc.mem_free()))

    def at_cap(self, max_clients):
        print("# DBG accept BLOCKED: clients=%d at MAX_CLIENTS=%d stations=%d"
              % (len(self.srv._clients), max_clients, self.stations()))

    def finished(self, c, ok):
        print("# DBG finish ok=%s state=%s sent=%d/%d age_ms=%d sel=%d "
              "blocked=%d clients=%d stations=%d"
              % (ok, c.state, c.sent, c.size,
                 ticks_diff(ticks_ms(), c.started_ms), c.sel, c.blocked,
                 len(self.srv._clients) - 1, self.stations()))
