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
# A dropped Splat: normal retries for LOST_RETRY_MS, then the lost glyph and
# retries spaced by LOST_GAPS_MS (each after a connect attempt of up to
# splat_link.CONNECT_TIMEOUT_MS) until LOST_GIVE_UP_MS, then it is released.
LOST_RETRY_MS = 30000
LOST_GAPS_MS = (20000, 40000, 80000)
LOST_GIVE_UP_MS = 150000
# Written just before the reset that follows a Splat card tap; main.py keeps
# the pairing only on that boot.
PAIR_BOOT_PATH = "/pair_boot"
# Splat lost: a dotted ring, shown in the wand's identity color. No other
# wand screen uses it.
SHAPE_SPLAT_LOST = (1, 3, 5, 9, 15, 19, 21, 23)
GLOW_SCALE = 0.5           # idle glow brightness on a Splat
GLOW_REFRESH_MS = 5000     # idle glow is rewritten this often (one-color code)
GLOW_ALT_MS = 1000         # two-color code: the glow alternates this often
CORNER_PIXEL = 4           # wand matrix pixel showing the identity color
SECOND_PIXEL = 3           # wand matrix pixel showing the second color

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


def second_name(mac_str):
    """Second color of the wand's two-color code: next-to-last MAC byte modulo
    the palette size. Equal to identity_name() for one wand in six."""
    return PALETTE[int(mac_str[-5:-3], 16) % len(PALETTE)]


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
        self.second = second_name(my_mac)
        self._phase = 0                # 0: identity, 1: second (two-color glow)
        self.macs = [m for m in macs if pairing.valid(m)][:pairing.MAX_SPLATS]
        self.hub = None
        self.group = None
        self.dropped = []              # MACs released since boot, oldest first
        self._connects = []            # per unit: link.connects already handled
        self._born = time.ticks_ms()
        self._deadline_done = False
        self._last_glow = self._born
        if self.macs:
            from splat_hub import SplatHub
            from splat_api import SplatGroup
            self.hub = SplatHub(count=len(self.macs), macs=self.macs)
            self.group = SplatGroup(self.hub)
            self._connects = [0] * len(self.macs)
            self._base_gate = self.hub._may_scan
            self._drops = [0] * len(self.macs)
            self._lost_at = [None] * len(self.macs)
            self._lost_step = [0] * len(self.macs)
            self._next_try = [0] * len(self.macs)
            self._slow = [False] * len(self.macs)
            for link in self.hub.links:
                link.scan_gate = self._gate

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
        PAIR_CONNECT_MS once. Returns the Splat button events taken, as
        [(unit index, "press" or "release"), ...]; the idle loop answers presses."""
        g = self.group
        if g is None:
            return []
        events = []
        for _ in range(UNIT_DRAIN):
            ev = g.poll()
            if ev is None:
                break
            events.append((g.last_index, ev))
        for i, link in enumerate(self.hub.links):
            if link.connects != self._connects[i]:
                first = self._connects[i] == 0
                self._connects[i] = link.connects
                self._on_ready(i, first)
        if (not self._deadline_done
                and time.ticks_diff(time.ticks_ms(), self._born) >= PAIR_CONNECT_MS):
            self._deadline_done = True
            self._drop_unconnected()
        self._track_lost()
        return events

    # ── dropped Splats ──

    def _gate(self, link):
        """scan_gate: the hub's gate, spaced out once a dropped Splat has been
        lost for LOST_RETRY_MS."""
        if not self._base_gate(link):
            return False
        i = self.hub.links.index(link)
        if not self._slow[i]:
            return True
        now = time.ticks_ms()
        if time.ticks_diff(now, self._next_try[i]) < 0:
            return False
        from splat_link import CONNECT_TIMEOUT_MS
        step = self._lost_step[i]
        gap = LOST_GAPS_MS[min(step, len(LOST_GAPS_MS) - 1)]
        self._lost_step[i] = step + 1
        self._next_try[i] = time.ticks_add(now, CONNECT_TIMEOUT_MS + gap)
        return True

    def _track_lost(self):
        now = time.ticks_ms()
        for i in range(len(self.macs) - 1, -1, -1):
            link = self.hub.links[i]
            if link.drops != self._drops[i]:
                self._drops[i] = link.drops
                if self._lost_at[i] is None:
                    self._lost_at[i] = now
                    self._lost_step[i] = 0
                    self._slow[i] = False
                    print("  Splat %s lost; retrying" % self.macs[i])
            lost = self._lost_at[i]
            if lost is None:
                continue
            if link.ready:
                self._lost_at[i] = None
                self._slow[i] = False
                print("  Splat %s back" % self.macs[i])
                continue
            age = time.ticks_diff(now, lost)
            if age >= LOST_GIVE_UP_MS:
                print("  Splat %s not back after %d ms; releasing" % (self.macs[i], age))
                self.release(i)
                self.lost_feedback()
            elif age >= LOST_RETRY_MS and not self._slow[i]:
                self._slow[i] = True
                self._next_try[i] = now
                print("  Splat %s still lost; slower retries" % self.macs[i])
                self.lost_feedback()

    def refresh_glow(self):
        """Rewrite the idle glow every GLOW_REFRESH_MS. Idle loop only: a game owns
        the Splat colors while it runs."""
        two = self.second != self.identity
        if time.ticks_diff(time.ticks_ms(), self._last_glow) >= (GLOW_ALT_MS if two else GLOW_REFRESH_MS):
            if two:
                self._phase ^= 1
            self.glow()

    def on_press(self, i):
        """A press on paired Splat i, at idle: the Splat shows the identity color
        at full brightness and the wand flashes its two-color code and beeps."""
        # UNVERIFIED on hardware: how the press answer looks and sounds.
        if self.group is None or i >= len(self.group.units):
            return
        self.group.unit(i).color(self.identity)
        self.leds.flash_color(WAND_RGB[self.identity], times=1)
        self.leds.flash_color(WAND_RGB[self.second], times=1)
        self.buz.beep(1500, 60)
        self._last_glow = time.ticks_ms()

    def _on_ready(self, i, first):
        if first:
            # UNVERIFIED on hardware: how the flash and rising tone look and sound.
            self.group.unit(i).color(self.identity)
            self.leds.flash_color(WAND_RGB[self.identity], times=2)
            self.buz.success()
        self.glow(i)

    def pause_search(self):
        """Stop SplatHub's discovery scan for the rest of a lobby game. It runs
        at 100% duty while no Splat is connected, and on the C6 that starved
        ESP-NOW: a lobby game wand whose Splat was asleep lost the leader's
        heartbeats for 3 s. A Splat with a known address (link.direct) still
        reconnects; one never found waits for resume_search()."""
        h = self.hub
        if h is None:
            return
        if h.discovering:
            h.links[0]._stop_scan()
            h.discovering = False
        self._base_gate = lambda link: link.direct and h._may_scan(link)

    def resume_search(self):
        """Let SplatHub scan and reconnect again (after a lobby game)."""
        h = self.hub
        if h is None:
            return
        self._base_gate = h._may_scan

    def glow(self, i=None):
        """Glow color on Splat i (every connected Splat if None): the identity
        color, or the second color in the second phase of a two-color code."""
        from splat_api import COLOR_RGB
        r, g, b = COLOR_RGB[self.second if self._phase else self.identity]
        rgb = (int(r * GLOW_SCALE), int(g * GLOW_SCALE), int(b * GLOW_SCALE))
        if self.group is None:
            return
        if i is None:
            self._last_glow = time.ticks_ms()
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
        """Two-color code in the top corner of the wand matrix."""
        if self.macs:
            leds.np[CORNER_PIXEL] = WAND_RGB[self.identity]
            leds.np[SECOND_PIXEL] = WAND_RGB[self.second]
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
        try:
            with open(PAIR_BOOT_PATH, "w") as f:
                f.write("1")
        except OSError as e:
            print("  [ERR] pair_boot write failed: %s" % e)
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
        if self._drops:
            del self._drops[i]
            del self._lost_at[i]
            del self._lost_step[i]
            del self._next_try[i]
            del self._slow[i]
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

    def lost_feedback(self):
        """Splat lost: the dotted ring in the identity color, blinked 3 times."""
        c = WAND_RGB[self.identity]
        for _ in range(3):
            self.leds.show_shape(SHAPE_SPLAT_LOST, c)
            time.sleep_ms(250)
            self.leds.off()
            time.sleep_ms(150)
        self.buz.warn()

    def ok_feedback(self):
        self.leds.show_shape(SHAPE_CHECK, GREEN)
        self.buz.confirm()
        time.sleep_ms(300)
        self.leds.off()


def _never(link):
    return False
