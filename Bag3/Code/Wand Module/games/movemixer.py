"""
Move Mixer -- collect move cards into a dance, preview it, and share it to the icon display
"""
import time
from machine import Pin

from hubtype import HUB_CONFIG
from nfc_reader import NfcReader
from game_tags import exit_tags_excluding
from leds import (WHITE, CYAN, PINK, SHAPE_ARROW_UP, SHAPE_SPIRAL, SHAPE_HAND,
                  SHAPE_SNOWFLAKE, SHAPE_DOUBLE, SHAPE_DANCER2,
                  SHAPE_0, SHAPE_1, SHAPE_2, SHAPE_3, SHAPE_4, SHAPE_5, SHAPE_6)
import signals

GAME_ICON = (SHAPE_DANCER2, PINK)
_EXIT_TAGS = exit_tags_excluding("movemixer")
# Move cards (prefixed to stay clear of the `jump` game tag) and the share card.
MOVE_CARDS = {
    "move_jump": "jump",
    "move_spin": "spin",
    "move_wave": "wave",
    "move_freeze": "freeze",
    "move_twice": "twice",
}
COMMANDS = {"move_jump", "move_spin", "move_wave", "move_freeze", "move_twice",
            "share"} | _EXIT_TAGS
NFC_EVERY = 5
LOOP_MS = 20
MAX_STEPS = 6
BEAT_MS = 2000            # one step every 2 s, the display's pace
LONG_PRESS_MS = 1500      # clears the dance
SHARE_REPEATS = 3

# move -> (wand shape, tone as (Hz, ms) steps)
MOVES = {
    "jump": (SHAPE_ARROW_UP, ((600, 60), (900, 90))),        # rising chirp
    "spin": (SHAPE_SPIRAL, ((700, 50), (900, 50), (700, 50))),  # swirl
    "wave": (SHAPE_HAND, ((800, 70), (0, 60), (800, 70))),    # two beeps
    "freeze": (SHAPE_SNOWFLAKE, ((300, 400),)),               # low hold
    "twice": (SHAPE_DOUBLE, ((1200, 30), (0, 40), (1200, 30))),  # double click
}
DIGITS = (SHAPE_0, SHAPE_1, SHAPE_2, SHAPE_3, SHAPE_4, SHAPE_5, SHAPE_6)


def _show_move(leds, buz, move, color=WHITE):
    shape, tone = MOVES[move]
    leds.show_shape(shape, color)
    for hz, ms in tone:
        if hz:
            buz.beep(hz, ms)
        else:
            time.sleep_ms(ms)


def _show_count(leds, steps):
    leds.show_shape(DIGITS[len(steps)], CYAN)


def _expand(steps):
    # `twice` repeats the step before it; the display only knows real moves.
    out = []
    for m in steps:
        if m == "twice":
            if out:
                out.append(out[-1])
        else:
            out.append(m)
    return out


def play(nfc, leds, buz, accel, i2c, enow, batt=None):
    reader = NfcReader(nfc, COMMANDS)
    btn = Pin(HUB_CONFIG["button_pin"], Pin.IN, Pin.PULL_UP)
    steps = []
    preview = None            # step index while previewing, else None
    beat_at = 0
    down_at = None
    was_down = btn.value() == 0
    frame = 0
    try:
        _show_count(leds, steps)
        while True:
            msg_type, _data, _mac = enow.poll()
            if msg_type in ("stop", "start_game"):
                return
            now = time.ticks_ms()

            # ── button: short press previews (or stops a preview), long press clears ──
            down = btn.value() == 0
            if down and not was_down:
                down_at = now
            elif down and down_at is not None and time.ticks_diff(now, down_at) >= LONG_PRESS_MS:
                down_at = None
                steps = []
                preview = None
                buz.stop()
                _show_count(leds, steps)
            elif not down and was_down and down_at is not None:
                down_at = None
                if preview is None and steps:
                    preview = 0
                    beat_at = now
                    _show_move(leds, buz, steps[0])
                else:
                    preview = None
                    _show_count(leds, steps)
            was_down = down

            # ── preview: one step every BEAT_MS ──
            if preview is not None and time.ticks_diff(now, beat_at) >= BEAT_MS:
                preview += 1
                beat_at = now
                if preview >= len(steps):
                    preview = None
                    _show_count(leds, steps)
                else:
                    _show_move(leds, buz, steps[preview])

            # ── cards ──
            if frame % NFC_EVERY == 0:
                cmd, _uid = reader.read_command(timeout=60)
                if cmd in _EXIT_TAGS:
                    return
                move = MOVE_CARDS.get(cmd)
                if move is not None:
                    if preview is not None:
                        steps[preview] = move          # change this step
                        _show_move(leds, buz, move)
                    elif len(steps) < MAX_STEPS:
                        steps.append(move)
                        _show_move(leds, buz, move)
                        time.sleep_ms(500)
                        _show_count(leds, steps)
                    else:
                        signals.wrong(leds, buz)        # full: 6 steps
                        _show_count(leds, steps)
                elif cmd == "share":
                    dance = _expand(steps)
                    if dance:
                        msg = {"type": "dance", "s": dance}
                        for _ in range(SHARE_REPEATS):
                            enow.broadcast(msg)
                            time.sleep_ms(5)
                        signals.level_up(leds, buz)    # the sparkle
                    else:
                        signals.wrong(leds, buz)
                    preview = None
                    _show_count(leds, steps)
            frame += 1
            time.sleep_ms(LOOP_MS)
    finally:
        leds.off()
