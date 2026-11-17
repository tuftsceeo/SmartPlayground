"""
splatcolors.py -- BENCH: step one Splat through candidate palette colors.

Bench script for the stress-test prep, block A (palette size).
Copy to a player wand's /games/splatcolors.py (a pulled-game slot; not part
of the wand bundle). Pair one Splat to that wand, then start the game with
an NDEF text card reading "splatcolors" or a start_game naming it.

Press the Splat: next color. The serial log prints the index, name and RGB
of the color now showing, and the wand's LEDs show it too. After the last
color it wraps to the first. Any exit tag or ESP-NOW stop ends it.
"""
import time

from nfc_reader import NfcReader
from game_tags import exit_tags_excluding

SPLATS_LOCAL = 1
_EXIT_TAGS = exit_tags_excluding("splatcolors")
NFC_EVERY = 10
LOOP_MS = 20

# 16 candidates, ordered around the hue wheel so neighbours are the pairs
# most likely to be confused.
COLORS = (
    ("red", (255, 0, 0)),
    ("orange", (255, 60, 0)),
    ("amber", (255, 120, 0)),
    ("yellow", (255, 180, 0)),
    ("lime", (140, 255, 0)),
    ("green", (0, 255, 0)),
    ("mint", (0, 255, 80)),
    ("teal", (0, 200, 140)),
    ("cyan", (0, 200, 255)),
    ("sky", (0, 100, 255)),
    ("blue", (0, 0, 255)),
    ("indigo", (70, 0, 255)),
    ("purple", (160, 0, 200)),
    ("magenta", (255, 0, 160)),
    ("pink", (255, 60, 90)),
    ("white", (200, 200, 200)),
)


def _show(splats, leds, i):
    name, rgb = COLORS[i]
    splats.unit(0).link.setLEDsON(rgb)
    leds.fill((rgb[0] // 4, rgb[1] // 4, rgb[2] // 4))
    print(f"  splatcolors {i + 1}/{len(COLORS)}: {name} {rgb}")


def play(nfc, leds, buz, accel, i2c, enow, batt=None, splats=None):
    reader = NfcReader(nfc, _EXIT_TAGS)
    i = 0
    frame = 0
    try:
        _show(splats, leds, i)
        while True:
            msg_type, _data, _mac = enow.poll()
            if msg_type in ("stop", "start_game"):
                return
            if frame % NFC_EVERY == 0:
                cmd, _uid = reader.read_command(timeout=100)
                if cmd in _EXIT_TAGS:
                    return
            ev = splats.poll()
            if ev and ev[0] == "press":
                i = (i + 1) % len(COLORS)
                _show(splats, leds, i)
            time.sleep_ms(LOOP_MS)
            frame += 1
    finally:
        splats.unit(0).off()
        leds.off()
