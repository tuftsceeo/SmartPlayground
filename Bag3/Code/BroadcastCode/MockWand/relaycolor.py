"""
Relay Color -- a color baton passed wand to wand
================================================
Tag / start_game name: relaycolor. Party game, messages model (SPEC
sections 6-7): SPLATS_MIN 1 across all joined wands; each wand drives only
its own net.local Splats.

One wand holds the baton: its matrix and its own Splats show the current
color (pairing.IDENTITY, in order). The holder's button, or a press on one
of its Splats, passes the baton to the next wand with the next color, sent
as {"h": holder, "k": color index}; a follower sends it to the leader,
which forwards it to every wand. Wands without Splats show
the color on the matrix only. The leader starts holding color 0.

Dropouts: the leader keeps the lost-wand list and sends it as {"x": [...]};
a pass skips those wands. When the holder is lost, the leader takes the
baton. Followers return on ("end",) or ("leader_lost",). Every wand exits on
a stop / other game tag or ESP-NOW "stop" / "start_game".

Entry point:
    play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None)
"""

import time
from machine import Pin

from nfc_reader import read_tag_command
from game_tags import exit_tags_excluding
from pairing import IDENTITY

SPLATS_MIN = 1

_EXIT_TAGS = exit_tags_excluding("relaycolor")
BUTTON_PIN = 0
NFC_POLL_INTERVAL = 10
LOOP_DELAY_MS = 20


class Game:
    """One wand's game state. step(pressed) -> False when the game ends."""

    def __init__(self, net, leds, buz):
        self.net = net
        self.leds = leds
        self.buz = buz
        self.holder = 0
        self.k = 0
        self.lost = []
        self.shown = None
        if net.is_leader:
            net.send(None, {"h": 0, "k": 0})
        self._show()

    def _show(self):
        net = self.net
        state = (self.holder == net.me, self.k)
        if state == self.shown:
            return
        self.shown = state
        name, rgb = IDENTITY[self.k]
        local = net.local
        if state[0]:
            self.leds.fill(rgb)
            if local is not None:
                for s in local.ready():
                    local.splat(s).color(name)
            self.buz.beep(660 + 40 * self.k, 60)
        else:
            self.leds.off()
            if local is not None:
                local.off()

    def _set(self, h, k):
        self.holder = h
        self.k = k % len(IDENTITY)
        self._show()

    def _pass(self):
        net = self.net
        n = len(net.wands)
        nxt = net.me
        for j in range(1, n + 1):
            w = (net.me + j) % n
            if w not in self.lost:
                nxt = w
                break
        self._set(nxt, self.k + 1)
        self._announce()

    def _announce(self):
        # Followers hold only the leader as a peer (party.py), so they send
        # to wand 0 and the leader forwards to every wand.
        net = self.net
        net.send(None if net.is_leader else 0, {"h": self.holder, "k": self.k})

    def _local_press(self, ev):
        """True if a press event is on one of this wand's own Splats."""
        if ev[0] != "press":
            return False
        if self.net.is_leader:
            return self.net.owner(ev[1]) == self.net.me
        return True

    def step(self, pressed):
        net = self.net
        while True:
            ev = net.poll()
            if ev is None:
                break
            kind = ev[0]
            if kind in ("end", "leader_lost"):
                print(f"  relaycolor: {kind}")
                return False
            if self._local_press(ev):
                pressed = True
            elif kind == "msg" and isinstance(ev[2], dict):
                d = ev[2]
                if "x" in d:
                    self.lost = list(d["x"])
                if "h" in d:
                    self._set(int(d["h"]), int(d.get("k", 0)))
                    if net.is_leader:
                        self._announce()
            elif kind == "wand_lost":
                print(f"  relaycolor: wand {ev[1]} lost")
                if ev[1] not in self.lost:
                    self.lost.append(ev[1])
                net.send(None, {"x": self.lost})
                if self.holder == ev[1]:
                    self._set(net.me, self.k + 1)
                    self._announce()
            elif kind == "wand_back":
                if ev[1] in self.lost:
                    self.lost.remove(ev[1])
                net.send(None, {"x": self.lost, "h": self.holder, "k": self.k})
        if pressed and self.holder == net.me:
            self._pass()
        return True


def _loop(nfc, leds, buz, enow, net):
    btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
    was = btn.value() == 0
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
        down = btn.value() == 0
        pressed = down and not was
        was = down
        if not g.step(pressed):
            return
        time.sleep_ms(LOOP_DELAY_MS)


def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
    buz.beep(523, 100)
    try:
        _loop(nfc, leds, buz, enow, net)
    finally:
        leds.off()
