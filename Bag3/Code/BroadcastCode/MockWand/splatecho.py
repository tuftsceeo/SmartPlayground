"""
Splat Echo -- two-player Simon, wand half
==========================================
Tag / start_game name: splatecho. Runs with the Splat Companion's
splatecho.py (SplatCompanion/Companion/), which runs the game: joining,
turns, playback, checking and scores. See that file for the rules.

This wand:
  joins     sends echo_hello every HELLO_MS until the hub answers with
            echo_you (its player number); blinks dim white until then
  identity  player 0 is cyan, player 1 is orange
  turn      own turn: steady player color and a chirp -- go to the Splats;
            other player's turn: dim player color
  repeat    each correct Splat press: a short beep
  add       when the hub asks (echo_add_now): tilt to pick a Splat
            (forward = 0, right = 1, back = 2, left = 3; the LEDs show its
            color, flat shows the player color), press to add it
  result    green (correct) or red (round over) flash, then this player's
            score as lit pixels for SCORE_MS

Exits on ESP-NOW "stop"/"start_game" or a stop / other game tag.

Entry point:
    play(nfc, leds, buz, accel, i2c, enow, batt=None)  -- called from main.py
"""

import time
from machine import Pin

from nfc_reader import read_tag_command
from game_tags import exit_tags_excluding
from leds import RED, BLUE, YELLOW, PURPLE, GREEN, WHITE_DIM, OFF

_EXIT_TAGS = exit_tags_excluding("splatecho")

NUM_LEDS = 25
BUTTON_PIN = 0
NFC_POLL_INTERVAL = 10
LOOP_DELAY_MS = 20
HELLO_MS = 1000
TILT_G = 0.5            # |x| or |y| above this picks a Splat
SCORE_MS = 2000

# Splat unit -> wand color and buzzer tone; same unit order as the hub's.
UNIT_COLOR = (RED, BLUE, YELLOW, PURPLE)
UNIT_TONE = (392, 523, 659, 784)
PLAYER_COLOR = ((0, 180, 240), (200, 80, 0))       # cyan, orange
PLAYER_DIM = ((0, 20, 30), (25, 10, 0))


def _pick(accel):
    """Splat unit chosen by tilt, or None when the wand is near flat."""
    x, y, z = accel.read()
    if abs(x) < TILT_G and abs(y) < TILT_G:
        return None
    if abs(y) >= abs(x):
        return 0 if y > 0 else 2
    return 1 if x > 0 else 3


class SplatEchoGame:
    def __init__(self, nfc, leds, buz, accel, enow):
        self.nfc = nfc
        self.np = leds.np
        self.buz = buz
        self.accel = accel
        self.enow = enow
        self.btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
        self.frame = 0
        self.me = None           # player number from the hub

    def _fill(self, color, n=NUM_LEDS):
        for i in range(NUM_LEDS):
            self.np[i] = color if i < n else OFF
        self.np.write()

    def _poll(self):
        """One ESP-NOW message and, every NFC_POLL_INTERVAL frames, one tag
        check. Returns ("exit", None), (kind, data) or (None, None)."""
        mt, data, _ = self.enow.poll()
        if mt in ("stop", "start_game"):
            return "exit", None
        self.frame += 1
        if self.frame % NFC_POLL_INTERVAL == 0:
            text, _ = read_tag_command(self.nfc, timeout=100)
            if text in _EXIT_TAGS:
                return "exit", None
        if isinstance(data, dict):
            return data.get("type"), data
        return None, None

    def join(self):
        """Hello until the hub assigns a player number. False to exit."""
        next_hello = time.ticks_ms()
        blink = False
        while self.me is None:
            kind, data = self._poll()
            if kind == "exit":
                return False
            if kind == "echo_you":
                self.me = data.get("player")
                print("  splatecho: I am player %d" % self.me)
                self.buz.beep(784, 80)
                break
            now = time.ticks_ms()
            if time.ticks_diff(now, next_hello) >= 0:
                self.enow.broadcast({"type": "echo_hello"})
                blink = not blink
                self._fill(WHITE_DIM if blink else OFF)
                next_hello = time.ticks_add(now, HELLO_MS)
            time.sleep_ms(LOOP_DELAY_MS)
        self._fill(PLAYER_DIM[self.me])
        return True

    def add_step(self):
        """Tilt to pick, press to add one step. False to exit."""
        print("  splatecho: your turn to add a step")
        shown = -1
        was_down = self.btn.value() == 0
        while True:
            kind, _ = self._poll()
            if kind == "exit":
                return False
            unit = _pick(self.accel)
            if unit != shown:
                self._fill(UNIT_COLOR[unit] if unit is not None else PLAYER_COLOR[self.me])
                shown = unit
            down = self.btn.value() == 0
            if down and not was_down and unit is not None:
                self.enow.broadcast({"type": "echo_add", "unit": unit})
                print("  splatecho: added Splat %d" % unit)
                self.buz.beep(UNIT_TONE[unit], 150)
                self._fill(PLAYER_DIM[self.me])
                return True
            was_down = down
            time.sleep_ms(LOOP_DELAY_MS)

    def show_result(self, data):
        ok = data.get("ok")
        self._fill(GREEN if ok else RED)
        if ok:
            self.buz.beep(1319, 120)
        else:
            self.buz.beep(196, 400)
        time.sleep_ms(500)
        scores = data.get("scores") or [0, 0]
        mine = scores[self.me] if self.me < len(scores) else 0
        print("  splatecho: scores %s (me: player %d)" % (scores, self.me))
        if not ok:
            self._fill(PLAYER_COLOR[self.me], n=min(mine, NUM_LEDS))
            time.sleep_ms(SCORE_MS)
        self._fill(PLAYER_DIM[self.me])

    def run(self):
        if not self.join():
            return
        while True:
            kind, data = self._poll()
            if kind == "exit":
                return
            if kind == "echo_turn":
                if data.get("player") == self.me:
                    print("  splatecho: my turn (length %d)" % data.get("len", 0))
                    self._fill(PLAYER_COLOR[self.me])
                    self.buz.beep(1047, 80)
                    self.buz.beep(1319, 80)
                else:
                    self._fill(PLAYER_DIM[self.me])
            elif kind == "echo_step" and data.get("player") == self.me:
                self.buz.beep(880, 50)
            elif kind == "echo_add_now" and data.get("player") == self.me:
                if not self.add_step():
                    return
            elif kind == "echo_result":
                self.show_result(data)
            elif kind == "echo_you":
                self.me = data.get("player")
            time.sleep_ms(LOOP_DELAY_MS)


def play(nfc, leds, buz, accel, i2c, enow, batt=None):
    buz.beep(523, 100)
    try:
        SplatEchoGame(nfc, leds, buz, accel, enow).run()
    finally:
        leds.off()
