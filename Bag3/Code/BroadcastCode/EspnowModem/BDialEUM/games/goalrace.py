"""
Team Goal Race — Join a Team, Race to the Goal
==============================================
Tap a team tag to join green or blue, then race to tap the goal tag. The
first wand to reach it wins the round for its team.

This is the WAND half of a two-device game. The icon display runs its own
goalrace.py -- a different program, with its own signature and its own loop,
that happens to play the same game. Nothing is shared between them but the
ESP-NOW messages below.

Messages this game broadcasts:
    {"type": "goal", "team": "green"|"blue"}   a wand reached the goal
Messages it listens for:
    {"type": "winner", "team": ...}            the display says who won

Entry points:
    play(nfc, leds, buz, accel, i2c, enow, batt=None)  — called from main.py
    main()                                             — standalone testing
"""

import machine
import time
from machine import Pin

from pn532 import PN532
from nfc_reader import NfcReader
from game_tags import exit_tags_excluding

_EXIT_TAGS = exit_tags_excluding("goalrace")
from leds import GREEN, BLUE, WHITE, AMBER, OFF, SHAPE_CHECK, SHAPE_X

# ─── Hardware Config ───
I2C_SDA, I2C_SCL = 22, 23
BUZZER_PIN, PN532_ADDR = 19, 0x24

# ─── Game Config ───
# Declared as literals so the send checklist, the Box's write menu and the
# simulator can all read the cards this game needs without running it.
COMMANDS = {"teamgreen", "teamblue", "goal"} | _EXIT_TAGS

NFC_POLL_INTERVAL = 10       # frames between card reads -- a read is 200-500ms
LOOP_DELAY_MS = 40
UID_REPEAT_MS = 1200         # ignore the same card until it has been away

TEAM_TAGS = {
    "teamgreen": "green",
    "teamblue": "blue",
}

TEAM_COLOR = {
    "green": GREEN,
    "blue": BLUE,
}


class GoalRaceGame:
    def __init__(self, nfc, leds, buz, enow):
        self.nfc = nfc
        self.leds = leds
        self.buz = buz
        self.enow = enow
        self.reader = NfcReader(nfc, COMMANDS)
        self.team = None
        self.scored = False
        self._frame = 0
        self._last_uid = None
        self._last_uid_ms = 0

    # ── Feedback ──
    def _show_team(self):
        if self.team is None:
            self.leds.fill(WHITE)
        else:
            self.leds.fill(TEAM_COLOR[self.team])

    def _join(self, team):
        self.team = team
        self.scored = False
        print("  joined team %s" % team)
        self.buz.beep(523, 80)
        time.sleep_ms(60)
        self.buz.beep(784, 120)
        self._show_team()

    def _score(self):
        """Tell everyone this wand reached the goal.

        A plain broadcast of a plain dict. The display reads it through the
        same enow.poll() every other game uses -- there is no goalrace
        message class, and there should not be one.
        """
        self.scored = True
        print("  GOAL for team %s" % self.team)
        self.enow.broadcast({"type": "goal", "team": self.team})
        for _ in range(3):
            self.leds.show_shape(SHAPE_CHECK, TEAM_COLOR[self.team])
            self.buz.beep(880, 90)
            time.sleep_ms(90)
            self.leds.off()
            time.sleep_ms(70)
        self._show_team()

    def _no_team_yet(self):
        print("  tap a team tag first")
        self.leds.show_shape(SHAPE_X, AMBER)
        self.buz.beep(220, 150)
        time.sleep_ms(400)
        self._show_team()

    # ── Loop ──
    def _check_radio(self):
        """True when main.py should take the wand back."""
        msg_type, data, _mac = self.enow.poll()
        if msg_type in ("stop", "start_game"):
            return True
        if msg_type == "raw" and isinstance(data, dict) and data.get("type") == "winner":
            won = data.get("team")
            print("  round over -- team %s took it" % won)
            if won == self.team:
                self.leds.show_shape(SHAPE_CHECK, TEAM_COLOR[won])
                self.buz.beep(1047, 200)
            else:
                self.leds.fill(OFF)
            time.sleep_ms(600)
            self.scored = False
            self._show_team()
        return False

    def _check_cards(self):
        """True when an exit tag was scanned."""
        if self._frame % NFC_POLL_INTERVAL != 0:
            return False
        cmd, uid = self.reader.read_command(timeout=100)
        now = time.ticks_ms()
        if uid is not None and uid == self._last_uid and \
                time.ticks_diff(now, self._last_uid_ms) < UID_REPEAT_MS:
            # A card left sitting on the reader reads over and over; without
            # this guard one tap on the goal scores several times.
            return False
        if uid is not None:
            self._last_uid = uid
            self._last_uid_ms = now
        if cmd is None:
            return False
        if cmd in _EXIT_TAGS:
            return True
        if cmd in TEAM_TAGS:
            self._join(TEAM_TAGS[cmd])
        elif cmd == "goal":
            if self.team is None:
                self._no_team_yet()
            elif not self.scored:
                self._score()
        return False

    def run(self):
        print("  Tap a team tag (teamgreen / teamblue), then race to the goal.")
        print("  Tap STOP or another game tag to exit.\n")
        self._show_team()
        while True:
            if self._check_radio():
                print("  stop received")
                return
            if self._check_cards():
                print("  exit tag scanned")
                return
            self._frame += 1
            time.sleep_ms(LOOP_DELAY_MS)


def play(nfc, leds, buz, accel, i2c, enow, batt=None):
    print("\n  === TEAM GOAL RACE ===")
    buz.beep(523, 80)
    try:
        GoalRaceGame(nfc, leds, buz, enow).run()
    finally:
        leds.off()
        print("\n  === RETURNING TO PROGRAMMING MODE ===\n")


def main():
    """Standalone entry point for testing without main.py."""
    print("\n  Team Goal Race\n")
    i2c = machine.SoftI2C(sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=100_000)

    from leds import Leds
    from buzzer import Buzzer
    leds = Leds()
    buz = Buzzer(BUZZER_PIN)

    nfc = PN532(i2c, PN532_ADDR)
    ic, ver, rev = nfc.begin()
    print("  PN5%02X fw %d.%d — NFC ready" % (ic, ver, rev))

    from espnow_manager import ESPNowManager
    enow = ESPNowManager()
    enow.init()

    play(nfc, leds, buz, None, i2c, enow)


if __name__ == "__main__":
    main()
