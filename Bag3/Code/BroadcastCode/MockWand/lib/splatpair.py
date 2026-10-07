"""
splatpair.py -- a wand's BLE links to its paired Splats
========================================================
Imported by main.py only after enow.init() and, when the wand is paired,
after ubluetooth.BLE().active(True). main.py builds one SplatPairing at boot
for a paired wand (hub + group) and calls poll() on every idle-loop
iteration.

BLE stays active until the next reboot, even after the last Splat is
released; adding a pairing always resets the wand (see main.py), so a
SplatHub is never rebuilt with a different count.
"""

import time

import pairing

PAIR_CONNECT_MS = 30000    # a Splat not READY this long after boot is dropped
UNIT_DRAIN = 8             # most SplatGroup events taken per poll()


class SplatPairing:
    def __init__(self, macs, enow, leds, buz):
        from splat_hub import SplatHub
        from splat_api import SplatGroup
        self.enow = enow
        self.leds = leds
        self.buz = buz
        self.macs = [m for m in macs if pairing.valid(m)][:pairing.MAX_SPLATS]
        if not self.macs:
            raise ValueError("no valid Splat MACs in %r" % (macs,))
        self.hub = SplatHub(count=len(self.macs), macs=self.macs)
        self.group = SplatGroup(self.hub)
        self._born = time.ticks_ms()
        self._deadline_done = False
        self.dropped = []              # MACs dropped since boot, oldest first

    @property
    def count(self):
        return len(self.macs)

    def poll(self):
        """Service the BLE links; enforce PAIR_CONNECT_MS once."""
        g = self.group
        if g is None:
            return
        for _ in range(UNIT_DRAIN):
            if g.poll() is None:
                break
        if (not self._deadline_done
                and time.ticks_diff(time.ticks_ms(), self._born) >= PAIR_CONNECT_MS):
            self._deadline_done = True
            self._drop_unconnected()

    def _drop_unconnected(self):
        # Highest index first so earlier indexes stay valid while dropping.
        lost = [i for i in range(len(self.macs)) if self.hub.links[i].connects == 0]
        for i in reversed(lost):
            print("  [WARN] Splat %s not ready after %d ms; dropping its pairing"
                  % (self.macs[i], PAIR_CONNECT_MS))
            self.release(i)
        if lost:
            self.error_feedback()

    def release(self, i):
        """Disconnect unit i, remove it from the group and the pairing file.
        Returns its MAC. Remaining units keep tap order."""
        hub, group = self.hub, self.group
        mac = self.macs[i]
        if hub.discovering:
            hub.links[0]._stop_scan()
            hub.discovering = False
        link = hub.links[i]
        link.scan_gate = _never
        link.close()
        del hub.links[i]               # group.links is this same list
        del hub.pinned[i]
        del group.units[i]
        del group._pending[:]
        del self.macs[i]
        self.dropped.append(mac)
        pairing.remove(mac)
        if not self.macs:
            self.hub = None
            self.group = None
        return mac

    def error_feedback(self):
        from leds import SHAPE_X, RED
        self.leds.show_shape(SHAPE_X, RED)
        self.buz.reject()
        time.sleep_ms(300)
        self.leds.off()


def _never(link):
    return False
