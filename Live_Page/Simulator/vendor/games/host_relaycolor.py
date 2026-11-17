"""
Relay Color -- one player holds the color token; their button passes it to the next player
"""
import time
from machine import Pin

from nfc_reader import NfcReader
from game_tags import exit_tags_excluding
from leds import RED, GREEN, BLUE, YELLOW, PURPLE, WHITE, SHAPE_SPIRAL, ORANGE

GAME_ICON = (SHAPE_SPIRAL, ORANGE)
SPLAT_HOST = True
SPLATS_MIN = 1
SPLATS_MAX = 4
PLAYERS_MIN = 2

_EXIT_TAGS = exit_tags_excluding("host_relaycolor")
COMMANDS = _EXIT_TAGS
NFC_EVERY = 10
LOOP_MS = 20

# A wand's identity name (net.wands[i][1]) is also a Splat color name.
WAND_COLOR = {"turnred": RED, "turngreen": GREEN, "turnblue": BLUE,
              "turnyellow": YELLOW, "turnpurple": PURPLE, "turnwhite": WHITE}


def _give(net, p, dead):
    """Host: every connected Splat takes player p's color; tell the players."""
    for i in range(net.splat_count):
        if i not in dead:
            net.splat(i).color(net.wands[p][1])
    net.send(None, {"h": p})


def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
    if net is None:
        return
    reader = NfcReader(nfc, COMMANDS)
    btn = Pin(0, Pin.IN, Pin.PULL_UP)
    was_down = (btn.value() == 0)
    frame = 0
    holder = None
    lost_wands = set()
    lost_splats = set()
    if not net.is_host:
        leds.show_shape(GAME_ICON[0], GAME_ICON[1])
        buz.beep(784, 100)
        time.sleep_ms(700)
        leds.off()
    try:
        if net.is_host:
            holder = net.players[0]
            _give(net, holder, lost_splats)
        while True:
            if frame % NFC_EVERY == 0:
                cmd, _uid = reader.read_command(timeout=100)
                if cmd in _EXIT_TAGS:
                    return
            ev = net.poll()
            if ev == ("end",) or ev == ("leader_lost",):
                return
            if net.is_host:
                # ── host: owns the token ──
                if ev and ev[0] == "splat_lost":
                    lost_splats.add(ev[1])
                elif ev and ev[0] == "splat_back":
                    lost_splats.discard(ev[1])
                    net.splat(ev[1]).color(net.wands[holder][1])
                elif ev and ev[0] == "wand_lost":
                    lost_wands.add(ev[1])
                elif ev and ev[0] == "wand_back":
                    lost_wands.discard(ev[1])
                pass_now = ev and ev[0] == "msg" and ev[1] == holder and ev[2].get("pass")
                if pass_now or holder in lost_wands:
                    live = [p for p in net.players if p not in lost_wands]
                    if live:
                        later = [p for p in live if p > holder]
                        holder = later[0] if later else live[0]
                        _give(net, holder, lost_splats)
            else:
                # ── player: shows the token, passes with the button ──
                if ev and ev[0] == "msg" and "h" in ev[2]:
                    holder = ev[2]["h"]
                    if holder == net.me:
                        leds.fill(WAND_COLOR[net.wands[net.me][1]])
                        buz.beep(880, 80)
                    else:
                        leds.off()
                down = (btn.value() == 0)
                if down and not was_down and holder == net.me:
                    net.send(0, {"pass": 1})
                was_down = down
            time.sleep_ms(LOOP_MS)
            frame += 1
    finally:
        leds.off()
