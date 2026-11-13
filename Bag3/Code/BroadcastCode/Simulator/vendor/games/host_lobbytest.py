"""
Host Lobby Test -- hardware check of the Splat host mechanics
=============================================================
Splat host game (SPLAT_HOST = True), ported from games/lobbytest.py. A wand in
the Splat host role holds every Splat and leads; game wands join its lobby
(no first-to-tap leader). The host shows the player count; its button, or the
teacher's start_game for this slug, starts the game.

  player button   lights the next Splat in the presser's identity color
  Splat press     lights that Splat white
  host log        each command's send time, for latency checks

Stop card on a player leaves; on the host it ends the game for everyone.

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
PLAYERS_MIN = 1

_EXIT_TAGS = exit_tags_excluding("host_lobbytest")

NFC_EVERY = 25
NFC_MS = 30


class _Game:
    def __init__(self, nfc, leds, buz, net):
        self.nfc = nfc
        self.leds = leds
        self.buz = buz
        self.net = net
        self.next = 0
        self.prev = None
        self.btn = Pin(HUB_CONFIG["button_pin"], Pin.IN, Pin.PULL_UP)

    def light_next(self, presser):
        net = self.net
        if net.splat_count == 0:
            return
        i = self.next % net.splat_count
        self.next += 1
        t0 = time.ticks_ms()
        ok = net.splat(i).color(net.wands[presser][1])
        print("  host_lobbytest: player %d lit Splat %d %s in %d ms"
              % (presser, i, "ok" if ok else "FAILED", time.ticks_diff(time.ticks_ms(), t0)))
        if self.prev is not None and self.prev != i:
            net.splat(self.prev).off()
        self.prev = i

    def event(self, ev):
        net = self.net
        kind = ev[0]
        if kind in ("end", "leader_lost"):
            return True
        if net.is_host:
            if kind == "msg" and isinstance(ev[2], dict) and ev[2].get("btn") == 1:
                self.light_next(ev[1])
            elif kind == "press":
                net.splat(ev[1]).color("turnwhite")
            elif kind != "release":
                print("  host_lobbytest: %s %s" % (kind, ev[1:]))
        return False

    def run(self):
        net = self.net
        color = WAND_RGB[net.wands[net.me][1]]
        for i in range(self.leds.num):
            self.leds.np[i] = color
        self.leds.np.write()
        was_down = self.btn.value() == 0
        frame = 0
        while True:
            ev = net.poll()
            if ev is not None and self.event(ev):
                return
            down = self.btn.value() == 0
            if down and not was_down and not net.is_host:
                ok = net.send(0, {"btn": 1})
                print("  host_lobbytest: button -> host %s" % ("ok" if ok else "FAILED"))
            was_down = down
            frame += 1
            if frame % NFC_EVERY == 0:
                text, _ = read_tag_command(self.nfc, timeout=NFC_MS)
                if text in _EXIT_TAGS:
                    return
            time.sleep_ms(1)


def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
    if net is None:
        print("  host_lobbytest: needs a Splat host lobby (net is None)")
        return
    print("\n  === HOST LOBBY TEST (%s, %d players, %d Splats) ==="
          % ("host" if net.is_host else "player", len(net.players), net.splat_count))
    try:
        _Game(nfc, leds, buz, net).run()
    finally:
        leds.off()
        if net.is_host:
            for i in range(net.splat_count):
                net.splat(i).off()
        print("\n  === LEAVING HOST LOBBY TEST ===\n")
