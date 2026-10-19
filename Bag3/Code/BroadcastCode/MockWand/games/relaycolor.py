"""
Relay Color -- message-passing party game
==========================================
Party game (SPLATS_MIN = 1). One wand at a time holds a color and shows it on
its own matrix and on its own Splats. Pressing the wand's button, or any of
its own Splats, passes the color to the next wand (a different color each
time); the sender goes dark.

Messages model: every wand drives only its own Splats (net.local) and the
wands talk through net.send(). The token's holder is whoever last received a
{"relay": n} message; each pass also tells the leader {"holder": i, "c": n},
so the leader can re-issue the token if the holder's wand is lost.

Entry point:
    play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None)
"""

import time
from machine import Pin

from hubtype import HUB_CONFIG
from leds import RED, GREEN, BLUE, MAGENTA, AMBER, WHITE, OFF
from nfc_reader import read_tag_command
from game_tags import exit_tags_excluding

SPLATS_MIN = 1
SPLATS_MAX = None

_EXIT_TAGS = exit_tags_excluding("relaycolor")

COLORS = ("turnred", "turngreen", "turnblue", "turnpurple", "turnyellow", "turnwhite")
WAND_COLOR = {"turnred": RED, "turngreen": GREEN, "turnblue": BLUE,
              "turnpurple": MAGENTA, "turnyellow": AMBER, "turnwhite": WHITE}
NFC_EVERY = 25
NFC_MS = 30


class _Relay:
    def __init__(self, nfc, leds, buz, net):
        self.nfc = nfc
        self.leds = leds
        self.buz = buz
        self.net = net
        self.btn = Pin(HUB_CONFIG["button_pin"], Pin.IN, Pin.PULL_UP)
        self.holding = None         # color index while this wand holds the token
        self.holder = 0             # leader: who holds it (wand index)
        self.color = 0              # leader: the color it holds
        self.alive = [True] * len(net.wands)

    def fill(self, rgb):
        for i in range(self.leds.num):
            self.leds.np[i] = rgb
        self.leds.np.write()

    def take(self, c):
        """This wand now holds the token with color index c."""
        self.holding = c
        name = COLORS[c]
        self.fill(WAND_COLOR[name])
        if self.net.local is not None:
            self.net.local.color(name)
        self.buz.beep(660 + 80 * c, 80)
        if self.net.is_leader:
            self.holder = self.net.me
            self.color = c
        print("  relaycolor: holding %s" % name)

    def drop(self):
        self.holding = None
        self.fill(OFF)
        if self.net.local is not None:
            self.net.local.color("turnoff")

    def give(self):
        """Pass the token on: the next wand that ACKs it gets it."""
        net = self.net
        c = (self.holding + 1) % len(COLORS)
        n = len(net.wands)
        for step in range(1, n):
            to = (net.me + step) % n
            if not self.alive[to]:
                continue
            if net.send(to, {"relay": c}):
                self.drop()
                if net.is_leader:
                    self.holder, self.color = to, c
                else:
                    net.send(0, {"holder": to, "c": c})
                print("  relaycolor: passed %s to wand %d" % (COLORS[c], to))
                return
            print("  relaycolor: wand %d did not answer" % to)
        print("  relaycolor: nobody to pass to; keeping %s" % COLORS[self.holding])

    def event(self, ev):
        """One net.poll() event. Returns True when the game should end."""
        net = self.net
        kind = ev[0]
        if kind in ("end", "leader_lost"):
            return True
        if kind == "msg" and isinstance(ev[2], dict):
            d = ev[2]
            if "relay" in d:
                self.take(d["relay"])
            elif "holder" in d and net.is_leader:
                self.holder, self.color = d["holder"], d["c"]
        elif (kind == "press" and self.holding is not None
                and (not net.is_leader or net.owner(ev[1]) == net.me)):
            self.give()                 # a press on one of this wand's own Splats
        elif kind == "wand_lost" and net.is_leader:
            self.alive[ev[1]] = False
            if ev[1] == self.holder:
                self.reissue()
        elif kind == "wand_back" and net.is_leader:
            self.alive[ev[1]] = True
        return False

    def reissue(self):
        """Leader: the holder's wand is gone; hand the token to the next live wand."""
        net = self.net
        n = len(net.wands)
        for step in range(1, n + 1):
            to = (self.holder + step) % n
            if not self.alive[to]:
                continue
            if to == net.me:
                self.take(self.color)
                return
            if net.send(to, {"relay": self.color}):
                self.holder = to
                print("  relaycolor: re-issued %s to wand %d" % (COLORS[self.color], to))
                return

    def run(self):
        net = self.net
        was_down = self.btn.value() == 0
        self.drop()                 # clears the idle glow on this wand's Splats
        if net.is_leader:
            self.take(0)
        frame = 0
        while True:
            ev = net.poll()
            if ev is not None and self.event(ev):
                return
            down = self.btn.value() == 0
            if down and not was_down and self.holding is not None:
                self.give()
            was_down = down
            frame += 1
            if frame % NFC_EVERY == 0:
                text, _ = read_tag_command(self.nfc, timeout=NFC_MS)
                if text in _EXIT_TAGS:
                    return
            time.sleep_ms(1)


def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
    if net is None:
        print("  relaycolor: needs a party (net is None)")
        return
    print("\n  === RELAY COLOR (%s, wand %d of %d) ===" % (
        "leader" if net.is_leader else "follower", net.me, len(net.wands)))
    try:
        _Relay(nfc, leds, buz, net).run()
    finally:
        leds.off()
        if net.local is not None:
            net.local.color("turnoff")
        print("\n  === LEAVING RELAY COLOR ===\n")
