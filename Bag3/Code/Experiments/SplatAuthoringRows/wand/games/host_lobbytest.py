"""
Lobby Test -- hardware check: a player's button lights the next Splat in that player's color
"""
import time
from machine import Pin

from nfc_reader import NfcReader
from game_tags import exit_tags_excluding
from leds import RED, GREEN, BLUE, YELLOW, PURPLE, WHITE, SHAPE_DIAMOND, CYAN

GAME_ICON = (SHAPE_DIAMOND, CYAN)
SPLAT_HOST = True
SPLATS_MIN = 1
SPLATS_MAX = 4
PLAYERS_MIN = 1

_EXIT_TAGS = exit_tags_excluding("host_lobbytest")
COMMANDS = _EXIT_TAGS
NFC_EVERY = 10
LOOP_MS = 20

# A wand's identity name (net.wands[i][1]) is also a Splat color name.
WAND_COLOR = {"turnred": RED, "turngreen": GREEN, "turnblue": BLUE,
              "turnyellow": YELLOW, "turnpurple": PURPLE, "turnwhite": WHITE}


def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
    if net is None:
        return
    reader = NfcReader(nfc, COMMANDS)
    btn = Pin(0, Pin.IN, Pin.PULL_UP)
    was_down = (btn.value() == 0)
    frame = 0
    nxt = 0
    lit = None
    if not net.is_host:
        leds.show_shape(GAME_ICON[0], GAME_ICON[1])
        buz.beep(523, 100)
        time.sleep_ms(700)
        leds.fill(WAND_COLOR[net.wands[net.me][1]])
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
                # ── host: lights Splats ──
                if ev and ev[0] == "msg" and ev[2].get("btn") and net.splat_count:
                    i = nxt % net.splat_count
                    nxt += 1
                    if lit is not None and lit != i:
                        net.splat(lit).off()
                    net.splat(i).color(net.wands[ev[1]][1])
                    lit = i
                elif ev and ev[0] == "press":
                    net.splat(ev[1]).color("turnwhite")
            else:
                # ── player: button goes to the host ──
                down = (btn.value() == 0)
                if down and not was_down:
                    net.send(0, {"btn": 1})
                was_down = down
            time.sleep_ms(LOOP_MS)
            frame += 1
    finally:
        leds.off()
