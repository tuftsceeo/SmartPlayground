"""
pairing.py -- wand-to-Splat pairing store, boot bring-up and local Splats
==========================================================================
SPEC: docs_and_design/2026-10-07-splat-pairing/SPEC.md sections 2, 4, 5, 9.

Imported by main.py only after enow.init() (AGENTS.md memory-order rule).
An unpaired wand imports this module but never ubluetooth or the Splat
libraries.

Store: /pairing.json = {"splats": ["AB:42:00:00:7E:B6", ...]}, tap order,
at most MAX_SPLATS entries. Written atomically (tmp + rename). A missing or
corrupt file reads as empty. Deleted at boot after a power-on reset.

Public API for game-side libraries (party.py, SoloNet):

    pairing.local()            -> LocalSplats, or None if this wand is unpaired
    ls.macs                    -> paired MACs still held, local order
    ls.count                   -> len(ls.macs)
    ls.ready()                 -> list of local indexes whose link is READY
    ls.is_ready(i)             -> bool
    ls.splat(i)                -> splat_api.SplatAPI for local index i
                                  (color/sound/note/play/off; IndexError past count)
    ls.poll()                  -> one event or None, oldest first:
                                  ("press", i) / ("release", i)
                                  ("splat_lost", i) / ("splat_back", i)
                                  Services every link (keepalives, reconnects);
                                  call every loop iteration.
    ls.off()                   -> off() on every held Splat
    ls.identity                -> (color_name, wand_rgb) for this wand
    pairing.identity(mac_str)  -> same, for any wand MAC

Local index i counts held Splats only: after one is unpaired, the indexes
of the ones after it shift down by one.

UNVERIFIED on hardware: BLE bring-up after enow.init() with this module
imported first; PAIR_CONNECT_MS; IDENTITY palette distinctness on a Splat.
"""

import json
import os
import time

PAIR_FILE = "/pairing.json"
MAX_SPLATS = 2               # gate G2 sets the final value
PAIR_CONNECT_MS = 30000      # a Splat not READY this long after boot is dropped

# Identity palette: (splat_api.COLOR_RGB name, wand matrix RGB). Indexed by
# the last byte of the wand's MAC.
IDENTITY = (
    ("turnred", (130, 0, 0)),
    ("turngreen", (0, 230, 0)),
    ("turnblue", (0, 20, 255)),
    ("turnpurple", (50, 0, 250)),
    ("turnyellow", (110, 120, 0)),
    ("turnwhite", (140, 150, 150)),
)

_HEX = "0123456789ABCDEF"


def parse_splat_card(text):
    """"splat-ab4200007eb6" -> "AB:42:00:00:7E:B6"; anything else -> None."""
    if not isinstance(text, str) or len(text) != 18:
        return None
    if text[:6].lower() != "splat-":
        return None
    h = text[6:].upper()
    for ch in h:
        if ch not in _HEX:
            return None
    return ":".join([h[i:i + 2] for i in range(0, 12, 2)])


def identity(mac_str):
    return IDENTITY[int(mac_str[-2:], 16) % len(IDENTITY)]


# ─── Store ───────────────────────────────────

def load(path=None):
    path = path or PAIR_FILE
    try:
        with open(path) as f:
            data = json.load(f)
    except OSError:
        return []
    except ValueError as e:
        print(f"  pairing: {path} unreadable ({e}); treating as empty")
        return []
    macs = data.get("splats") if isinstance(data, dict) else None
    if not isinstance(macs, list):
        return []
    out = []
    for m in macs:
        if isinstance(m, str) and m not in out:
            out.append(m.upper())
    return out[:MAX_SPLATS]


def _save(macs, path):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"splats": macs}, f)
    os.rename(tmp, path)


def add(mac, path=None):
    """Append mac. Returns False if already held or the store is full."""
    path = path or PAIR_FILE
    macs = load(path)
    mac = mac.upper()
    if mac in macs or len(macs) >= MAX_SPLATS:
        return False
    macs.append(mac)
    _save(macs, path)
    return True


