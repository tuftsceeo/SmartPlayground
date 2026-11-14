"""
Red Glow — every wand glows red; press the button for a happy sound.
"""
import time
from machine import Pin

from nfc_reader import NfcReader
from game_tags import exit_tags_excluding
from leds import RED

_EXIT_TAGS = exit_tags_excluding("red_glow")
COMMANDS = _EXIT_TAGS
NFC_EVERY = 10
LOOP_MS = 50


def play(nfc, leds, buz, accel, i2c, enow, batt=None):
    reader = NfcReader(nfc, COMMANDS)
    btn = Pin(0, Pin.IN, Pin.PULL_UP)
    btn_was_down = (btn.value() == 0)
    frame = 0
    buz.beep(523, 80)
    buz.beep(784, 120)
    try:
        while True:
            msg_type, data, _mac = enow.poll()
            if msg_type in ("stop", "start_game"):
                return
            if frame % NFC_EVERY == 0:
                cmd, uid = reader.read_command(timeout=100)
                if cmd in _EXIT_TAGS:
                    return
            down = (btn.value() == 0)
            if down and not btn_was_down:
                buz.confirm()
            btn_was_down = down
            leds.breathe(130, 0, 0, frame)
            time.sleep_ms(LOOP_MS)
            frame += 1
    finally:
        leds.off()
