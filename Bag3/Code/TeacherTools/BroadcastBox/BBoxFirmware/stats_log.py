"""
stats_log.py — append-only pull / tag-write event log.

Copies reset_log.py's idiom (append, never raise, _trim via temp-file +
rename). Stats are a product feature: they are NOT gated by
reset_log.LOG_ENABLED.

Format (one event per line):
    <ticks> pull <slug> ok|fail
    <ticks> tag  <label> ok

No call sites yet — F3 wires pull + tag write and the stats.* handlers.
"""

import os
import time

PATH = '/flash/stats.log'
MAX_LINES = 200
_SINCE_PATH = '/flash/stats_since.txt'


def _since_ticks():
    try:
        with open(_SINCE_PATH, 'r') as f:
            return int(f.read().strip() or '0')
    except Exception:
        return 0


def _set_since(ticks):
    try:
        with open(_SINCE_PATH, 'w') as f:
            f.write(str(ticks))
    except Exception as e:
        print("# stats_log._set_since failed: %s" % str(e))


def record_pull(slug, ok):
    """Append a pull event. Never raises."""
    _append("%d pull %s %s" % (time.ticks_ms(), slug, "ok" if ok else "fail"))


def record_tag(label):
    """Append a successful tag-write event. Never raises."""
    _append("%d tag %s ok" % (time.ticks_ms(), label))


def _append(line):
    try:
        if _since_ticks() == 0:
            _set_since(time.ticks_ms())
        with open(PATH, 'a') as f:
            f.write(line + "\n")
    except Exception as e:
        print("# stats_log append failed: %s" % str(e))
        return
    try:
        _trim()
    except Exception as e:
        print("# stats_log trim failed: %s" % str(e))


def _trim():
    """Cap the log at MAX_LINES, newest kept, via temp file + rename."""
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


def aggregate():
    """Return {pulls:{slug:n}, writes:{label:n}, since:<ticks>}. Never raises."""
    pulls = {}
    writes = {}
    since = _since_ticks()
    try:
        with open(PATH, 'r') as f:
            lines = f.read().splitlines()
    except OSError:
        return {"pulls": pulls, "writes": writes, "since": since}
    for line in lines:
        parts = line.split()
        if len(parts) < 4:
            continue
        # <ticks> pull <slug> ok|fail
        # <ticks> tag  <label> ok
        kind = parts[1]
        if kind == "pull" and parts[3] == "ok":
            slug = parts[2]
            pulls[slug] = pulls.get(slug, 0) + 1
        elif kind == "tag" and parts[3] == "ok":
            label = parts[2]
            writes[label] = writes.get(label, 0) + 1
    return {"pulls": pulls, "writes": writes, "since": since}


def reset():
    """Truncate the stats log and set since=now. Never raises."""
    try:
        with open(PATH, 'w') as f:
            f.write("")
        _set_since(time.ticks_ms())
    except Exception as e:
        print("# stats_log.reset failed: %s" % str(e))
