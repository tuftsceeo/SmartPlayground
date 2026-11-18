"""
Splat Tag -- the host lights a Splat in a player's color; that player's wand scores when it is pressed
"""
import random
import time

from nfc_reader import NfcReader
from game_tags import exit_tags_excluding
from leds import (RED, GREEN, BLUE, YELLOW, PURPLE, WHITE, ORANGE, SHAPE_BULLSEYE,
                  SHAPE_0, SHAPE_1, SHAPE_2, SHAPE_3, SHAPE_4, SHAPE_5)

GAME_ICON = (SHAPE_BULLSEYE, ORANGE)
SPLAT_HOST = True
SPLATS_MIN = 2
SPLATS_MAX = 4
PLAYERS_MIN = 1

_EXIT_TAGS = exit_tags_excluding("host_splattag")
COMMANDS = _EXIT_TAGS
NFC_EVERY = 10
LOOP_MS = 20

# A wand's identity name (net.wands[i][1]) is also a Splat color name.
WAND_COLOR = {"turnred": RED, "turngreen": GREEN, "turnblue": BLUE,
              "turnyellow": YELLOW, "turnpurple": PURPLE, "turnwhite": WHITE}

DIGITS = (SHAPE_0, SHAPE_1, SHAPE_2, SHAPE_3, SHAPE_4, SHAPE_5)
WIN_SCORE = 5
ROUND_MS = 8000
PAUSE_MS = 1200


def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
    if net is None:
        return
    reader = NfcReader(nfc, COMMANDS)
    frame = 0
    lost_splats = set()
    lost_wands = set()
    scores = [0] * len(net.wands)
    target = None                 # host: (splat, player)
    state = "pick"                # host: pick, wait, pause
    at = time.ticks_ms()
    if not net.is_host:
        leds.show_shape(GAME_ICON[0], GAME_ICON[1])
        buz.beep(659, 100)
        time.sleep_ms(700)
        leds.off()
    try:
        while True:
            if frame % NFC_EVERY == 0:
                cmd, _uid = reader.read_command(timeout=100)
                if cmd in _EXIT_TAGS:
                    return
            ev = net.poll()
            if ev == ("end",) or ev == ("leader_lost",):
                return
            if net.is_host:
                # ── host: decides everything ──
                if ev and ev[0] == "splat_lost":
                    lost_splats.add(ev[1])
                elif ev and ev[0] == "splat_back":
                    lost_splats.discard(ev[1])
                elif ev and ev[0] == "wand_lost":
                    lost_wands.add(ev[1])
                elif ev and ev[0] == "wand_back":
                    lost_wands.discard(ev[1])
                elif ev and ev[0] == "press" and state == "wait" and ev[1] == target[0]:
                    p = target[1]
                    scores[p] += 1
                    net.splat(ev[1]).play(["turnyellow", "cow"])
                    net.send(None, {"s": scores})
                    if scores[p] >= WIN_SCORE:
                        net.send(None, {"win": p})
                        return
                    target = None
                    state = "pause"
                    at = time.ticks_ms()
                waited = time.ticks_diff(time.ticks_ms(), at)
                lost_target = target and (target[0] in lost_splats or target[1] in lost_wands)
                if state == "pause" and waited >= PAUSE_MS or state == "wait" and (
                        waited >= ROUND_MS or lost_target):
                    if target:
                        net.splat(target[0]).off()
                    target = None
                    state = "pick"
                if state == "pick":
                    splats = [i for i in range(net.splat_count) if i not in lost_splats]
                    players = [p for p in net.players if p not in lost_wands]
                    if splats and players:
                        target = (random.choice(splats), random.choice(players))
                        net.splat(target[0]).color(net.wands[target[1]][1])
                        state = "wait"
                        at = time.ticks_ms()
            else:
                # ── player: shows what the host sends ──
                if ev and ev[0] == "msg":
                    d = ev[2]
                    if "s" in d:
                        leds.show_shape(DIGITS[d["s"][net.me]], WAND_COLOR[net.wands[net.me][1]])
                    elif "win" in d:
                        leds.fill(WAND_COLOR[net.wands[d["win"]][1]])
                        if d["win"] == net.me:
                            buz.success()
                        time.sleep_ms(3000)
                        return
            time.sleep_ms(LOOP_MS)
            frame += 1
    finally:
        leds.off()
