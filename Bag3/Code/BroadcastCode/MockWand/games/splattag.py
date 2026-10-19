"""
Splat Tag -- pooled party game
===============================
Party game (SPLATS_MIN = 2). The leader lights one random Splat from the whole
pool (every wand's Splats); the first press on it scores a point for the wand
that owns that Splat. First to WIN_SCORE points wins.

Pooled model: only the leader's code decides anything and drives every Splat
through net.splat(i); follower wands run a bare event loop that shows their
score (lit pixels) and the result, and leave when the leader does. A Splat
that drops, or a wand that goes silent, is skipped when picking the target.

Entry point:
    play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None)
"""

import random
import time

from nfc_reader import read_tag_command
from game_tags import exit_tags_excluding
from splatpair import WAND_RGB

SPLATS_MIN = 2
SPLATS_MAX = None

_EXIT_TAGS = exit_tags_excluding("splattag")

WIN_SCORE = 5
ROUND_MS = 8000         # a target nobody presses is replaced after this
PAUSE_MS = 1200         # between a point and the next target
OVER_MS = 4000          # the result stays up this long before the leader leaves
NFC_EVERY = 25
NFC_MS = 30


def _show_score(leds, score, color):
    for i in range(leds.num):
        leds.np[i] = color if i < score else (0, 0, 0)
    leds.np.write()


class _Tag:
    def __init__(self, nfc, leds, buz, net):
        self.nfc = nfc
        self.leds = leds
        self.buz = buz
        self.net = net
        n = len(net.wands)
        self.color = WAND_RGB[net.wands[net.me][1]]
        self.scores = [0] * n
        self.alive = [True] * n
        self.lost = set()           # pool Splats currently not READY
        self.lit = None             # pool Splat currently lit
        self.target = None
        self.state = "pick"         # leader: pick, wait, pause, over
        self.at = time.ticks_ms()   # when the state was entered

    # ── leader ──

    def candidates(self):
        net = self.net
        return [i for i in range(net.splat_count)
                if self.alive[net.owner(i)] and i not in self.lost and i != self.lit]

    def go(self, state):
        self.state = state
        self.at = time.ticks_ms()

    def pick(self):
        net = self.net
        if self.lit is not None:
            net.splat(self.lit).off()
            self.lit = None
        cands = self.candidates()
        if not cands:
            self.target = None
            self.go("pick")
            return
        self.target = self.lit = cands[random.randrange(len(cands))]
        ok = net.splat(self.target).play(["turngreen"])
        print("  splattag: target pool Splat %d (wand %d) %s"
              % (self.target, net.owner(self.target), "lit" if ok else "NOT LIT"))
        self.go("wait")

    def point(self, owner):
        net = self.net
        self.scores[owner] += 1
        net.splat(self.target).play(["turnyellow", "cow"])
        print("  splattag: point for wand %d -> %s" % (owner, self.scores))
        net.send(None, {"s": self.scores})
        _show_score(self.leds, self.scores[net.me], self.color)
        self.target = None
        if self.scores[owner] >= WIN_SCORE:
            net.send(None, {"win": owner})
            self.shown_win(owner)
            self.go("over")
        else:
            self.go("pause")

    def shown_win(self, owner):
        print("  splattag: wand %d wins" % owner)
        if owner == self.net.me:
            self.buz.success()
        for i in range(self.leds.num):
            self.leds.np[i] = WAND_RGB[self.net.wands[owner][1]]
        self.leds.np.write()

    def leader_event(self, ev):
        net = self.net
        kind = ev[0]
        if kind == "press" and self.state == "wait" and ev[1] == self.target:
            self.point(net.owner(ev[1]))
        elif kind == "splat_lost":
            self.lost.add(ev[1])
            if ev[1] == self.target and self.state == "wait":
                print("  splattag: target Splat dropped; picking another")
                self.pick()
        elif kind == "splat_back":
            self.lost.discard(ev[1])
        elif kind == "wand_lost":
            self.alive[ev[1]] = False
            if self.state == "wait" and net.owner(self.target) == ev[1]:
                self.pick()
        elif kind == "wand_back":
            self.alive[ev[1]] = True

    def leader_tick(self):
        now = time.ticks_ms()
        waited = time.ticks_diff(now, self.at)
        if self.state == "pick":
            self.pick()
        elif self.state == "wait" and waited >= ROUND_MS:
            self.pick()
        elif self.state == "pause" and waited >= PAUSE_MS:
            self.pick()
        elif self.state == "over" and waited >= OVER_MS:
            return True
        return False

    # ── followers ──

    def follower_event(self, ev):
        if ev[0] == "msg" and isinstance(ev[2], dict):
            d = ev[2]
            if "s" in d:
                _show_score(self.leds, d["s"][self.net.me], self.color)
            elif "win" in d:
                self.shown_win(d["win"])

    def run(self):
        net = self.net
        _show_score(self.leds, 0, self.color)
        frame = 0
        while True:
            ev = net.poll()
            if ev is not None:
                if ev[0] in ("end", "leader_lost"):
                    return
                if net.is_leader:
                    self.leader_event(ev)
                else:
                    self.follower_event(ev)
            if net.is_leader and self.leader_tick():
                return
            frame += 1
            if frame % NFC_EVERY == 0:
                text, _ = read_tag_command(self.nfc, timeout=NFC_MS)
                if text in _EXIT_TAGS:
                    if net.is_leader:
                        for i in range(net.splat_count):
                            net.splat(i).off()
                    return
            time.sleep_ms(1)


def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
    if net is None:
        print("  splattag: needs a party (net is None)")
        return
    print("\n  === SPLAT TAG (%s, %d Splats) ===" % ("leader" if net.is_leader else "follower",
                                                  net.splat_count))
    try:
        _Tag(nfc, leds, buz, net).run()
    finally:
        leds.off()
        if net.is_leader:
            for i in range(net.splat_count):
                net.splat(i).off()
        print("\n  === LEAVING SPLAT TAG ===\n")
