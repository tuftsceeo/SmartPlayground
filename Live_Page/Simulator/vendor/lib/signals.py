"""
signals.py -- the shared signal set for the built-in example games.

Every built-in game uses these exact cues, so children learn them once
(Experiments/SplatAuthoringRows/game_design/builtin_games_spec.md, "Shared
access rules"). Each cue is a light and a sound together: the light is set
first and stays up while the sound plays.

    turn(leds, buz)      your turn / watch: white pulse + buz.info()
    right(leds, buz)     green tick + buz.confirm()
    wrong(leds, buz)     dim amber, no flashing + one soft low beep
    level_up(leds, buz)  brief sparkle + buz.success()
    win(leds, buz)       rainbow + buz.celebrate()

Imported by games only (after the radio is up). Nothing here allocates at
import beyond these functions and a few constant tuples.
"""

import time

from leds import (WHITE, GREEN, AMBER_DIM, RED, ORANGE, YELLOW, BLUE, PURPLE,
                  SHAPE_CHECK, SHAPE_CENTER, SHAPE_STAR, SHAPE_CORNERS)

WRONG_HZ = 220
WRONG_MS = 150
_RAINBOW = (RED, ORANGE, YELLOW, GREEN, BLUE)   # one per column


def turn(leds, buz):
    leds.fill(WHITE)
    buz.info()
    leds.pulse_color(WHITE[0], WHITE[1], WHITE[2], 400)


def right(leds, buz):
    leds.show_shape(SHAPE_CHECK, GREEN)
    buz.confirm()
    time.sleep_ms(400)
    leds.off()


def wrong(leds, buz):
    leds.fill(AMBER_DIM)
    buz.beep(WRONG_HZ, WRONG_MS)
    time.sleep_ms(500)
    leds.off()


def level_up(leds, buz):
    for shape in (SHAPE_CENTER, SHAPE_STAR, SHAPE_CORNERS):
        leds.show_shape(shape, WHITE)
        time.sleep_ms(60)
    leds.show_shape(SHAPE_STAR, PURPLE)
    buz.success()
    leds.off()


def rainbow(leds):
    for i in range(leds.num):
        leds.np[i] = _RAINBOW[i % 5]
    leds.np.write()


def win(leds, buz):
    rainbow(leds)
    buz.celebrate()
    time.sleep_ms(800)
    leds.off()
