"""
reset_log.py — persist machine.reset_cause() across the USB CDC drop.

The Box's USB is native CDC: a reset drops the port itself, so any panic
message or reset-cause read taken *before* the reset goes into a port the
host has already lost (see known_issue.md). The only way to observe why the
box reset is to write the cause to flash on this boot and read it back on
the next one.

Usage: call record() once, early in BboxServer.run(), before the boot grace
so a fresh reset_cause() reading is captured before anything else can raise.
"""

import time
import machine

PATH = '/flash/resetlog.txt'
MAX_LINES = 40

# Not every reset_cause() value machine exposes is meaningful here, and not
# every port defines all of them (BROWNOUT_RESET in particular is a
# recent-ish addition on the ESP32 port) -- look each one up with getattr so
# a missing attribute degrades to the numeric fallback in cause_name()
# instead of raising at import time.
_CAUSE_NAMES = {
    getattr(machine, 'PWRON_RESET', -1): 'PWRON',
    getattr(machine, 'HARD_RESET', -2): 'HARD',
    getattr(machine, 'WDT_RESET', -3): 'WDT',
    getattr(machine, 'DEEPSLEEP_RESET', -4): 'DEEPSLEEP',
    getattr(machine, 'SOFT_RESET', -5): 'SOFT',
    getattr(machine, 'BROWNOUT_RESET', -6): 'BROWNOUT',
}


def cause_name(c):
    """Map a machine.reset_cause() value to a short discriminating label."""
    return _CAUSE_NAMES.get(c, '?%s' % c)


def record(note=""):
    """Append one line for this boot's reset cause; never raises.

    Format: '<ticks_ms> <cause> <note>', newest entry last in the file.
    Trims to MAX_LINES on every call so the log cannot grow unbounded on a
    device with no filesystem housekeeping. A full or read-only filesystem
    degrades to a printed warning rather than crashing the caller -- this
    must not be the reason the box fails to boot.
    """
    try:
        cause = cause_name(machine.reset_cause())
        line = "%d %s %s" % (time.ticks_ms(), cause, note)
        lines = []
        try:
            with open(PATH, 'r') as f:
                lines = f.read().splitlines()
        except OSError:
            pass  # no log yet, or filesystem unreadable -- start fresh
        lines.append(line)
        if len(lines) > MAX_LINES:
            lines = lines[-MAX_LINES:]
        with open(PATH, 'w') as f:
            f.write('\n'.join(lines) + '\n')
    except Exception as e:
        print("# reset_log.record() failed: %s" % str(e))


def last(n=5):
    """Return up to the n most recent log lines, newest-first.

    Never raises: a missing or unreadable file returns an empty list.
    """
    try:
        with open(PATH, 'r') as f:
            lines = f.read().splitlines()
    except OSError:
        return []
    return list(reversed(lines[-n:])) if n > 0 else []
