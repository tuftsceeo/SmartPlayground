"""
Simon Stomp -- stomp your two Splats in the order the wand shows; the pattern grows by one
"""
import random
import time

from nfc_reader import NfcReader
from game_tags import exit_tags_excluding
from leds import BLUE, YELLOW, SHAPE_CIRCLE, SHAPE_TRIANGLE
import signals

GAME_ICON = (SHAPE_TRIANGLE, YELLOW)
SPLATS_LOCAL = 2
_EXIT_TAGS = exit_tags_excluding("simonstomp")
COMMANDS = _EXIT_TAGS
NFC_EVERY = 10
LOOP_MS = 20

# Shared color table: Splat i -> (Splat color, wand color, wand shape, Splat
# note, wand buzzer Hz). Every step shows a shape and plays a note as well
# as lighting a color.
TABLE = (
    ("turnblue", BLUE, SHAPE_CIRCLE, "note_c", 523),
    ("turnyellow", YELLOW, SHAPE_TRIANGLE, "note_e", 659),
)
START_LEN = 2
MAX_LEN = 8
STEP_MS = 600
STEP_GAP_MS = 250
ANSWER_MS = 8000          # per press; then the pattern is shown again


def _show_step(leds, buz, splats, i):
    color, rgb, shape, note, hz = TABLE[i]
    leds.show_shape(shape, rgb)
    splats.unit(i).play([color, note])
    buz.beep(hz, 200)
    time.sleep_ms(STEP_MS - 200)
    leds.off()


def _idle_colors(splats):
    for i in range(SPLATS_LOCAL):
        splats.unit(i).color(TABLE[i][0])


def _show_pattern(leds, buz, splats, pattern):
    for i in range(SPLATS_LOCAL):
        splats.unit(i).off()
    time.sleep_ms(300)
    for i in pattern:
        _show_step(leds, buz, splats, i)
        splats.unit(i).off()
        time.sleep_ms(STEP_GAP_MS)
    _idle_colors(splats)
    signals.turn(leds, buz)


def play(nfc, leds, buz, accel, i2c, enow, batt=None, splats=None):
    reader = NfcReader(nfc, COMMANDS)
    pattern = [random.randrange(SPLATS_LOCAL) for _ in range(START_LEN)]
    pos = 0
    frame = 0
    try:
        _show_pattern(leds, buz, splats, pattern)
        at = time.ticks_ms()
        while True:
            msg_type, _data, _mac = enow.poll()
            if msg_type in ("stop", "start_game"):
                return
            if frame % NFC_EVERY == 0:
                cmd, _uid = reader.read_command(timeout=100)
                if cmd in _EXIT_TAGS:
                    return
            frame += 1
            ev = splats.poll()
            if ev and ev[0] == "press":
                i = ev[1]
                _show_step(leds, buz, splats, i)
                splats.unit(i).color(TABLE[i][0])
                if i == pattern[pos]:
                    pos += 1
                    if pos == len(pattern):
                        signals.right(leds, buz)
                        if len(pattern) == MAX_LEN:
                            signals.win(leds, buz)
                            pattern = [random.randrange(SPLATS_LOCAL) for _ in range(START_LEN)]
                        else:
                            pattern.append(random.randrange(SPLATS_LOCAL))
                        pos = 0
                        time.sleep_ms(400)
                        _show_pattern(leds, buz, splats, pattern)
                else:
                    signals.wrong(leds, buz)
                    pos = 0
                    _show_pattern(leds, buz, splats, pattern)
                at = time.ticks_ms()
            elif time.ticks_diff(time.ticks_ms(), at) > ANSWER_MS:
                pos = 0
                _show_pattern(leds, buz, splats, pattern)
                at = time.ticks_ms()
            time.sleep_ms(LOOP_MS)
    finally:
        leds.off()
