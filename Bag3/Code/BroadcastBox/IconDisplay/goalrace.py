"""
Team Goal Race — the shared display
====================================
Shows a ready mark while a round is open, then the winning team's icon: a
tree for green, a whale for blue. The first goal message of a round wins;
later ones are ignored until a stop clears it.

This is the ICON DISPLAY half of a two-device game. MockWand runs its own
goalrace.py -- a different program, with its own signature and its own loop.
Nothing is shared between them but the ESP-NOW messages below.

Messages this game listens for:
    {"type": "goal", "team": "green"|"blue"}   a wand reached the goal
Messages it broadcasts:
    {"type": "winner", "team": ...}            so the wands can react

Entry point:
    play(nfc, panel, enow)  — called from main.py

    nfc   — an NfcReader, already built, or None until a card reader is
            fitted. Note this differs from a wand game, which is handed the
            raw PN532 driver and builds its own reader.
    panel — the icon_matrix.Matrix itself
    enow  — ESPNowManager; poll it every loop iteration
"""

import time

from display_tags import exit_tags_excluding
import icon_store

_EXIT_TAGS = exit_tags_excluding("goalrace")

# ─── Game Config ───
# Declared as literals so the send checklist and the Box's write menu can
# read the cards this game needs without running it. The display only reads
# cards to leave a game; the round itself is driven over ESP-NOW.
COMMANDS = _EXIT_TAGS

# Icon names, resolved from icons/<name>.py by icon_store.read_icon().
ICON_READY = "ready"
TEAM_ICON = {
    "green": "tree",
    "blue": "whale",
}

# Below MAX_INTENSITY (0.50), which is a measured supply ceiling rather than
# a preference: 256 pixels at full brightness exceed the driver board. The
# ready mark sits dimmer still, because it is what the panel shows for most
# of a session and sustained heat is its own failure mode.
READY_INTENSITY = 0.12
WINNER_INTENSITY = 0.30

NFC_POLL_FRAMES = 12      # a card read is 200-500ms; not every frame
LOOP_DELAY_MS = 40
WINNER_HOLD_MS = 6000     # how long a winner stays up before the next round


def _show(panel, name, intensity):
    """Draw a named icon. A missing or malformed one raises rather than
    leaving the panel blank -- a display that looks alive and shows nothing
    is the hardest failure to diagnose from across a room."""
    panel.set_intensity(intensity)
    icon_store.read_icon(name, into=panel.src)
    panel.draw_bytes(panel.src)


def play(nfc, panel, enow):
    print("\n  === TEAM GOAL RACE (display) ===")
    winner = None
    winner_ms = 0
    frame = 0
    try:
        _show(panel, ICON_READY, READY_INTENSITY)
        while True:
            frame += 1

            msg_type, data, _mac = enow.poll()
            if msg_type in ("stop", "start_game"):
                print("  stop received")
                return

            if msg_type == "raw" and isinstance(data, dict) and data.get("type") == "goal":
                team = data.get("team")
                if team not in TEAM_ICON:
                    print("  [WARN] goal names an unknown team: %r" % (team,))
                elif winner is None:
                    winner = team
                    winner_ms = time.ticks_ms()
                    print("  team %s took it" % team)
                    _show(panel, TEAM_ICON[team], WINNER_INTENSITY)
                    # Tell the wands, so the team that won can celebrate and
                    # the others can reset.
                    enow.broadcast({"type": "winner", "team": team})

            # The round reopens on its own, so a class can keep playing
            # without anyone touching the display.
            if winner is not None and \
                    time.ticks_diff(time.ticks_ms(), winner_ms) > WINNER_HOLD_MS:
                winner = None
                print("  next round")
                _show(panel, ICON_READY, READY_INTENSITY)

            # The display reads cards only to leave a game. nfc is None until
            # a reader is fitted; the loop is written for one either way.
            if nfc is not None and frame % NFC_POLL_FRAMES == 0:
                cmd, _uid = nfc.read_command(timeout=100)
                if cmd in _EXIT_TAGS:
                    print("  exit tag scanned")
                    return

            time.sleep_ms(LOOP_DELAY_MS)
    finally:
        panel.clear()
        print("\n  === DISPLAY IDLE ===\n")
