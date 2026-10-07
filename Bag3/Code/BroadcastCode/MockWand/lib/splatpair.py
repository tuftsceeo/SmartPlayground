"""
splatpair.py -- a wand's BLE links to its paired Splats
========================================================
Imported by main.py only after enow.init() and, when the wand is paired,
after ubluetooth.BLE().active(True). main.py builds one SplatPairing: at boot
for a paired wand (hub + group), or on the first Splat card / pw_ message
for an unpaired one (no hub). poll() runs on every idle-loop iteration.

BLE stays active until the next reboot, even after the last Splat is
released; adding a pairing always resets the wand (see on_card), so a
SplatHub is never rebuilt with a different count.
"""

import time

import pairing
import pwire
from leds import (SHAPE_X, SHAPE_CHECK, RED, GREEN, BLUE, MAGENTA, AMBER, WHITE)

PAIR_CONNECT_MS = 30000    # a Splat not READY this long after boot is dropped
CLAIM_WAIT_MS = 300        # how long a pairing tap waits for a pw_held answer
UNIT_DRAIN = 8             # most SplatGroup events taken per poll()
PAIRED_DETECT_MS = 100     # NFC detect timeout while paired (idle loop)
PAIRED_IDLE_SLEEP_MS = 20  # idle-loop sleep while paired
GLOW_SCALE = 0.15          # idle glow brightness on a Splat
CORNER_PIXEL = 4           # wand matrix pixel showing the identity color

# Identity palette: splat_api.COLOR_RGB names, so a wand and its Splats show
# the same name. WAND_RGB gives each name's wand-matrix color.
PALETTE = ("turnred", "turngreen", "turnblue", "turnpurple", "turnyellow", "turnwhite")
WAND_RGB = {
    "turnred": RED, "turngreen": GREEN, "turnblue": BLUE,
    "turnpurple": MAGENTA, "turnyellow": AMBER, "turnwhite": WHITE,
}


def identity_name(mac_str):
    """Palette name for a wand MAC string: last byte modulo the palette size."""
    return PALETTE[int(mac_str[-2:], 16) % len(PALETTE)]


