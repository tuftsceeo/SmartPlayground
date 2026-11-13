"""
Color Pads -- press the Splat that glows the same color as the wand
"""
import time
import random

from nfc_reader import NfcReader
from game_tags import exit_tags_excluding
from leds import RED, BLUE, SHAPE_STAR, MINT

GAME_ICON = (SHAPE_STAR, MINT)
SPLATS_LOCAL = 2
_EXIT_TAGS = exit_tags_excluding("color_pads")
COMMANDS = _EXIT_TAGS
NFC_EVERY = 10
LOOP_MS = 20
CHOICES = (("turnred", RED), ("turnblue", BLUE))


def play(nfc, leds, buz, accel, i2c, enow, batt=None, splats=None):
    reader = NfcReader(nfc, COMMANDS)
    n = SPLATS_LOCAL
    frame = 0
    score = 0
    try:
        for i in range(n):
            splats.unit(i).color(CHOICES[i][0])
        want = random.randrange(n)
        leds.fill(CHOICES[want][1])
        while True:
            msg_type, data, _mac = enow.poll()
            if msg_type in ("stop", "start_game"):
                return
            if frame % NFC_EVERY == 0:
                cmd, _uid = reader.read_command(timeout=100)
                if cmd in _EXIT_TAGS:
                    return
            ev = splats.poll()
            if ev and ev[0] == "press":
                if ev[1] == want:
                    score += 1
                    splats.unit(ev[1]).play(["turnwhite", "note_c"])
                    time.sleep_ms(200)
                    splats.unit(ev[1]).color(CHOICES[ev[1]][0])
                    want = random.randrange(n)
                    leds.fill(CHOICES[want][1])
                else:
                    buz.beep(200, 150)
            time.sleep_ms(LOOP_MS)
            frame += 1
    finally:
        leds.off()
