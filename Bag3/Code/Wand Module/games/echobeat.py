"""
Echo Beat -- the wand buzzes a rhythm of short and long beats; shake it back the same way
"""
import math
import time

from nfc_reader import NfcReader
from game_tags import exit_tags_excluding
from leds import WHITE, CYAN, SHAPE_INNER_3x3, SHAPE_PLAY
from leds import SHAPE_2, SHAPE_3, SHAPE_4, SHAPE_5, SHAPE_6
import signals

GAME_ICON = (SHAPE_PLAY, CYAN)
_EXIT_TAGS = exit_tags_excluding("echobeat")
COMMANDS = _EXIT_TAGS
NFC_EVERY = 25
LOOP_MS = 10

# Fixed rhythms per length (S short, L long), so a child can practice the
# same one. After a win the next round uses the next variant.
RHYTHMS = {
    2: ("SL", "LS"),
    3: ("SSL", "LSS"),
    4: ("SLSL", "LLSS"),
    5: ("SSLSL", "LSLSS"),
    6: ("SLLSSL", "LSSLLS"),
}
MIN_BEATS = 2
MAX_BEATS = 6
SHORT_MS = 150
LONG_MS = 450
GAP_MS = 250
BEAT_HZ = 880
# Time between the starts of two beats, and the echo tolerance (+-40%).
IOI = {"S": SHORT_MS + GAP_MS, "L": LONG_MS + GAP_MS}
TOLERANCE = 0.4
ANSWER_MS = 5000          # after the first shake
WAIT_FIRST_MS = 10000     # for the first shake
# Shake detection as in shake.py: |a| - 1 g, here with a threshold and a
# refractory time so one shake counts once.
SHAKE_G = 1.0
REFRACTORY_MS = 180
WRONG_LIMIT = 3
DIGITS = {2: SHAPE_2, 3: SHAPE_3, 4: SHAPE_4, 5: SHAPE_5, 6: SHAPE_6}


def _mag(accel):
    try:
        x, y, z = accel.read()
        return math.sqrt(x * x + y * y + z * z) - 1
    except Exception:
        return 0


def _buzz_rhythm(leds, buz, rhythm):
    # Each beat lights the matrix for exactly as long as it sounds: a short
    # beat the centre square, a long beat the whole matrix.
    for b in rhythm:
        if b == "L":
            leds.fill(WHITE)
            buz.beep(BEAT_HZ, LONG_MS)
        else:
            leds.show_shape(SHAPE_INNER_3x3, WHITE)
            buz.beep(BEAT_HZ, SHORT_MS)
        leds.off()
        time.sleep_ms(GAP_MS)


def _matches(rhythm, onsets):
    if len(onsets) != len(rhythm):
        return False
    for i in range(len(rhythm) - 1):
        got = time.ticks_diff(onsets[i + 1], onsets[i])
        want = IOI[rhythm[i]]
        if abs(got - want) > want * TOLERANCE:
            return False
    return True


def play(nfc, leds, buz, accel, i2c, enow, batt=None):
    reader = NfcReader(nfc, COMMANDS)
    beats = MIN_BEATS
    variant = 0
    wrong_run = 0
    frame = 0
    try:
        while True:
            rhythm = RHYTHMS[beats][variant % len(RHYTHMS[beats])]
            leds.show_shape(DIGITS[beats], CYAN)
            time.sleep_ms(700)
            _buzz_rhythm(leds, buz, rhythm)
            signals.turn(leds, buz)

            # Record shakes: wait for the first, then ANSWER_MS more.
            onsets = []
            above = False
            last = 0
            start = time.ticks_ms()
            while True:
                msg_type, _data, _mac = enow.poll()
                if msg_type in ("stop", "start_game"):
                    return
                if frame % NFC_EVERY == 0:
                    cmd, _uid = reader.read_command(timeout=30)
                    if cmd in _EXIT_TAGS:
                        return
                frame += 1
                now = time.ticks_ms()
                if onsets:
                    if time.ticks_diff(now, onsets[0]) > ANSWER_MS or len(onsets) > MAX_BEATS:
                        break
                elif time.ticks_diff(now, start) > WAIT_FIRST_MS:
                    break
                m = _mag(accel)
                if m > SHAKE_G and not above and time.ticks_diff(now, last) > REFRACTORY_MS:
                    onsets.append(now)
                    last = now
                    leds.fill(WHITE)        # every counted shake is seen
                    above = True
                elif m < SHAKE_G * 0.5:
                    if above:
                        leds.off()
                    above = False
                time.sleep_ms(LOOP_MS)
            leds.off()
            time.sleep_ms(300)

            if _matches(rhythm, onsets):
                wrong_run = 0
                signals.right(leds, buz)
                if beats == MAX_BEATS:
                    signals.win(leds, buz)
                    beats = MIN_BEATS
                    variant += 1
                else:
                    beats += 1
                    signals.level_up(leds, buz)
            else:
                wrong_run += 1
                signals.wrong(leds, buz)
                if wrong_run >= WRONG_LIMIT and beats > MIN_BEATS:
                    beats -= 1
                    wrong_run = 0
            time.sleep_ms(400)
    finally:
        leds.off()
