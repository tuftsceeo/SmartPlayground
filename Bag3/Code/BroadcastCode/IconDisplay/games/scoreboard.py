"""
Team Scoreboard — the shared display
====================================
Keeps a running tally of each team's goals and draws it, so a class can see
the score from across the room without anyone keeping it on paper.

This is the demo for lib/draw16.py, and it is the case named icons cannot
cover: there is no icons/<name>.py for "7-4", and there could not be without
a file per score. Every frame here is composed at runtime instead.

It deliberately listens for the SAME message MockWand/goalrace.py already
broadcasts, so it runs against the existing wand half unchanged -- tap
`scoreboard` on the display instead of `goalrace` and the same wands now
feed a running tally rather than a one-shot winner icon.

Messages this game listens for:
    {"type": "goal", "team": "green"|"blue"}   a wand reached the goal
Messages it broadcasts:
    none -- the wands need nothing back to keep scoring

Entry point:
    play(nfc, panel, enow)  — called from main.py

    nfc   — an NfcReader, already built, or None until a card reader is
            fitted.
    panel — the icon_matrix.Matrix itself
    enow  — ESPNowManager; poll it every loop iteration

Not served over the wire: draw16 is firmware-resident (code_server.py sends
a pulled game its own file and icons, nothing from lib/), so this one ships
in the tree rather than as a pullable slug.
"""

import time

from display_tags import exit_tags_excluding
import draw16

_EXIT_TAGS = exit_tags_excluding("scoreboard")

# ─── Game Config ───
# Declared as literals so the send checklist and the Box's write menu can
# read the cards this game needs without running it.
COMMANDS = _EXIT_TAGS

TEAM_COLOR = {
    "green": (0, 200, 60),
    "blue": (40, 120, 200),
}
DIVIDER = (60, 60, 60)

# Static content sits lit for a whole session, so it stays at the low end of
# the range -- see main.py's IDLE_INTENSITY and the readme's voltage ramp.
INTENSITY = 0.15

# Two 3x5 digits plus their gap is 7 columns, so each team gets a 7-wide
# half with two spare columns down the middle for the divider.
_HALF_W = 7
_LEFT_COL = 0
_RIGHT_COL = 9
_SCORE_ROW = 6
_BAR_ROW = 1
_MAX_SHOWN = 99   # 3 digits will not fit a half; the tally itself keeps counting

LOOP_DELAY_MS = 40
NFC_POLL_FRAMES = 12


def _render(src, green, blue):
    """Compose the whole frame: a colour bar per team over its own score.

    Split out so the layout can be exercised off-device -- this module
    imports nothing that needs hardware, so a bench script can call this
    against a bytearray and render it through the Station's preview.
    """
    draw16.clear(src)

    # Which half belongs to which team, so the numbers need no labels.
    draw16.rect(src, _BAR_ROW, _LEFT_COL, _BAR_ROW, _LEFT_COL + _HALF_W - 1,
                TEAM_COLOR["green"])
    draw16.rect(src, _BAR_ROW, _RIGHT_COL, _BAR_ROW, _RIGHT_COL + _HALF_W - 1,
                TEAM_COLOR["blue"])
    draw16.rect(src, _SCORE_ROW - 1, 7, _SCORE_ROW + draw16.GLYPH_H, 7, DIVIDER)

    for value, color, left in (
        (green, TEAM_COLOR["green"], _LEFT_COL),
        (blue, TEAM_COLOR["blue"], _RIGHT_COL),
    ):
        shown = "%d" % (value if value <= _MAX_SHOWN else _MAX_SHOWN)
        col = left + (_HALF_W - draw16.width(shown)) // 2
        draw16.text(src, shown, _SCORE_ROW, col, color)


def play(nfc, panel, enow):
    print("\n  === TEAM SCOREBOARD (display) ===")
    score = {"green": 0, "blue": 0}
    frame = 0
    dirty = True
    try:
        panel.set_intensity(INTENSITY)
        while True:
            frame += 1

            msg_type, data, _mac = enow.poll()
            if msg_type in ("stop", "start_game"):
                print("  stop received")
                return

            if msg_type == "raw" and isinstance(data, dict) and data.get("type") == "goal":
                team = data.get("team")
                if team not in score:
                    print("  [WARN] goal names an unknown team: %r" % (team,))
                else:
                    score[team] += 1
                    dirty = True
                    print("  %s %d - %d blue" % (team, score["green"], score["blue"]))

            # Redraw only on a change: the panel holds its last frame, and
            # pushing 768 bytes every 40 ms buys nothing.
            if dirty:
                _render(panel.src, score["green"], score["blue"])
                draw16.show(panel)
                dirty = False

            if nfc is not None and frame % NFC_POLL_FRAMES == 0:
                cmd, _uid = nfc.read_command(timeout=100)
                if cmd in _EXIT_TAGS:
                    print("  exit tag scanned")
                    return

            time.sleep_ms(LOOP_DELAY_MS)
    finally:
        panel.clear()
        print("\n  === DISPLAY IDLE ===\n")
