"""
Code Breakers -- tap three animal cards on the display in the right order to open the treasure
=========================================================================================
A small group at the display. The display picks a secret order of 3 of the 5
animals (no repeats). Each tap shows the animal big for a moment, then its mark
in the next slot. After 3, feedback: one bright dot per animal in the right
place, one dim dot per right animal in the wrong place. Right: sparkles, then a
new code. Wrong: the guess moves up (dimmed, with its feedback) and the group
tries again.

Layout (rows): 0-3 last guess + its feedback, 6-9 this guess + feedback,
11-15 the try count. Blank rows between parts.

Cards: frog, cat, fish, bird, bunny (raised marks on the cards for blind
children). No buzzer here: all feedback is on the panel.
Messages: none sent or listened for.
"""
import random
import time

from nfc_reader import NfcReader
from display_tags import exit_tags_excluding
import icon_store
import draw16

_EXIT_TAGS = exit_tags_excluding("codebreakers")
CARDS = ("frog", "cat", "fish", "bird", "bunny")
COMMANDS = {"frog", "cat", "fish", "bird", "bunny"} | _EXIT_TAGS
CODE_LEN = 3
INTENSITY = 0.15
LOOP_MS = 40
NFC_EVERY = 6
UID_REPEAT_MS = 1200
TAP_SHOW_MS = 700
WIN_ICON = "sparkles"
WIN_MS = 2500

# Each animal's mark: a 4x4 pattern (differs in outline, not only color) and color.
MARKS = {
    "frog": (("####", "####", "####", "####"), (0, 160, 0)),
    "cat": ((".##.", "####", "####", ".##."), (230, 110, 0)),
    "fish": (("#..#", "####", "####", "#..#"), (0, 80, 220)),
    "bird": (("#..#", ".##.", ".##.", "...."), (230, 200, 0)),
    "bunny": (("#.#.", "#.#.", "####", "####"), (185, 200, 200)),
}
SLOT_COLS = (0, 5, 10)
FEEDBACK_COL = 15
LAST_ROW = 0
THIS_ROW = 6
COUNT_ROW = 11
EXACT = (185, 200, 200)
NEAR = (40, 44, 44)
EMPTY = (12, 12, 12)


def _mark(src, row, col, name, dim):
    pattern, rgb = MARKS[name]
    if dim:
        rgb = (rgb[0] // 4, rgb[1] // 4, rgb[2] // 4)
    for r in range(4):
        for c in range(4):
            if pattern[r][c] == "#":
                draw16.px(src, row + r, col + c, rgb)


def _feedback(src, row, exact, near):
    for k in range(CODE_LEN):
        color = EXACT if k < exact else (NEAR if k < exact + near else None)
        if color is not None:
            draw16.px(src, row + k, FEEDBACK_COL, color)


def _score(code, guess):
    exact = sum(1 for i in range(CODE_LEN) if guess[i] == code[i])
    near = sum(1 for g in guess if g in code) - exact
    return exact, near


def _render(leds, last, last_fb, guess, tries):
    src = leds.src
    draw16.clear(src)
    if last:
        for i, name in enumerate(last):
            _mark(src, LAST_ROW, SLOT_COLS[i], name, True)
        _feedback(src, LAST_ROW, last_fb[0], last_fb[1])
    for i in range(CODE_LEN):
        if i < len(guess):
            _mark(src, THIS_ROW, SLOT_COLS[i], guess[i], False)
        else:
            draw16.frame(src, THIS_ROW, SLOT_COLS[i], THIS_ROW + 3, SLOT_COLS[i] + 3, EMPTY)
    draw16.number(src, tries, COUNT_ROW)
    leds.draw_bytes(src)


def _new_code():
    pool = list(CARDS)
    code = []
    for _ in range(CODE_LEN):
        code.append(pool.pop(random.randrange(len(pool))))
    return code


def play(nfc, leds, buz, accel, i2c, enow, batt=None):
    if nfc is None:
        print("  [ERR] codebreakers needs the display's card reader")
        return
    reader = NfcReader(nfc, COMMANDS)
    code = _new_code()
    guess = []
    last = None
    last_fb = (0, 0)
    tries = 1
    last_uid = None
    last_uid_ms = 0
    frame = 0
    try:
        leds.set_intensity(INTENSITY)
        _render(leds, last, last_fb, guess, tries)
        while True:
            msg_type, _data, _mac = enow.poll()
            if msg_type in ("stop", "start_game"):
                return
            if frame % NFC_EVERY == 0:
                cmd, uid = reader.read_command(timeout=100)
                now = time.ticks_ms()
                if uid is not None and uid == last_uid and \
                        time.ticks_diff(now, last_uid_ms) < UID_REPEAT_MS:
                    cmd = None                   # same card still on the reader
                if uid is not None:
                    last_uid = uid
                    last_uid_ms = now
                if cmd in _EXIT_TAGS:
                    return
                if cmd in MARKS:
                    icon_store.read_icon(cmd, into=leds.src)   # the animal, big
                    leds.draw_bytes(leds.src)
                    time.sleep_ms(TAP_SHOW_MS)
                    guess.append(cmd)
                    if len(guess) == CODE_LEN:
                        exact, near = _score(code, guess)
                        if exact == CODE_LEN:
                            _render(leds, last, last_fb, guess, tries)
                            _feedback(leds.src, THIS_ROW, exact, near)
                            leds.draw_bytes(leds.src)
                            time.sleep_ms(1200)
                            icon_store.read_icon(WIN_ICON, into=leds.src)
                            leds.draw_bytes(leds.src)
                            time.sleep_ms(WIN_MS)
                            code = _new_code()
                            last = None
                            tries = 1
                        else:
                            last = guess
                            last_fb = (exact, near)
                            tries += 1
                        guess = []
                    _render(leds, last, last_fb, guess, tries)
            frame += 1
            time.sleep_ms(LOOP_MS)
    finally:
        leds.clear()
