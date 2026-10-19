"""
Party Test -- every wand's button lights the next pool Splat
============================================================
Tag / start_game name: partytest. Party game, pooled model (SPEC sections
6-7): SPLATS_MIN 1 across all joined wands.

Each wand-button press lights the next pool Splat (round robin) in the
presser's identity color and beeps on the leader. A press on a pool Splat
counts as a press by the wand that holds it. Followers send {"b": 1} to the
leader; the leader drives every Splat. Each wand's matrix shows its own
identity color.

Followers return on ("end",) or ("leader_lost",). The leader keeps going
when a follower drops (its Splats' commands fail and are logged by
party.py). Every wand exits on a stop / other game tag or ESP-NOW "stop" /
"start_game".

Entry point:
    play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None)
"""

import time
from machine import Pin

from nfc_reader import read_tag_command
from game_tags import exit_tags_excluding
from pairing import IDENTITY

SPLATS_MIN = 1

_EXIT_TAGS = exit_tags_excluding("partytest")
BUTTON_PIN = 0
NFC_POLL_INTERVAL = 10
LOOP_DELAY_MS = 20


def _rgb(name):
    for n, rgb in IDENTITY:
        if n == name:
            return rgb
    return (60, 60, 60)


class Game:
    """One wand's game state. step(pressed) -> False when the game ends."""

    def __init__(self, net, leds, buz):
        self.net = net
        self.leds = leds
        self.buz = buz
        self.k = -1                  # last lit pool index (leader)
        leds.fill(_rgb(net.wands[net.me][1]))

    def _light(self, w):
        net = self.net
        if net.splat_count == 0:
            return
        self.k = (self.k + 1) % net.splat_count
        net.splat(self.k).color(net.wands[w][1])
        self.buz.beep(660 + 60 * w, 50)

    def step(self, pressed):
        net = self.net
        if pressed:
            if net.is_leader:
                self._light(net.me)
            else:
                net.send(0, {"b": 1})
        while True:
            ev = net.poll()
            if ev is None:
                return True
            kind = ev[0]
            if kind in ("end", "leader_lost"):
                print(f"  partytest: {kind}")
                return False
            if not net.is_leader:
                continue
            if kind == "msg" and isinstance(ev[2], dict) and ev[2].get("b"):
                self._light(ev[1])
            elif kind == "press":
                self._light(net.owner(ev[1]))
            elif kind in ("wand_lost", "wand_back"):
                print(f"  partytest: {kind} {ev[1]}")


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
