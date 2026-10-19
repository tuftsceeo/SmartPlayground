"""
Splat Tag -- first press on the lit Splat scores
================================================
Tag / start_game name: splattag. Party game, pooled model (SPEC sections
6-7): SPLATS_MIN 2 across all joined wands.

The leader lights one random pool Splat green. The first press on it scores
a point for the wand holding that Splat; the Splat goes off and another is
lit after GAP_MS. An unpressed Splat moves after ROUND_MS. The leader sends
the scores to every wand as {"s": [score per wand]}; each matrix shows its
own score as lit pixels in its identity color. At WIN_SCORE the leader sends
{"s": ..., "w": winner} and returns, which ends the game for everyone.

Dropouts: a lost Splat (splat_lost, or every Splat of a wand_lost wand) is
not chosen until it is back. Followers return on ("end",) or
("leader_lost",). Every wand exits on a stop / other game tag or ESP-NOW
"stop" / "start_game".

Entry point:
    play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None)
"""

import time
import random

from nfc_reader import read_tag_command
from game_tags import exit_tags_excluding
from pairing import IDENTITY

SPLATS_MIN = 2

_EXIT_TAGS = exit_tags_excluding("splattag")
NFC_POLL_INTERVAL = 10
LOOP_DELAY_MS = 20
TARGET = "turngreen"
GAP_MS = 800
ROUND_MS = 5000
WIN_SCORE = 5


def _rgb(name):
    for n, rgb in IDENTITY:
        if n == name:
            return rgb
    return (60, 60, 60)


class Game:
    """One wand's game state. step() -> False when the game ends."""

    def __init__(self, net, leds, buz):
        self.net = net
        self.leds = leds
        self.buz = buz
        self.rgb = _rgb(net.wands[net.me][1])
        self.scores = [0] * len(net.wands)
        self.lost = set()            # pool indexes not to light (leader)
        self.lit = None
        self.lit_t = 0
        self.next_t = time.ticks_ms()
        self.winner = None
        self._show()

    def _show(self):
        n = min(self.scores[self.net.me], 25)
        self.leds.show_shape(tuple(range(n)), self.rgb)

    def _pick(self):
        net = self.net
        free = [i for i in range(net.splat_count) if i not in self.lost]
        if not free:
            return
        self.lit = free[random.getrandbits(8) % len(free)]
        self.lit_t = time.ticks_ms()
        net.splat(self.lit).color(TARGET)

    def _clear(self):
        if self.lit is not None:
            self.net.splat(self.lit).off()
            self.lit = None
        self.next_t = time.ticks_add(time.ticks_ms(), GAP_MS)

    def _score(self, i):
        net = self.net
        w = net.owner(i)
        self.scores[w] += 1
        self._clear()
        self.buz.beep(880, 80)
        msg = {"s": self.scores}
        if self.scores[w] >= WIN_SCORE:
            self.winner = w
            msg["w"] = w
        net.send(None, msg)
        self._show()

    def _wand_splats(self, w):
        net = self.net
        return [i for i in range(net.splat_count) if net.owner(i) == w]

    def _lead(self, ev):
        kind = ev[0]
        if kind == "press" and ev[1] == self.lit:
            self._score(ev[1])
        elif kind == "splat_lost":
            self.lost.add(ev[1])
            if ev[1] == self.lit:
                self.lit = None
        elif kind == "splat_back":
            self.lost.discard(ev[1])
        elif kind == "wand_lost":
            print(f"  splattag: wand {ev[1]} lost")
            for i in self._wand_splats(ev[1]):
                self.lost.add(i)
                if i == self.lit:
                    self.lit = None
        elif kind == "wand_back":
            for i in self._wand_splats(ev[1]):
                self.lost.discard(i)

    def _follow(self, ev):
        d = ev[2] if ev[0] == "msg" else None
        if isinstance(d, dict) and "s" in d:
            self.scores = list(d["s"])
            self._show()
            if "w" in d:
                self.winner = d["w"]

    def step(self):
        net = self.net
        while True:
            ev = net.poll()
            if ev is None:
                break
            if ev[0] in ("end", "leader_lost"):
                print(f"  splattag: {ev[0]}")
                if self.winner == net.me:
                    self.buz.celebrate()
                return False
            if net.is_leader:
                self._lead(ev)
            else:
                self._follow(ev)
        if not net.is_leader:
            return True
        if self.winner is not None:
            print(f"  splattag: wand {self.winner} wins {self.scores}")
            if self.winner == net.me:
                self.buz.celebrate()
            return False
        now = time.ticks_ms()
        if self.lit is None:
            if time.ticks_diff(now, self.next_t) >= 0:
                self._pick()
        elif time.ticks_diff(now, self.lit_t) >= ROUND_MS:
            self._clear()
        return True


def _loop(nfc, leds, buz, enow, net):
    g = Game(net, leds, buz)
    frame = 0
    while True:
        mt, _, _ = enow.poll()
        if mt in ("stop", "start_game"):
            return
        frame += 1
        if frame % NFC_POLL_INTERVAL == 0:
            text, _ = read_tag_command(nfc, timeout=100)
            if text in _EXIT_TAGS:
                return
        if not g.step():
            return
        time.sleep_ms(LOOP_DELAY_MS)


def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
    buz.beep(523, 100)
    try:
        _loop(nfc, leds, buz, enow, net)
    finally:
        leds.off()