class SplatPairing:
    def __init__(self, macs, enow, leds, buz, my_mac=None):
        self.enow = enow
        self.leds = leds
        self.buz = buz
        if my_mac is None:
            from espnow_manager import get_own_mac
            my_mac = get_own_mac()
        self.my_mac = my_mac
        self.identity = identity_name(my_mac)
        self.macs = [m for m in macs if pairing.valid(m)][:pairing.MAX_SPLATS]
        self.hub = None
        self.group = None
        self.dropped = []              # MACs released since boot, oldest first
        self._connects = []            # per unit: link.connects already handled
        self._born = time.ticks_ms()
        self._deadline_done = False
        if self.macs:
            from splat_hub import SplatHub
            from splat_api import SplatGroup
            self.hub = SplatHub(count=len(self.macs), macs=self.macs)
            self.group = SplatGroup(self.hub)
            self._connects = [0] * len(self.macs)

    @property
    def count(self):
        return len(self.macs)

    @property
    def detect_ms(self):
        return PAIRED_DETECT_MS

    @property
    def idle_sleep_ms(self):
        return PAIRED_IDLE_SLEEP_MS

    # ── idle-loop service ──

    def poll(self):
        """Service the BLE links; flash and glow on a (re)connect; enforce
        PAIR_CONNECT_MS once."""
        g = self.group
        if g is None:
            return
        for _ in range(UNIT_DRAIN):
            if g.poll() is None:
                break
        for i, link in enumerate(self.hub.links):
            if link.connects != self._connects[i]:
                first = self._connects[i] == 0
                self._connects[i] = link.connects
                self._on_ready(i, first)
        if (not self._deadline_done
                and time.ticks_diff(time.ticks_ms(), self._born) >= PAIR_CONNECT_MS):
            self._deadline_done = True
            self._drop_unconnected()

    def _on_ready(self, i, first):
        if first:
            # UNVERIFIED on hardware: how the flash and rising tone look and sound.
            self.group.unit(i).color(self.identity)
            self.leds.flash_color(WAND_RGB[self.identity], times=2)
            self.buz.success()
        self.glow(i)

    def glow(self, i=None):
        """Dim identity color on Splat i (every connected Splat if None)."""
        from splat_api import COLOR_RGB
        r, g, b = COLOR_RGB[self.identity]
        rgb = (int(r * GLOW_SCALE), int(g * GLOW_SCALE), int(b * GLOW_SCALE))
        if self.group is None:
            return
        units = self.group.units if i is None else [self.group.unit(i)]
        for u in units:
            if u.connected:
                u._check(u.link.setLEDsON(rgb), "glow")

    def after_game(self):
        """A game may leave any Splat state behind: clear it and restore the glow."""
        if self.group is None:
            return
        self.group.off()
        self.glow()

    def mark(self, leds):
        """Identity color in one corner pixel of the wand matrix."""
        if self.macs:
            leds.np[CORNER_PIXEL] = WAND_RGB[self.identity]
            leds.np.write()

    # ── ESP-NOW ──

    def on_msg(self, data, sender):
        """Handle a raw pw_ message from the idle loop or a running game.
        Returns "who" (a claim query, answered or not) or "release" (a
        release-all, done), or None for anything else."""
        t = data.get("type")
        if t == "pw_who":
            if data.get("m") in self.macs:
                added = pwire.ensure_peer(self.enow, sender)
                pwire.send_acked(self.enow, sender, {"type": "pw_held", "m": data["m"]})
                if added:
                    self.enow.remove_peer(sender)
            return "who"
        if t == "pw_release_all":
            self.release_all()
            return "release"
        return None

    # ── pairing and unpairing ──

    def on_card(self, text):
        """Act on a Splat card or the unpair card from the idle loop. Returns
        "reset" when the wand must reset to pick up a new pairing, else None."""
        if text == "unpair":
            print("  unpair: releasing %d Splat(s)" % self.count)
            self.release_all()
            self.ok_feedback()
            return None
        from nfc_reader import parse_splat_card
        mac = parse_splat_card(text)
        if mac is None:
            raise ValueError("not a Splat card: %r" % text)
        if mac in self.macs:
            print("  Splat %s: unpairing" % mac)
            self.release(self.macs.index(mac))
            self.ok_feedback()
            return None
        if self.count >= pairing.MAX_SPLATS:
            print("  Splat %s: this wand already holds %d" % (mac, pairing.MAX_SPLATS))
            self.error_feedback()
            return None
        if self.claimed_elsewhere(mac):
            print("  Splat %s: already paired to another wand" % mac)
            self.error_feedback()
            return None
        try:
            pairing.add(mac)
        except OSError as e:
            print("  [ERR] pairing file write failed: %s" % e)
            self.error_feedback()
            return None
        print("  Splat %s: paired, resetting to connect" % mac)
        self.ok_feedback()
        return "reset"

    def claimed_elsewhere(self, mac):
        """Broadcast pw_who and listen CLAIM_WAIT_MS for a pw_held answer."""
        if not self.enow.is_active:
            print("  [WARN] ESP-NOW is down; cannot check whether %s is held" % mac)
            return True
        self.enow.broadcast({"type": "pw_who", "m": mac})
        end = time.ticks_add(time.ticks_ms(), CLAIM_WAIT_MS)
        held = False
        while time.ticks_diff(end, time.ticks_ms()) > 0:
            mt, data, sender = self.enow.poll()
            if mt == "raw" and isinstance(data, dict):
                if data.get("type") == "pw_held" and data.get("m") == mac:
                    held = True
                else:
                    self.on_msg(data, sender)
            time.sleep_ms(1)
        return held

    def release_all(self):
        if self.group is not None:
            for i in range(len(self.macs) - 1, -1, -1):
                self.release(i)
        pairing.clear()

    def release(self, i):
        """Disconnect unit i, remove it from the group and the pairing file.
        Returns its MAC. Remaining units keep tap order."""
        hub, group = self.hub, self.group
        mac = self.macs[i]
        group.unit(i).off()
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
        del self._connects[i]
        del self.macs[i]
        self.dropped.append(mac)
        pairing.remove(mac)
        if not self.macs:
            self.hub = None
            self.group = None
        return mac

    def _drop_unconnected(self):
        lost = [i for i in range(len(self.macs)) if self.hub.links[i].connects == 0]
        for i in reversed(lost):
            print("  [WARN] Splat %s not ready after %d ms; dropping its pairing"
                  % (self.macs[i], PAIR_CONNECT_MS))
            self.release(i)
        if lost:
            self.error_feedback()

    # ── feedback ──

    def error_feedback(self):
        self.leds.show_shape(SHAPE_X, RED)
        self.buz.reject()
        time.sleep_ms(300)
        self.leds.off()

    def ok_feedback(self):
        self.leds.show_shape(SHAPE_CHECK, GREEN)
        self.buz.confirm()
        time.sleep_ms(300)
        self.leds.off()


def _never(link):
    return False
