"""
Pattern Stomp -- the host lights a pattern across four Splats; the group stomps it back in order
"""
import random
import time

from nfc_reader import NfcReader
from game_tags import exit_tags_excluding
from leds import (BLUE, YELLOW, PURPLE, WHITE, CYAN,
                  SHAPE_CIRCLE, SHAPE_TRIANGLE, SHAPE_BORDER, SHAPE_STAR,
                  SHAPE_0, SHAPE_1, SHAPE_2, SHAPE_3, SHAPE_4, SHAPE_5,
                  SHAPE_6, SHAPE_7, SHAPE_8, SHAPE_9)
import signals

GAME_ICON = (SHAPE_BORDER, PURPLE)
SPLAT_HOST = True
SPLATS_MIN = 4
SPLATS_MAX = 4
PLAYERS_MIN = 1

_EXIT_TAGS = exit_tags_excluding("host_patternstomp")
COMMANDS = _EXIT_TAGS
NFC_EVERY = 10
LOOP_MS = 20

# Shared color table: Splat i -> (Splat color, wand color, wand shape, Splat note).
TABLE = (
    ("turnblue", BLUE, SHAPE_CIRCLE, "note_c"),
    ("turnyellow", YELLOW, SHAPE_TRIANGLE, "note_e"),
    ("turnpurple", PURPLE, SHAPE_BORDER, "note_g"),
    ("turnwhite", WHITE, SHAPE_STAR, "note_c_high"),
)
START_LEN = 2
MAX_LEN = 10
STEP_ON_MS = 600
STEP_OFF_MS = 250
ANSWER_MS = 10000         # per stomp; then the pattern is shown again
DIGITS = (SHAPE_0, SHAPE_1, SHAPE_2, SHAPE_3, SHAPE_4, SHAPE_5,
          SHAPE_6, SHAPE_7, SHAPE_8, SHAPE_9)


def _round_shape(n):
    return DIGITS[n if n < 10 else 9]


def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
    if net is None:
        return
    reader = NfcReader(nfc, COMMANDS)
    frame = 0
    lost = set()              # Splats that dropped out (host)
    pattern = [random.randrange(4) for _ in range(START_LEN)]
    pos = 0
    state = "show"            # host: show, wait, paused
    step = 0                  # host: index into pattern while showing
    lit = False               # host: the step's Splat is lit
    at = time.ticks_ms()
    try:
        if net.is_host:
            for i in range(4):
                net.splat(i).off()
        else:
            leds.show_shape(_round_shape(1), CYAN)
        while True:
            ev = net.poll()
            if ev == ("end",) or ev == ("leader_lost",):
                return
            if frame % NFC_EVERY == 0:
                cmd, _uid = reader.read_command(timeout=100)
                if cmd in _EXIT_TAGS:
                    return
            frame += 1
            now = time.ticks_ms()

            if not net.is_host:
                # ── player: show the round, echo right / wrong / win ──
                if ev and ev[0] == "msg":
                    d = ev[2]
                    if "round" in d:
                        leds.show_shape(_round_shape(d["round"]), CYAN)
                    elif "ok" in d:
                        signals.right(leds, buz)
                        leds.show_shape(_round_shape(d["ok"]), CYAN)
                    elif "bad" in d:
                        signals.wrong(leds, buz)
                    elif "watch" in d:
                        signals.turn(leds, buz)
                    elif "win" in d:
                        signals.win(leds, buz)
                time.sleep_ms(LOOP_MS)
                continue

            # ── host: decides everything ──
            if ev and ev[0] in ("wand_lost", "wand_back"):
                # The group plays as one team: carry on with whoever is there.
                print(f"  pattern stomp: {ev[0]} {ev[1]}, carrying on")
            elif ev and ev[0] == "splat_lost":
                lost.add(ev[1])
                state = "paused"
                for i in range(4):
                    if i not in lost:
                        net.splat(i).off()
                net.send(None, {"watch": 1})
                signals.turn(leds, buz)
            elif ev and ev[0] == "splat_back":
                lost.discard(ev[1])
                if not lost and state == "paused":
                    state, step, lit, pos, at = "show", 0, False, 0, now
            elif ev and ev[0] == "press" and state == "wait":
                i = ev[1]
                color, rgb, shape, note = TABLE[i]
                net.splat(i).play([color, note])
                leds.show_shape(shape, rgb)
                if i == pattern[pos]:
                    pos += 1
                    if pos == len(pattern):
                        n = len(pattern) - START_LEN + 1
                        net.send(None, {"ok": n + 1})
                        signals.right(leds, buz)
                        if len(pattern) == MAX_LEN:
                            net.send(None, {"win": 1})
                            signals.win(leds, buz)
                            return
                        pattern.append(random.randrange(4))
                        state, step, lit, pos, at = "show", 0, False, 0, now
                else:
                    net.send(None, {"bad": 1})
                    signals.wrong(leds, buz)
                    state, step, lit, pos, at = "show", 0, False, 0, now
                if state == "wait":
                    at = now
                time.sleep_ms(250)           # let the stomped Splat show
                net.splat(i).off()

            if state == "show":
                # One step at a time without blocking: net.poll() must keep
                # running or the players' wands see the host as lost.
                wait = STEP_ON_MS if lit else STEP_OFF_MS
                if time.ticks_diff(now, at) >= wait:
                    at = now
                    if lit:
                        net.splat(pattern[step]).off()
                        leds.off()
                        lit = False
                        step += 1
                        if step == len(pattern):
                            state = "wait"
                            pos = 0
                            net.send(None, {"watch": 1})
                            signals.turn(leds, buz)
                            leds.show_shape(_round_shape(len(pattern) - START_LEN + 1), CYAN)
                    else:
                        if step == 0:
                            net.send(None, {"round": len(pattern) - START_LEN + 1})
                        color, rgb, shape, note = TABLE[pattern[step]]
                        net.splat(pattern[step]).play([color, note])
                        leds.show_shape(shape, rgb)
                        lit = True
            elif state == "wait" and time.ticks_diff(now, at) > ANSWER_MS:
                state, step, lit, pos, at = "show", 0, False, 0, now
            time.sleep_ms(LOOP_MS)
    finally:
        leds.off()
