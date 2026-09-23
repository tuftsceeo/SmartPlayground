# PEER: Bag3/Code/BroadcastCode/MockWand/pull_probe.py — keep in sync.
"""
pull_probe.py — DIAGNOSTIC ONLY. Not part of pulling; delete with
code_puller.DEBUG_PULL once the intermittent pull failure is understood.

Why this is a separate module rather than code in code_puller.py: the radio
needs a large contiguous block of IDF DRAM and takes it at sta.active(True).
main.py imports code_puller inside pull mode, BEFORE that join, so anything
living there -- every docstring, every format string -- is allocated ahead of
the one allocation that cannot be made to fit later. The same mistake on the
Dial cost both units their AP ("WiFi Out of Memory" at idf_free=12456 with
idf_largest=7680: fragmentation, not exhaustion).

So the strings live here, and code_puller.py imports this module only when
DEBUG_PULL is set AND only after the join has succeeded. With the flag off,
this file is never parsed and costs nothing.

Reads as `# DBG ...` lines on serial.
"""

from time import ticks_ms, ticks_diff

try:
    from ubinascii import hexlify
except ImportError:
    from binascii import hexlify

INTERVAL_MS = 2000


def joined(sta, ssid, bssid, channel, nets, prefix, ticks):
    """Report a SUCCESSFUL join, which nothing did before.

    The failure path already dumps the whole scan. Logging the chosen AP and
    how many hosts were audible on success too is what makes a good run and a
    bad one comparable -- previously there was nothing to compare against.
    """
    n = 0
    if nets:
        for net in nets:
            try:
                if net[0].decode('utf-8').startswith(prefix):
                    n += 1
            except Exception:
                continue
    try:
        bss = hexlify(bssid).decode() if bssid else '?'
    except Exception:
        bss = '?'
    print("# DBG joined %s bssid=%s ch=%s after %d ticks; %d %s* visible"
          % (ssid, bss, channel, ticks, n, prefix))


class BodyProbe:
    """Association state while a file body is arriving.

    code_puller's body loop prints nothing per chunk, which is why a stall
    mid-body and a transfer that never started produced identical logs -- the
    only evidence either way was the ETIMEDOUT at the end. assoc=False here
    says the wand lost the association during the transfer rather than
    stalling in software.
    """

    def __init__(self, sta):
        self.sta = sta
        self.last_ms = ticks_ms()
        self.last_n = -1

    def step(self, received, expected):
        now = ticks_ms()
        if ticks_diff(now, self.last_ms) < INTERVAL_MS:
            return
        self.last_ms = now
        try:
            assoc = self.sta.isconnected() if self.sta is not None else '?'
        except Exception:
            assoc = '?'
        # "STALLED" = not one byte since the previous report. Paired with the
        # server's sel/blocked counters for the same window, that says which
        # side stopped.
        print("# DBG body %d/%d assoc=%s%s"
              % (received, expected, assoc,
                 " STALLED" if received == self.last_n else ""))
        self.last_n = received

    def done(self, received, expected):
        try:
            assoc = self.sta.isconnected() if self.sta is not None else '?'
        except Exception:
            assoc = '?'
        print("# DBG body done %d/%d assoc=%s" % (received, expected, assoc))


def reset_cause(machine):
    """Which reset landed this boot here.

    A soft reset leaves RTC-held radio calibration, the LED strip's latched
    colours and the NFC reader's own state untouched; a power-on clears all
    three. The reported pattern is that a pairing which starts failing keeps
    failing until both devices are fully power-cycled, so this is the field
    that says whether the sticky state is something only a power-on clears.

    Called after the pull, never before -- reading it is free, printing it is
    not, and nothing may print before the radio has its memory.
    """
    c = machine.reset_cause()
    for n in ('PWRON_RESET', 'HARD_RESET', 'WDT_RESET', 'DEEPSLEEP_RESET',
              'SOFT_RESET'):
        if getattr(machine, n, None) == c:
            return "%s (%s)" % (n, c)
    return str(c)
