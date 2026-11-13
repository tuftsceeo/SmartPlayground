"""
Color Says -- the teacher's wand taps a color card; every wand shows that color, its shape and its note
"""
import random
import time

from nfc_reader import NfcReader
from game_tags import exit_tags_excluding
from leds import (BLUE, YELLOW, PURPLE, WHITE, AMBER, AMBER_DIM,
                  SHAPE_CIRCLE, SHAPE_TRIANGLE, SHAPE_BORDER, SHAPE_STAR, SHAPE_ARROW_DN)

GAME_ICON = (SHAPE_STAR, BLUE)
_EXIT_TAGS = exit_tags_excluding("colorsays")
# The leader is chosen as in Freeze Dance: the teacher taps the `caller` card.
COLOR_CARDS = ("turnblue", "turnyellow", "turnpurple", "turnwhite")
COMMANDS = {"caller", "turnblue", "turnyellow", "turnpurple", "turnwhite"} | _EXIT_TAGS
NFC_EVERY = 5
LOOP_MS = 40
SEND_REPEATS = 3

# Shared color table: card -> (wand color, shape, buzzer Hz). The move each
# color means is on the teacher's printed card, not in the code.
TABLE = {
    "turnblue": (BLUE, SHAPE_CIRCLE, 523),        # note_c
    "turnyellow": (YELLOW, SHAPE_TRIANGLE, 659),  # note_e
    "turnpurple": (PURPLE, SHAPE_BORDER, 784),    # note_g (square): freeze
    "turnwhite": (WHITE, SHAPE_STAR, 1047),       # note_c_high
}
FREEZE_CARD = "turnpurple"
FREEZE_MS = 3000
FREEZE_GRACE_MS = 1000
# Freeze Dance's motion check (freeze_dance.py MotionChecker.triggered),
# copied rather than imported: importing freeze_dance compiles all of it.
MOVE_THRESHOLD = 0.70
MOVE_HITS_NEEDED = 2


class _Motion:
    def __init__(self, accel):
        self.accel = accel
        self.last = None
        self.hits = 0

    def reset(self):
        self.hits = 0
        try:
            self.last = self.accel.read()
        except Exception:
            self.last = None

    def moved(self):
        try:
            xyz = self.accel.read()
        except Exception:
            return False
        if self.last is None:
            self.last = xyz
            return False
        m = abs(xyz[0] - self.last[0]) + abs(xyz[1] - self.last[1]) + abs(xyz[2] - self.last[2])
        self.last = xyz
        if m >= MOVE_THRESHOLD:
            self.hits += 1
        elif self.hits > 0:
            self.hits -= 1
        return self.hits >= MOVE_HITS_NEEDED


def _show(leds, buz, card):
    rgb, shape, hz = TABLE[card]
    leds.show_shape(shape, rgb)
    buz.beep(hz, 300)


def play(nfc, leds, buz, accel, i2c, enow, batt=None):
    reader = NfcReader(nfc, COMMANDS)
    motion = _Motion(accel)
    is_caller = False
    seq = random.randrange(1 << 20)
    last_seq = None
    freeze_at = None
    moved = False
    frame = 0
    try:
        leds.show_shape(SHAPE_ARROW_DN, WHITE)     # waiting for the first color
        while True:
            msg_type, data, _mac = enow.poll()
            if msg_type in ("stop", "start_game"):
                return
            card = None
            if (msg_type == "raw" and isinstance(data, dict) and data.get("type") == "colorsays"
                    and data.get("n") != last_seq and data.get("c") in TABLE):
                last_seq = data["n"]
                card = data["c"]

            if frame % NFC_EVERY == 0:
                cmd, _uid = reader.read_command(timeout=60)
                if cmd in _EXIT_TAGS:
                    return
                if cmd == "caller" and not is_caller:
                    is_caller = True
                    leds.flash_color(AMBER, times=3, on_ms=80, off_ms=60)
                    buz.confirm()
                    leds.show_shape(SHAPE_ARROW_DN, WHITE)
                elif is_caller and cmd in TABLE:
                    seq += 1
                    for _ in range(SEND_REPEATS):
                        enow.broadcast({"type": "colorsays", "c": cmd, "n": seq})
                        time.sleep_ms(5)
                    card = cmd
            frame += 1

            if card is not None:
                _show(leds, buz, card)
                freeze_at = None
                if card == FREEZE_CARD and not is_caller and accel is not None:
                    freeze_at = time.ticks_ms()
                    moved = False
                    motion.reset()

            # Freeze: a reminder, not a score. Soft amber if the wand moved.
            if freeze_at is not None:
                held = time.ticks_diff(time.ticks_ms(), freeze_at)
                if held >= FREEZE_MS:
                    freeze_at = None
                    rgb, shape, _hz = TABLE[FREEZE_CARD]
                    leds.show_shape(shape, rgb)
                elif held >= FREEZE_GRACE_MS and not moved and motion.moved():
                    moved = True
                    leds.fill(AMBER_DIM)
                    buz.beep(220, 150)
            time.sleep_ms(LOOP_MS)
    finally:
        leds.off()
