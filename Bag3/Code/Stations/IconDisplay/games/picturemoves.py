"""
Picture Moves -- the display shows an animal; everyone moves like it until the next one
=====================================================================================
Display half of a two-device game; the wand half is Wand Module/games/picturemoves.py.
Each device starts from its own `picturemoves` card (the display never broadcasts
start_game, so two displays cannot restart each other).

Messages it broadcasts (each sent 3 times; `i` lets a wand drop repeats):
    {"type": "picture", "icon": "<animal>", "i": <0..7>}   a new animal
    {"type": "picture", "end": 1, "i": 8}                   the round is over
Messages it listens for: none.

No buzzer here: the change is shown by the new icon and heard on the wands.
"""
import random
import time

from nfc_reader import NfcReader
from display_tags import exit_tags_excluding
import icon_store
import draw16

_EXIT_TAGS = exit_tags_excluding("picturemoves")
COMMANDS = _EXIT_TAGS
# Animals from several regions; torogoz is El Salvador's national bird.
ANIMALS = ("frog", "bird", "fish", "bunny", "snake", "elephant", "butterfly",
           "penguin", "turtle", "monkey", "dog", "cat", "duck", "torogoz")
ROUNDS = 8
SHOW_MS = 15000
END_ICON = "sleepy"
END_MS = 6000
SEND_REPEATS = 3
INTENSITY = 0.15
LOOP_MS = 40
NFC_EVERY = 12
DOT_ON = (185, 200, 200)
DOT_OFF = (20, 22, 22)


def _send(enow, msg):
    for _ in range(SEND_REPEATS):
        enow.broadcast(msg)
        time.sleep_ms(5)


def _draw(leds, name, done):
    # The animal, plus a progress row along the bottom: one dot per animal,
    # lit for those already shown.
    icon_store.read_icon(name, into=leds.src)
    col = (draw16.W - ROUNDS) // 2
    for k in range(ROUNDS):
        draw16.px(leds.src, draw16.H - 1, col + k, DOT_ON if k <= done else DOT_OFF)
    leds.draw_bytes(leds.src)


def play(nfc, leds, buz, accel, i2c, enow, batt=None):
    reader = NfcReader(nfc, COMMANDS) if nfc is not None else None
    order = list(ANIMALS)
    for i in range(len(order) - 1, 0, -1):   # MicroPython has no random.shuffle
        j = random.randrange(i + 1)
        order[i], order[j] = order[j], order[i]
    order = order[:ROUNDS]
    frame = 0
    try:
        leds.set_intensity(INTENSITY)
        for k, name in enumerate(order):
            _draw(leds, name, k)
            _send(enow, {"type": "picture", "icon": name, "i": k})
            at = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), at) < SHOW_MS:
                msg_type, _data, _mac = enow.poll()
                if msg_type in ("stop", "start_game"):
                    return
                if reader is not None and frame % NFC_EVERY == 0:
                    cmd, _uid = reader.read_command(timeout=100)
                    if cmd in _EXIT_TAGS:
                        return
                frame += 1
                time.sleep_ms(LOOP_MS)
        icon_store.read_icon(END_ICON, into=leds.src)
        leds.draw_bytes(leds.src)
        _send(enow, {"type": "picture", "end": 1, "i": ROUNDS})
        time.sleep_ms(END_MS)
    finally:
        leds.clear()
