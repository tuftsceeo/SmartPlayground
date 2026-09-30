"""
Splat Echo -- two-player pattern game, wand half
=================================================
Tag / start_game name: splatecho. Runs with the Splat Companion's
splatecho.py (SplatCompanion/Companion/), a separate program for the same
game.

Players:
  Caller (this wand) builds a pattern of Splats; Echo repeats it on the
  Splats. Echo scores when the whole pattern is repeated in order; Caller
  scores on a wrong Splat or a timeout.

Caller controls:
  tilt       pick a Splat: forward = 0, right = 1, back = 2, left = 3
             (the LEDs show the picked Splat's color; flat = no pick)
  press      add the picked Splat to the pattern (it lights and sounds)
  hold 1 s   finish the pattern; Echo's turn starts

Messages (dicts, "type" names not used elsewhere):
  sent      {"type": "echo_add", "unit": i}
            {"type": "echo_go", "n": steps}
  received  {"type": "echo_step", "idx": k}           Echo got step k right
            {"type": "echo_result", "ok": bool, "n": steps}

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
TILT_G = 0.5            # |x| or |y| above this picks a Splat
HOLD_MS = 1000          # button held this long finishes the pattern
MAX_STEPS = 12

# Splat unit -> wand color and buzzer tone. The Splat half uses the same
# unit order for its colors and sounds.
UNIT_COLOR = (RED, BLUE, YELLOW, PURPLE)
UNIT_TONE = (392, 523, 659, 784)


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
        self.score_caller = 0
        self.score_echo = 0

    def _fill(self, color):
        for i in range(NUM_LEDS):
            self.np[i] = color
        self.np.write()

    def _flash(self, color, ms):
        self._fill(color)
        time.sleep_ms(ms)
        self._fill(OFF)

    def _poll(self):
        """One ESP-NOW message and, every NFC_POLL_INTERVAL frames, one tag
        check. Returns ("exit", None), (msg_type, data) or (None, None)."""
        mt, data, _ = self.enow.poll()
        if mt in ("stop", "start_game"):
            return "exit", None
        self.frame += 1
        if self.frame % NFC_POLL_INTERVAL == 0:
            text, _ = read_tag_command(self.nfc, timeout=100)
            if text in _EXIT_TAGS:
                return "exit", None
        return mt, data

    def _show_score(self):
        print("  splatecho: score  Caller %d  Echo %d"
              % (self.score_caller, self.score_echo))

    def compose(self):
        """Caller builds a pattern. Returns its length, or None to exit."""
        steps = 0
        pressed_at = None
        shown = -1
        while True:
            mt, _ = self._poll()
            if mt == "exit":
                return None
            unit = _pick(self.accel)
            if unit != shown:
                self._fill(UNIT_COLOR[unit] if unit is not None else OFF)
                shown = unit
            down = self.btn.value() == 0
            now = time.ticks_ms()
            if down and pressed_at is None:
                pressed_at = now
            elif down and time.ticks_diff(now, pressed_at) >= HOLD_MS and steps:
                self.enow.broadcast({"type": "echo_go", "n": steps})
                print("  splatecho: pattern of %d sent -- Echo's turn" % steps)
                self.buz.beep(1047, 200)
                return steps
            elif not down and pressed_at is not None:
                short = time.ticks_diff(now, pressed_at) < HOLD_MS
                pressed_at = None
                if short and unit is not None and steps < MAX_STEPS:
                    steps += 1
                    self.enow.broadcast({"type": "echo_add", "unit": unit})
                    print("  splatecho: step %d -> Splat %d" % (steps, unit))
                    self.buz.beep(UNIT_TONE[unit], 120)
            time.sleep_ms(LOOP_DELAY_MS)

    def await_echo(self):
        """Wait for Echo's result. Returns True to play on, None to exit."""
        self._fill(WHITE_DIM)
        while True:
            mt, data = self._poll()
            if mt == "exit":
                return None
            if isinstance(data, dict) and data.get("type") == "echo_step":
                self.buz.beep(880, 60)
            elif isinstance(data, dict) and data.get("type") == "echo_result":
                if data.get("ok"):
                    self.score_echo += 1
                    self._flash(GREEN, 600)
                    self.buz.beep(1319, 150)
                else:
                    self.score_caller += 1
                    self._flash(RED, 600)
                    self.buz.beep(196, 300)
                self._show_score()
                return True
            time.sleep_ms(LOOP_DELAY_MS)

    def run(self):
        print("  splatecho: tilt to pick a Splat, press to add, hold 1 s to finish")
        while True:
            if self.compose() is None:
                return
            if self.await_echo() is None:
                return


def play(nfc, leds, buz, accel, i2c, enow, batt=None):
    buz.beep(523, 100)
    try:
        SplatEchoGame(nfc, leds, buz, accel, enow).run()
    finally:
        leds.off()
