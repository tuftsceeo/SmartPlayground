"""
pairing.py -- the wand's paired-Splat list on flash
====================================================
/pairing.json holds {"splats": ["AB:42:00:00:7E:B6", ...]} in tap order, at
most MAX_SPLATS entries. Tap order is the local Splat order (SplatGroup
unit 0, unit 1).

main.py clears the file on a power-on reset and reads it inline at boot,
before this module is imported (nothing may allocate ahead of the radio).
This module serves the idle loop: pairing, unpairing and claim checks.

A missing file is an empty list. A corrupt file prints a warning and reads
as an empty list. Writes go to a temp file that is renamed over the real
one; an OSError from the write or the rename propagates, and the previous
file is left in place.
"""

import json
import os

PATH = "/pairing.json"
MAX_SPLATS = 2


def _tmp():
    return PATH + ".tmp"


def _valid(mac):
    if not isinstance(mac, str) or len(mac) != 17:
        return False
    parts = mac.split(":")
    if len(parts) != 6:
        return False
    for p in parts:
        if len(p) != 2:
            return False
        for ch in p:
            if ch not in "0123456789ABCDEF":
                return False
    return True


def load():
    """Paired MACs in tap order; [] if the file is missing or unusable."""
    try:
        with open(PATH, "r") as f:
            raw = f.read()
    except OSError:
        return []
    try:
        data = json.loads(raw)
        items = data["splats"]
        if not isinstance(items, list):
            raise ValueError("splats is not a list")
    except (ValueError, KeyError, TypeError) as e:
        print("  [WARN] pairing: %s unreadable (%s); treating as empty" % (PATH, e))
        return []
    out = []
    for m in items:
        if _valid(m) and m not in out:
            out.append(m)
    return out[:MAX_SPLATS]


def _drop_tmp(tmp):
    try:
        os.stat(tmp)
    except OSError:
        return                  # never created
    try:
        os.remove(tmp)
    except OSError as e:
        print("  [WARN] pairing: could not remove %s: %s" % (tmp, e))


def _write(macs):
    tmp = _tmp()
    try:
        with open(tmp, "w") as f:
            f.write(json.dumps({"splats": macs}))
        os.rename(tmp, PATH)
    except OSError:
        _drop_tmp(tmp)
        raise


def holds(mac):
    return mac in load()


def add(mac):
    """Append mac and write the file. Returns the new list. A MAC already
    held leaves the file alone; ValueError for a malformed MAC or a full list."""
    if not _valid(mac):
        raise ValueError("bad MAC %r" % (mac,))
    macs = load()
    if mac in macs:
        return macs
    if len(macs) >= MAX_SPLATS:
        raise ValueError("already holding %d Splats" % MAX_SPLATS)
    macs.append(mac)
    _write(macs)
    return macs


def remove(mac):
    """Drop mac and write the file; an absent MAC leaves the file alone.
    Removing the last entry deletes the file. Returns the new list."""
    macs = load()
    if mac not in macs:
        return macs
    macs.remove(mac)
    if macs:
        _write(macs)
    else:
        clear()
    return macs


def clear():
    """Delete the file. An absent file is not an error."""
    try:
        os.remove(PATH)
    except OSError:
        if exists():
            raise


def exists():
    try:
        os.stat(PATH)
        return True
    except OSError:
        return False
