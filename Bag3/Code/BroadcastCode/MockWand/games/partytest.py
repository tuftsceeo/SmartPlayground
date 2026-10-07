"""
Party Test -- hardware check of the party mechanics
====================================================
Party game (SPLATS_MIN = 2). Every wand taps the same card; the first wand
leads, the others join, and the leader's button starts the game.

  wand button   lights the next pool Splat in the presser's identity color
                (a follower's press goes to the leader as a message; the
                leader's own press is handled directly)
  Splat press   lights that Splat in its owner's identity color
  leader log    each pooled command's send time, for latency checks

The leader turns the Splats off when it leaves. Stop card on any wand leaves
the game; the leader leaving ends it for everyone.

Entry point:
    play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None)
"""

import time
from machine import Pin

from hubtype import HUB_CONFIG
from nfc_reader import read_tag_command
from game_tags import exit_tags_excluding
from splatpair import WAND_RGB

SPLATS_MIN = 2
SPLATS_MAX = None

_EXIT_TAGS = exit_tags_excluding("partytest")

NFC_EVERY = 25          # loops between stop-card reads
NFC_MS = 30             # NFC detect timeout for those reads


def _fill(leds, color):
    for i in range(leds.num):
        leds.np[i] = color
    leds.np.write()


class _Game:
    def __init__(self, nfc, leds, buz, net):
        self.nfc = nfc
        self.leds = leds
        self.buz = buz
        self.net = net
        self.next = 0               # next pool Splat to light
        self.prev = None            # pool Splat lit by the previous press
        self.btn = Pin(HUB_CONFIG["button_pin"], Pin.IN, Pin.PULL_UP)

    def ident(self, wand):
        return self.net.wands[wand][1]

    def light_next(self, presser):
        """Leader: light the next pool Splat in the presser's identity color."""
        net = self.net
        if net.splat_count == 0:
            print("  partytest: no Splats in this party")
            return
        i = self.next % net.splat_count
        self.next += 1
        t0 = time.ticks_ms()
        ok = net.splat(i).color(self.ident(presser))
        print("  partytest: wand %d lit pool Splat %d (wand %d's) %s in %d ms"
              % (presser, i, net.owner(i), "ok" if ok else "FAILED",
                 time.ticks_diff(time.ticks_ms(), t0)))
        if self.prev is not None and self.prev != i:
            net.splat(self.prev).color("turnoff")
        self.prev = i

    def pressed(self):
        """The wand's own button was pressed."""
        if self.net.is_leader:
            self.light_next(self.net.me)
        else:
            ok = self.net.send(0, {"btn": 1})
            print("  partytest: button -> leader %s" % ("ok" if ok else "FAILED"))

    def event(self, ev):
        """One net.poll() event. Returns True when the game should end."""
        net = self.net
        kind = ev[0]
        if kind in ("end", "leader_lost"):
            print("  partytest: %s" % kind)
            return True
        if kind == "msg":
            if net.is_leader and isinstance(ev[2], dict) and ev[2].get("btn") == 1:
                self.light_next(ev[1])
        elif kind == "press":
            if net.is_leader:
                self.ev_splat(ev[1])
            else:
                print("  partytest: local Splat %d pressed" % ev[1])
        elif kind in ("release", "splat_lost", "splat_back", "wand_lost", "wand_back"):
            print("  partytest: %s %s" % (kind, ev[1:]))
        return False

    def ev_splat(self, i):
        t0 = time.ticks_ms()
        ok = self.net.splat(i).color(self.ident(self.net.owner(i)))
        print("  partytest: pool Splat %d pressed; lit for its owner %s in %d ms"
              % (i, "ok" if ok else "FAILED", time.ticks_diff(time.ticks_ms(), t0)))

    def run(self):
        net = self.net
        _fill(self.leds, WAND_RGB[net.wands[net.me][1]])
        was_down = self.btn.value() == 0
        frame = 0
        while True:
            ev = net.poll()
            if ev is not None and self.event(ev):
                return
            down = self.btn.value() == 0
            if down and not was_down:
                self.pressed()
            was_down = down
            frame += 1
            if frame % NFC_EVERY == 0:
                text, _ = read_tag_command(self.nfc, timeout=NFC_MS)
                if text in _EXIT_TAGS:
                    print("  partytest: stop card")
                    if net.is_leader:
                        for i in range(net.splat_count):
                            net.splat(i).off()
                    return
            time.sleep_ms(1)


def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
    if net is None:
        print("  partytest: needs a party (net is None)")
        return
    buz.beep(523, 100)
    print("\n  === PARTY TEST (%s, wand %d of %d, %d Splats) ==="
          % ("leader" if net.is_leader else "follower", net.me, len(net.wands),
             net.splat_count))
    try:
        _Game(nfc, leds, buz, net).run()
    finally:
        leds.off()
        print("\n  === LEAVING PARTY TEST ===\n")
