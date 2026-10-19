"""
Solo Test -- one local Splat, cycled through the identity palette
=================================================================
Tag / start_game name: solotest. Solo Splat game (SPEC section 6, "Solo
Splat games"): needs 1 paired, READY Splat on this wand.

Each wand-button press, or a press on Splat 0, moves Splat 0 and the wand
matrix to the next pairing.IDENTITY color and beeps. A dropped Splat shows
dim red on the wand until it is back. Exits on a stop / other game tag or
ESP-NOW "stop" / "start_game".

Entry point:
    play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None)
"""

import time
from machine import Pin

from nfc_reader import read_tag_command
from game_tags import exit_tags_excluding
from pairing import IDENTITY

SPLATS_LOCAL = 1

_EXIT_TAGS = exit_tags_excluding("solotest")
BUTTON_PIN = 0
NFC_POLL_INTERVAL = 10
LOOP_DELAY_MS = 20
LOST_RGB = (20, 0, 0)


def _show(net, leds, k):
    name, rgb = IDENTITY[k]
    net.splat(0).color(name)
    leds.fill(rgb)


def _loop(nfc, leds, buz, enow, net):
    btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
    was = btn.value() == 0
    k = 0
    frame = 0
    _show(net, leds, k)
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
        step = down and not was
        was = down
        ev = net.poll()
        if ev == ("press", 0):
            step = True
        elif ev == ("splat_lost", 0):
            leds.fill(LOST_RGB)
        elif ev == ("splat_back", 0):
            _show(net, leds, k)
        if step:
            k = (k + 1) % len(IDENTITY)
            _show(net, leds, k)
            buz.beep(660 + 40 * k, 60)
        time.sleep_ms(LOOP_DELAY_MS)


def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
    buz.beep(523, 100)
    try:
        _loop(nfc, leds, buz, enow, net)
    finally:
        leds.off()
