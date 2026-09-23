"""
pull_flag.py — "pull code on next boot" flag, stored on flash.

Why this exists
---------------
A WiFi join only succeeds on a radio that ESP-NOW has never touched this
boot. Measured on real hardware, same wand, same Box, same code:

  cold  (ESP-NOW never initialised)  -> joins and transfers, first try
  warm  (ESP-NOW ran, then shut down) -> 3/3 real NFC taps failed, either
        STAT_WRONG_PASSWORD then stuck STAT_CONNECTING, or STAT_IDLE for
        the whole 15s window (connect() never even took)

MicroPython exposes esp_wifi_stop() (network.WLAN.active(False)) but not
esp_wifi_deinit(), so whatever ESP-NOW leaves behind cannot be cleared from
Python. A full chip reset can clear it.

The wand already reboots after a successful pull, so the round trip was
never needed -- only ESP-NOW -> WiFi *within one boot* has to be avoided.
This flag is how a tap in the ESP-NOW-owning boot hands the job to a fresh
boot that owns the radio instead:

    tap "getcode:<slug>@<id>" -> set_pending(slug, host_id) -> machine.reset()
    next boot           -> is_pending()  -> pull on a cold radio -> reset again

Format: three text lines --

    line 1: the attempt count
    line 2: the requested slug ("" = "whatever the Box has active")
    line 3: the requested host id ("" = "whatever SP-FILEPUSH* answers
            strongest" -- see code_puller.py's _find_ap())

The count is bumped *before* each attempt so a hard crash mid-pull still
spends budget and cannot boot-loop. The slug and host id are what the
tapped card asked for ("getcode:<slug>@<id>"); they have to be stored here
because the tap and the pull happen in *different boots*, and nothing else
survives the reset. Line 3 is new; a flag written by older firmware simply
has no line 3, and _read() below treats that the same as an empty host id.
"""

PATH = "/pullpending"
MAX_ATTEMPTS = 2


def is_pending():
    """True if a pull is queued for this boot.

    Existence is the flag; the contents are only the attempt counter, so a
    truncated or empty file still counts as pending (with 0 attempts spent).
    """
    try:
        import os
        os.stat(PATH)
        return True
    except OSError:
        return False


def _read():
    """(attempts, slug, host_id). Returns (0, "", "") when unset, empty or
    unreadable.

    A truncated or malformed file still counts as pending with a fresh
    budget -- losing the flag entirely would silently drop the teacher's tap.
    A file with no line 3 (written by older firmware) reads as host_id="".
    """
    try:
        with open(PATH, "r") as f:
            raw = f.read()
    except OSError:
        return 0, "", ""
    lines = raw.split("\n")
    try:
        n = int(lines[0].strip()) if lines[0].strip() else 0
    except ValueError:
        n = 0
    slug = lines[1].strip() if len(lines) > 1 else ""
    host_id = lines[2].strip() if len(lines) > 2 else ""
    return n, slug, host_id


def attempts():
    """How many attempts have already been spent. 0 if unset/unreadable."""
    return _read()[0]


def requested_slug():
    """The slug the card asked for, or "" for "whatever the Box has active"."""
    return _read()[1]


def requested_host():
    """The host id the card asked for, or "" for "whatever SP-FILEPUSH*
    answers strongest" -- see code_puller.py's _find_ap()."""
    return _read()[2]


def _write(n, slug, host_id):
    # Closed before returning: the caller resets the chip moments later and
    # an unflushed buffer would lose the flag entirely.
    with open(PATH, "w") as f:
        f.write("%d\n%s\n%s" % (n, slug or "", host_id or ""))


def set_pending(slug="", host_id=""):
    """Queue a pull for the next boot. Attempt budget starts fresh."""
    _write(0, slug, host_id)


def bump():
    """Spend one attempt. Returns the new count. Keeps the requested
    slug/host_id."""
    n, slug, host_id = _read()
    n += 1
    _write(n, slug, host_id)
    return n


def budget_left():
    return attempts() < MAX_ATTEMPTS


def clear():
    """Remove the flag. Safe to call when it does not exist."""
    try:
        import os
        os.remove(PATH)
    except OSError:
        pass
