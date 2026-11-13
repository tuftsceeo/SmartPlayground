"""
Host Relay Color -- pass a color token between players
======================================================
Splat host game (SPLAT_HOST = True), ported from games/relaycolor.py. One
player holds the token (their wand lit, every Splat on the host in their
identity color). The holder's button passes it to the next player. The host
broadcasts relay_pass for an icon display, as relaycolor does.

Entry point:
    play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None)
"""

import time
from machine import Pin

from hubtype import HUB_CONFIG
from nfc_reader import read_tag_command
from game_tags import exit_tags_excluding
from splatpair import WAND_RGB

SPLAT_HOST = True
SPLATS_MIN = 1
SPLATS_MAX = 4
PLAYERS_MIN = 2

_EXIT_TAGS = exit_tags_excluding("host_relaycolor")

NFC_EVERY = 25
NFC_MS = 30


def _fill(leds, color):
    for i in range(leds.num):
        leds.np[i] = color
    leds.np.write()


class _Relay:
    def __init__(self, nfc, leds, buz, enow, net):
        self.nfc = nfc
        self.leds = leds
        self.buz = buz
        self.enow = enow
        self.net = net
        self.holder = None
        self.btn = Pin(HUB_CONFIG["button_pin"], Pin.IN, Pin.PULL_UP)

    def give(self, p):
        """Host: hand the token to player p."""
        net = self.net
        self.holder = p
        name = net.wands[p][1]
        for i in range(net.splat_count):
            net.splat(i).color(name)
        net.send(None, {"h": p})
        self.enow.broadcast({"type": "relay_pass", "to": p, "color": name})
        print("  host_relaycolor: token -> player %d" % p)

    def show(self):
        net = self.net
        if self.holder == net.me:
            _fill(self.leds, WAND_RGB[net.ident])
            self.buz.beep(880, 80)
        else:
            self.leds.off()

    def run(self):
        net = self.net
        players = net.players
        if net.is_host:
            self.give(players[0])
        was_down = self.btn.value() == 0
        frame = 0
        while True:
            ev = net.poll()
            if ev is not None:
                if ev[0] in ("end", "leader_lost"):
                    return
                if ev[0] == "msg" and isinstance(ev[2], dict):
                    d = ev[2]
                    if net.is_host and d.get("pass") == 1 and ev[1] == self.holder:
                        k = players.index(self.holder)
                        self.give(players[(k + 1) % len(players)])
                    elif not net.is_host and "h" in d:
                        self.holder = d["h"]
                        self.show()
            down = self.btn.value() == 0
            if down and not was_down and not net.is_host and self.holder == net.me:
                net.send(0, {"pass": 1})
            was_down = down
            frame += 1
            if frame % NFC_EVERY == 0:
                text, _ = read_tag_command(self.nfc, timeout=NFC_MS)
                if text in _EXIT_TAGS:
                    return
            time.sleep_ms(1)


def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
    if net is None:
        print("  host_relaycolor: needs a Splat host lobby (net is None)")
        return
    print("\n  === HOST RELAY COLOR (%s, %d players) ==="
          % ("host" if net.is_host else "player", len(net.players)))
    try:
        _Relay(nfc, leds, buz, enow, net).run()
    finally:
        leds.off()
        if net.is_host:
            for i in range(net.splat_count):
                net.splat(i).off()
        print("\n  === LEAVING HOST RELAY COLOR ===\n")
