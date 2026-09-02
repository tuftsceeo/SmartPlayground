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

import os
import time
import machine

PATH = '/flash/resetlog.txt'
MODE_PATH = '/flash/lastmode.txt'
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


def note_mode(mode):
    """Persist the mode the box is entering; never raises.

    Called on every mode change so the NEXT boot can say which mode the box
    was in when it stopped. It has to be persisted rather than read at the
    time, because reset_cause() is only meaningful after the reset -- and
    the board's USB CDC port drops with the reset, so nothing can be
    reported as it happens. Mode changes are teacher-paced, seconds apart at
    most, so one small flash write per change costs nothing.
    """
    try:
        with open(MODE_PATH, 'w') as f:
            f.write(str(mode))
    except Exception as e:
        print("# reset_log.note_mode() failed: %s" % str(e))


def last_mode():
    """Mode persisted before the last reset, or '?' if none is recorded."""
    try:
        with open(MODE_PATH, 'r') as f:
            m = f.read().strip()
        return m if m else '?'
    except Exception:
        return '?'


def record(note=""):
    """Append one line for this boot's reset cause; never raises.

    Format: '<ticks_ms> <cause> was:<mode> [note]', newest entry last.

    The mode comes from note_mode()'s file, i.e. the mode the box was in
    before this reset -- NOT the current one, which at call time is still
    the constructor default and told you nothing.

    Appends rather than rewriting. This module exists to survive brownouts,
    and a brownout landing inside a truncate-then-rewrite loses the whole
    history at exactly the moment it is worth having -- an interrupted
    open(PATH, 'w') leaves an empty file. Trimming is therefore split out
    into _trim(), which only runs when the log is actually over length and
    writes through a temp file so the live log is never the truncated one.

    A full or read-only filesystem degrades to a printed warning rather than
    crashing the caller -- this must not be the reason the box fails to boot.
    """
    try:
        cause = cause_name(machine.reset_cause())
        line = "%d %s was:%s" % (time.ticks_ms(), cause, last_mode())
        if note:
            line += " " + str(note)
        with open(PATH, 'a') as f:
            f.write(line + "\n")
    except Exception as e:
        print("# reset_log.record() failed: %s" % str(e))
        return
    try:
        _trim()
    except Exception as e:
        print("# reset_log trim failed: %s" % str(e))


def _trim():
    """Cap the log at MAX_LINES, newest kept, via temp file + rename.

    A crash mid-trim leaves either the old full log or the new trimmed one,
    never an empty file.
    """
    with open(PATH, 'r') as f:
        lines = f.read().splitlines()
    if len(lines) <= MAX_LINES:
        return
    tmp = PATH + '.tmp'
    with open(tmp, 'w') as f:
        f.write('\n'.join(lines[-MAX_LINES:]) + '\n')
    try:
        os.remove(PATH)
    except OSError:
        pass
    os.rename(tmp, PATH)


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