def remove(mac, path=None):
    path = path or PAIR_FILE
    macs = load(path)
    mac = mac.upper()
    if mac not in macs:
        return False
    macs.remove(mac)
    if macs:
        _save(macs, path)
    else:
        clear(path)
    return True


def clear(path=None):
    try:
        os.remove(path or PAIR_FILE)
    except OSError:
        pass


# ─── Boot ────────────────────────────────────

_local = None


def local():
    return _local


def boot(machine, own_mac=None, path=None):
    """SPEC section 4 steps 3-4. Call right after enow.init().

    Returns None when unpaired, True when BLE and the Splat links are up,
    False when BLE bring-up failed (file cleared, wand continues unpaired).
    """
    global _local
    path = path or PAIR_FILE
    if machine.reset_cause() == machine.PWRON_RESET:
        clear(path)
        return None
    macs = load(path)
    if not macs:
        return None
    if own_mac is None:
        from espnow_manager import get_own_mac
        own_mac = get_own_mac()
    try:
        import ubluetooth
        ubluetooth.BLE().active(True)
        from splat_hub import SplatHub
        from splat_api import SplatGroup
        hub = SplatHub(count=len(macs), macs=macs)
        _local = LocalSplats(hub, SplatGroup(hub), macs, own_mac, path)
    except Exception as e:
        print("  [WARN] pairing: BLE bring-up failed; booting unpaired")
        import sys
        sys.print_exception(e)
        clear(path)
        _local = None
        return False
    print(f"  pairing: {len(macs)} Splat(s) {macs}")
    return True


class LocalSplats:
    """This wand's paired Splats. See the module docstring for the API."""

    def __init__(self, hub, group, macs, own_mac, path):
        self.hub = hub
        self.group = group
        self.path = path
        self.identity = identity(own_mac)
        self._units = list(range(len(macs)))   # hub unit index per local index
        self._all_macs = list(macs)
        self._was_ready = [False] * len(macs)
        self._ever_ready = [False] * len(macs)
        self._boot_ms = time.ticks_ms()
        self._events = []

    @property
    def macs(self):
        return [self._all_macs[u] for u in self._units]

    @property
    def count(self):
        return len(self._units)

    def splat(self, i):
        return self.group.units[self._units[i]]

    def is_ready(self, i):
        return self.group.units[self._units[i]].connected

    def ready(self):
        return [i for i in range(len(self._units)) if self.is_ready(i)]

    def index_of(self, mac):
        mac = mac.upper()
        for i, u in enumerate(self._units):
            if self._all_macs[u] == mac:
                return i
        return None

    def poll(self):
        ev = self.group.poll()
        if ev is not None:
            u = self.group.last_index
            if u in self._units:
                self._events.append((ev, self._units.index(u)))
        for i, u in enumerate(self._units):
            up = self.group.units[u].connected
            if up != self._was_ready[u]:
                self._was_ready[u] = up
                if up:
                    self._ever_ready[u] = True
                self._events.append(("splat_back" if up else "splat_lost", i))
        if self._events:
            return self._events.pop(0)
        return None

    def off(self):
        ok = True
        for i in range(len(self._units)):
            ok = self.splat(i).off() and ok
        return ok

    def overdue(self):
        """MACs never READY within PAIR_CONNECT_MS of boot (SPEC section 4)."""
        if time.ticks_diff(time.ticks_ms(), self._boot_ms) < PAIR_CONNECT_MS:
            return []
        return [self._all_macs[u] for u in self._units if not self._ever_ready[u]]

    def release(self, mac):
        """Disconnect one Splat, stop it reconnecting, drop it from the store.
        BLE stays active (SPEC section 3)."""
        i = self.index_of(mac)
        if i is None:
            return False
        u = self._units.pop(i)
        link = self.hub.links[u]
        link.scan_gate = lambda l: False
        link.close()
        self._events = [e for e in self._events if e[1] != i]
        self._events = [(e[0], e[1] - 1) if e[1] > i else e for e in self._events]
        remove(mac, self.path)
        return True

    def release_all(self):
        for mac in self.macs:
            self.release(mac)
        clear(self.path)
