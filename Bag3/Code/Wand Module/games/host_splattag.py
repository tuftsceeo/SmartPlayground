"""
Host Splat Tag -- Splat Tag on a Splat host
===========================================
Splat host game (SPLAT_HOST = True), ported from games/splattag.py. The host
holds every Splat and lights a random one in a random player's identity
color; the first press on it scores for that player. First to WIN_SCORE wins.

Only the host's code decides anything. Players show their score (lit
pixels) and the winner's color. A Splat that drops, or a player that goes
silent, is skipped when picking.

Entry point:
    play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None)
"""

import random
import time

from nfc_reader import read_tag_command
from game_tags import exit_tags_excluding
from splatpair import WAND_RGB

SPLAT_HOST = True
SPLATS_MIN = 2
SPLATS_MAX = 4
PLAYERS_MIN = 1

_EXIT_TAGS = exit_tags_excluding("host_splattag")

WIN_SCORE = 5
ROUND_MS = 8000
PAUSE_MS = 1200
OVER_MS = 4000
NFC_EVERY = 25
NFC_MS = 30


def _show_score(leds, score, color):
    for i in range(leds.num):
        leds.np[i] = color if i < score else (0, 0, 0)
    leds.np.write()


def _fill(leds, color):
    for i in range(leds.num):
        leds.np[i] = color
    leds.np.write()


class _Tag:
    def __init__(self, nfc, leds, buz, net):
        self.nfc = nfc
        self.leds = leds
        self.buz = buz
        self.net = net
        self.scores = [0] * len(net.wands)
        self.alive = [True] * len(net.wands)
        self.lost = set()
        self.target = None          # (Splat, player)
        self.state = "pick"         # host: pick, wait, pause, over
        self.at = time.ticks_ms()

    def go(self, state):
        self.state = state
        self.at = time.ticks_ms()

    # ── host ──

    def pick(self):
        net = self.net
        if self.target is not None:
            net.splat(self.target[0]).off()
            self.target = None
        splats = [i for i in range(net.splat_count) if i not in self.lost]
        players = [p for p in net.players if self.alive[p]]
        if not splats or not players:
            self.go("pick")
            return
        s = splats[random.randrange(len(splats))]
        p = players[random.randrange(len(players))]
        self.target = (s, p)
        ok = net.splat(s).color(net.wands[p][1])
        print("  host_splattag: Splat %d for player %d %s" % (s, p, "lit" if ok else "NOT LIT"))
        self.go("wait")

    def point(self):
        net = self.net
        s, p = self.target
        self.scores[p] += 1
        net.splat(s).play(["turnyellow", "cow"])
        net.send(None, {"s": self.scores})
        self.target = None
        if self.scores[p] >= WIN_SCORE:
            net.send(None, {"win": p})
            _fill(self.leds, WAND_RGB[net.wands[p][1]])
            self.go("over")
        else:
            self.go("pause")

    def host_event(self, ev):
        kind = ev[0]
        if kind == "press" and self.state == "wait" and self.target and ev[1] == self.target[0]:
            self.point()
        elif kind == "splat_lost":
            self.lost.add(ev[1])
            if self.state == "wait" and self.target and ev[1] == self.target[0]:
                self.pick()
        elif kind == "splat_back":
            self.lost.discard(ev[1])
        elif kind == "wand_lost":
            self.alive[ev[1]] = False
            if self.state == "wait" and self.target and self.target[1] == ev[1]:
                self.pick()
        elif kind == "wand_back":
            self.alive[ev[1]] = True

    def host_tick(self):
        waited = time.ticks_diff(time.ticks_ms(), self.at)
        if self.state == "pick":
            self.pick()
        elif self.state == "wait" and waited >= ROUND_MS:
            self.pick()
        elif self.state == "pause" and waited >= PAUSE_MS:
            self.pick()
        elif self.state == "over" and waited >= OVER_MS:
            return True
        return False

    # ── players ──

    def player_event(self, ev):
        net = self.net
        if ev[0] == "msg" and isinstance(ev[2], dict):
            d = ev[2]
            if "s" in d:
                _show_score(self.leds, d["s"][net.me], WAND_RGB[net.ident])
            elif "win" in d:
                if d["win"] == net.me:
                    self.buz.success()
                _fill(self.leds, WAND_RGB[net.wands[d["win"]][1]])

    def run(self):
        net = self.net
        if not net.is_host:
            _show_score(self.leds, 0, WAND_RGB[net.ident])
        frame = 0
        while True:
            ev = net.poll()
            if ev is not None:
                if ev[0] in ("end", "leader_lost"):
                    return
                if net.is_host:
                    self.host_event(ev)
                else:
                    self.player_event(ev)
            if net.is_host and self.host_tick():
                return
            frame += 1
            if frame % NFC_EVERY == 0:
                text, _ = read_tag_command(self.nfc, timeout=NFC_MS)
                if text in _EXIT_TAGS:
                    return
            time.sleep_ms(1)


def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
    if net is None:
        print("  host_splattag: needs a Splat host lobby (net is None)")
        return
    print("\n  === HOST SPLAT TAG (%s, %d players, %d Splats) ==="
          % ("host" if net.is_host else "player", len(net.players), net.splat_count))
    try:
        _Tag(nfc, leds, buz, net).run()
    finally:
        leds.off()
        if net.is_host:
            for i in range(net.splat_count):
                net.splat(i).off()
        print("\n  === LEAVING HOST SPLAT TAG ===\n")
