"""
pairing.py -- the wand's paired-Splat list on flash
====================================================
/pairing.json holds {"splats": ["AB:42:00:00:7E:B6", ...]} in tap order, at
most max_splats() entries: MAX_SPLATS for a game wand, HOST_MAX_SPLATS for a
Splat host (ROLE_PATH holds "splat_host"; see lib/splat_host.py). Tap order is the local Splat order (SplatGroup
unit 0, unit 1).

A host also keeps "slots": HOST_MAX_SPLATS entries, each null or [MAC, A, B],
A and B its color pair (splatpair.pick_pair). A slot whose MAC is not in
"splats" is missing: it keeps its place and pair, and the next new Splat takes
it before any empty slot. clear() forgets every slot.

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
MAX_SPLATS = 2             # a game wand: tested
HOST_MAX_SPLATS = 4        # a Splat host: more than 2 per wand is not yet tested on hardware
ROLE_PATH = "/role.txt"    # same file as main.py _ROLE_PATH


def is_host():
    try:
        with open(ROLE_PATH) as f:
            return f.read().strip() == "splat_host"
    except OSError:
        return False


def max_splats():
    return HOST_MAX_SPLATS if is_host() else MAX_SPLATS


def _tmp():
    return PATH + ".tmp"


def valid(mac):
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
        if valid(m) and m not in out:
            out.append(m)
    return out[:max_splats()]


def _drop_tmp(tmp):
    try:
        os.stat(tmp)
    except OSError:
        return                  # never created
    try:
        os.remove(tmp)
    except OSError as e:
        print("  [WARN] pairing: could not remove %s: %s" % (tmp, e))


def load_slots():
    """Host slots: HOST_MAX_SPLATS entries, each None or [MAC, A, B]."""
    out = [None] * HOST_MAX_SPLATS
    try:
        with open(PATH, "r") as f:
            items = json.loads(f.read()).get("slots") or []
    except (OSError, ValueError, AttributeError):
        return out
    for k in range(min(len(items), HOST_MAX_SPLATS)):
        e = items[k]
        if isinstance(e, list) and len(e) == 3 and valid(e[0]):
            out[k] = e
    return out


def slot_of(slots, mac):
    for k in range(len(slots)):
        if slots[k] is not None and slots[k][0] == mac:
            return k
    return None


def choose_slot(slots, macs, mac):
    """Own slot, else first missing, else first empty, else None."""
    k = slot_of(slots, mac)
    if k is not None:
        return k
    for k in range(len(slots)):
        if slots[k] is not None and slots[k][0] not in macs:
            return k
    for k in range(len(slots)):
        if slots[k] is None:
            return k
    return None


def _write(macs, slots=None):
    if slots is None and is_host():
        slots = load_slots()
    d = {"splats": macs}
    if slots is not None:
        d["slots"] = slots
    tmp = _tmp()
    try:
        with open(tmp, "w") as f:
            f.write(json.dumps(d))
        os.rename(tmp, PATH)
    except OSError:
        _drop_tmp(tmp)
        raise


def holds(mac):
    return mac in load()


def add(mac, pick=None):
    """Append mac and write the file. Returns the new list. A MAC already
    held leaves the file alone; ValueError for a malformed MAC or a full list.
    Host: pick(mac, used) -> (A, B) for a new slot."""
    if not valid(mac):
        raise ValueError("bad MAC %r" % (mac,))
    macs = load()
    if mac in macs:
        return macs
    cap = max_splats()
    if len(macs) >= cap:
        raise ValueError("already holding %d Splats" % cap)
    macs.append(mac)
    slots = None
    if is_host():
        slots = load_slots()
        k = choose_slot(slots, macs, mac)
        if k is None:
            raise ValueError("no free slot")
        if slots[k] is None:
            used = [(e[1], e[2]) for e in slots if e is not None]
            a, b = pick(mac, used) if pick is not None else ("turnwhite", "turnblue")
            slots[k] = [mac, a, b]
        else:
            slots[k] = [mac, slots[k][1], slots[k][2]]
    _write(macs, slots)
    return macs


def remove(mac):
    """Drop mac and write the file; an absent MAC leaves the file alone.
    Removing the last entry deletes the file. Returns the new list."""
    macs = load()
    if mac not in macs:
        return macs
    macs.remove(mac)
    if is_host():
        _write(macs)            # the slot stays, as missing
    elif macs:
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
