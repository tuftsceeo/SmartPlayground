"""
mini_splat.py -- the mini's one Splat link, and the `splats` game argument
===========================================================================
Replaces the Wand's card-based pairing (lib/splatpair.py): there is no NFC
here, so the mini discovers the first Splat advertising by name, or the one
named in /splat_mac.txt ("AB:42:00:00:7E:B6", optional), and reconnects to
it by address if it drops (lib/splat_hub.py).

Import only after the radio is up (main.py's prewarm and ESPNowManager.init).
"""

import time

from splat_hub import SplatHub
from splat_api import SplatGroup

MAC_PATH = "/splat_mac.txt"
UNIT_DRAIN = 8                 # events taken per poll(), as splatpair.UNIT_DRAIN
GLOW = (0, 12, 24)             # dim blue on the Splat while linked and idle


def _read_mac():
    try:
        with open(MAC_PATH) as f:
            mac = f.read().strip().upper()
    except OSError:
        return None
    return mac or None


class MiniSplat:
    def __init__(self):
        mac = _read_mac()
        self.hub = SplatHub(count=1, macs=[mac] if mac else None)
        self.group = SplatGroup(self.hub)
        self._connects = 0
        self._base_gate = self.hub._may_scan
        for link in self.hub.links:
            link.scan_gate = self._gate

    def _gate(self, link):
        return self._base_gate(link)

    @property
    def count(self):
        return 1

    @property
    def connected(self):
        return self.group.connected_count > 0

    def poll(self):
        """Service the link. Returns [(0, "press"/"release"), ...]."""
        events = []
        for _ in range(UNIT_DRAIN):
            ev = self.group.poll()
            if ev is None:
                break
            events.append((self.group.last_index, ev))
        return events

    def take_connect(self):
        """True once per (re)connect."""
        n = self.hub.links[0].connects
        if n != self._connects:
            self._connects = n
            return True
        return False

    def glow(self):
        u = self.group.unit(0)
        if u.connected:
            u._check(u.link.setLEDsON(GLOW), "glow")

    def after_game(self):
        """A game may leave any Splat state behind: clear it, restore the glow."""
        self.group.off()
        self.glow()

    def pause_search(self):
        """No discovery scan while a game runs: at 100% duty it starved
        ESP-NOW on the C6 (splatpair.pause_search). A Splat with a known
        address still reconnects."""
        h = self.hub
        if h.discovering:
            h.links[0]._stop_scan()
            h.discovering = False
        self._base_gate = lambda link: link.direct and h._may_scan(link)

    def resume_search(self):
        self._base_gate = self.hub._may_scan

    def close(self):
        self.hub.close_all()

    def game_handle(self):
        return GameSplats(self)


class GameSplats:
    """The 'splats' play() argument of a SPLATS_LOCAL game (same shape as
    Wand Module/lib/splatpair.py GameSplats).

    count    1
    unit(i)  the Splat: color / note / sound / play / off
    poll()   ("press", i), ("release", i) or None; call every loop
    """

    def __init__(self, ctl):
        self._ctl = ctl
        self._pending = []
        ctl.pause_search()

    @property
    def count(self):
        return 1

    def unit(self, i):
        return self._ctl.group.unit(i)

    def poll(self):
        if not self._pending:
            for i, ev in self._ctl.poll():
                self._pending.append((ev, i))
        if self._pending:
            return self._pending.pop(0)
        return None

    def close(self):
        self._ctl.resume_search()
