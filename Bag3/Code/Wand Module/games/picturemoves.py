"""
Picture Moves -- the icon display shows an animal; the wand chimes when it changes
"""
import time

from nfc_reader import NfcReader
from game_tags import exit_tags_excluding
from leds import WHITE, TEAL, SHAPE_FISH, SHAPE_BIRD, SHAPE_DANCER1, SHAPE_DANCER2, SHAPE_DANCER3
import signals

GAME_ICON = (SHAPE_DANCER1, TEAL)
_EXIT_TAGS = exit_tags_excluding("picturemoves")
COMMANDS = _EXIT_TAGS
NFC_EVERY = 10
LOOP_MS = 40
# Animals with a 5x5 shape; the rest show a dancer. Moves are the children's
# choice: there is no wrong move and nothing to check.
SHAPES = {"fish": SHAPE_FISH, "bird": SHAPE_BIRD, "torogoz": SHAPE_BIRD,
          "duck": SHAPE_BIRD, "penguin": SHAPE_BIRD}
DANCERS = (SHAPE_DANCER1, SHAPE_DANCER2, SHAPE_DANCER3)


def play(nfc, leds, buz, accel, i2c, enow, batt=None):
    reader = NfcReader(nfc, COMMANDS)
    last_i = None
    shape = None
    frame = 0
    try:
        while True:
            msg_type, data, _mac = enow.poll()
            if msg_type in ("stop", "start_game"):
                return
            if (msg_type == "raw" and isinstance(data, dict) and data.get("type") == "picture"
                    and data.get("i") != last_i):
                last_i = data.get("i")
                if data.get("end"):
                    signals.win(leds, buz)
                    return
                signals.turn(leds, buz)              # the change chime
                shape = SHAPES.get(data.get("icon"))
            if frame % NFC_EVERY == 0:
                cmd, _uid = reader.read_command(timeout=60)
                if cmd in _EXIT_TAGS:
                    return
            if last_i is None:
                leds.breathe_shape(DANCERS[0], WHITE, frame)   # waiting for the display
            elif shape is not None:
                leds.show_shape(shape, TEAL)
            else:
                leds.show_shape(DANCERS[(frame // 8) % 3], TEAL)
            frame += 1
            time.sleep_ms(LOOP_MS)
    finally:
        leds.off()
