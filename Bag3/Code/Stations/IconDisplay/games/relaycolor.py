"""
Relay Timer -- the shared display for relaycolor
=================================================
Listens to the wands' relaycolor game and shows, from across the room, which
colour is being held and how long the current holder has had it. When the
colour moves on, the time that pass took drops to the lower half in the old
colour, and the counter starts again from 0.

It only listens: it is not a player and not the leader. It assumes one
relaycolor game is running nearby. It has the wands' slug, so the same
relaycolor card or start_game starts it, as goalrace does on both devices.

Messages this game listens for:
    {"type": "relay_pass", "color": "turnblue", "to": 1}
        broadcast by MockWand/games/relaycolor.py each time a wand takes the
        colour; "color" is a splat_api.COLOR_RGB name, "to" the wand index
Messages it broadcasts:
    none

Entry point:
    play(nfc, panel, enow)  -- called from main.py
"""

import time

from display_tags import exit_tags_excluding
import draw16

_EXIT_TAGS = exit_tags_excluding("relaycolor")

COMMANDS = _EXIT_TAGS

# splat_api.COLOR_RGB for the relaycolor names, so the panel matches the Splats.
COLOR_RGB = {
    "turnred": (255, 0, 0), "turngreen": (0, 255, 0),
    "turnblue": (0, 0, 255), "turnpurple": (160, 0, 200),
    "turnyellow": (255, 180, 0), "turnwhite": (200, 200, 200),
}
UNKNOWN_RGB = (200, 200, 200)
WHITE = (200, 200, 200)
DIM = (60, 60, 60)

INTENSITY = 0.15

_BAR_TOP = 0          # holder colour, rows 0-1
_NOW_ROW = 3          # seconds the current holder has had it
_LAST_ROW = 10        # how long the previous pass took
_BAR_BOTTOM = 15

LOOP_DELAY_MS = 40
NFC_POLL_FRAMES = 12


def _secs(ms):
    """Seconds as at most three glyphs: "4.2" under 10 s, "37" up to 99."""
    s = ms / 1000
    if s < 10:
        return "%d.%d" % (int(s), int(s * 10) % 10)
    return "%d" % min(int(s), 99)


def _render(src, color, now_text, last_text, last_color):
    draw16.clear(src)
    if color is None:
        draw16.text(src, "--", _NOW_ROW, (draw16.W - draw16.width("--")) // 2, DIM)
        return
    draw16.rect(src, _BAR_TOP, 0, _BAR_TOP + 1, draw16.W - 1, color)
    draw16.text(src, now_text, _NOW_ROW, (draw16.W - draw16.width(now_text)) // 2, WHITE)
    if last_text:
        draw16.text(src, last_text, _LAST_ROW, (draw16.W - draw16.width(last_text)) // 2, last_color)
    draw16.rect(src, _BAR_BOTTOM, 0, _BAR_BOTTOM, draw16.W - 1, color)


def play(nfc, panel, enow):
    print("\n  === RELAY TIMER (display) ===")
    color = None
    last_color = WHITE
    last_text = ""
    since = time.ticks_ms()
    shown = None
    frame = 0
    try:
        panel.set_intensity(INTENSITY)
        while True:
            frame += 1

            msg_type, data, _mac = enow.poll()
            if msg_type in ("stop", "start_game"):
                print("  stop received")
                return

            if (msg_type == "raw" and isinstance(data, dict)
                    and data.get("type") == "relay_pass"):
                now = time.ticks_ms()
                name = data.get("color")
                rgb = COLOR_RGB.get(name)
                if rgb is None:
                    print("  [WARN] relay_pass names an unknown colour: %r" % (name,))
                    rgb = UNKNOWN_RGB
                if color is not None:
                    took = time.ticks_diff(now, since)
                    last_text = _secs(took)
                    last_color = color
                    print("  relaytimer: %s -> wand %s after %d ms" % (name, data.get("to"), took))
                else:
                    print("  relaytimer: %s at wand %s" % (name, data.get("to")))
                color = rgb
                since = now

            now_text = _secs(time.ticks_diff(time.ticks_ms(), since)) if color else ""
            view = (color, now_text, last_text)
            if view != shown:
                _render(panel.src, color, now_text, last_text, last_color)
                draw16.show(panel)
                shown = view

            if nfc is not None and frame % NFC_POLL_FRAMES == 0:
                cmd, _uid = nfc.read_command(timeout=100)
                if cmd in _EXIT_TAGS:
                    print("  exit tag scanned")
                    return

            time.sleep_ms(LOOP_DELAY_MS)
    finally:
        panel.clear()
        print("\n  === DISPLAY IDLE ===\n")
