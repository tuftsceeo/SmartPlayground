"""
Solo Echo -- Simon on one wand and its own Splat
================================================
Tag / start_game name: soloecho. Solo Splat game (SPEC section 6, "Solo
Splat games"): needs 1 paired, READY Splat on this wand. The solo port of
splatecho.py, which stays until this one is play-tested.

  watch   the Splat plays the sequence: each step is a color and its note;
          the wand shows the same color
  repeat  tilt the wand to pick a color (forward, right, back, left; flat
          keeps the last pick). The Splat and the wand show the pick.
          Press the Splat (or the wand button) to enter it.
  result  a full repeat: rainbow and a tune, one step is added. A miss:
          red and a low tune, then the score (steps repeated) as lit
          pixels for SCORE_MS, and a new 1-step sequence.
  dropout the Splat's link drops: the wand shows a dim red hourglass until
          it is back, then the sequence plays again.

Exits on a stop / other game tag or ESP-NOW "stop" / "start_game".

Entry point:
    play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None)
"""

import random
import time
from machine import Pin

from nfc_reader import read_tag_command
from game_tags import exit_tags_excluding
from leds import RED, BLUE, YELLOW, PURPLE, OFF
from leds import SHAPE_HOURGLASS, SHAPE_PLUS

SPLATS_LOCAL = 1

_EXIT_TAGS = exit_tags_excluding("soloecho")

NUM_LEDS = 25
BUTTON_PIN = 0
NFC_POLL_INTERVAL = 10
LOOP_DELAY_MS = 20
TILT_G = 0.5            # |x| or |y| above this picks a color
STEP_MS = 500           # one sequence step lit
GAP_MS = 200            # dark gap between steps
SCORE_MS = 2000
RAINBOW_MS = 900
RAINBOW_LEVEL = 150

# Choice -> (Splat color, Splat note, wand color, wand tone)
CHOICES = (
    ("turnred", "note_c", RED, 523),
    ("turnblue", "note_e", BLUE, 659),
    ("turnyellow", "note_g", YELLOW, 784),
    ("turnpurple", "note_c_high", PURPLE, 1047),
)
LOST_RGB = (25, 0, 0)


class _Exit(Exception):
    pass


class _Replay(Exception):
    """The Splat came back after a dropout: play the sequence again."""


def _wheel(pos):
    pos &= 255
    if pos < 85:
        r, g, b = 255 - pos * 3, pos * 3, 0
    elif pos < 170:
        pos -= 85
        r, g, b = 0, 255 - pos * 3, pos * 3
    else:
        pos -= 170
        r, g, b = pos * 3, 0, 255 - pos * 3
    return (r * RAINBOW_LEVEL // 255, g * RAINBOW_LEVEL // 255,
            b * RAINBOW_LEVEL // 255)


def _pick(accel):
    x, y, z = accel.read()
    if abs(x) < TILT_G and abs(y) < TILT_G:
        return None
    if abs(y) >= abs(x):
        return 0 if y > 0 else 2
    return 1 if x > 0 else 3


class SoloEcho:
    def __init__(self, nfc, leds, buz, accel, enow, net):
        self.nfc = nfc
        self.np = leds.np
        self.buz = buz
        self.accel = accel
        self.enow = enow
        self.net = net
        self.splat = net.splat(0)
        self.btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
        self.was_down = self.btn.value() == 0
        self.frame = 0
        self.lost = False

    # ── display ──
    def _icon(self, shape, color):
        for i in range(NUM_LEDS):
            self.np[i] = color if i in shape else OFF
        self.np.write()

    def _fill(self, color, n=NUM_LEDS):
        for i in range(NUM_LEDS):
            self.np[i] = color if i < n else OFF
        self.np.write()

    def _rainbow(self):
        t0 = time.ticks_ms()
        k = 0
        while time.ticks_diff(time.ticks_ms(), t0) < RAINBOW_MS:
            for i in range(NUM_LEDS):
                self.np[i] = _wheel(i * 10 + k * 16)
            self.np.write()
            k += 1
            self._tick()
            time.sleep_ms(40)

    # ── input ──
    def _tick(self):
        """Exit checks and Splat events. Returns True on a press (Splat 0
        or the wand button). Raises _Exit. Blocks while the Splat is lost."""
        mt, _, _ = self.enow.poll()
        if mt in ("stop", "start_game"):
            raise _Exit()
        self.frame += 1
        if self.frame % NFC_POLL_INTERVAL == 0:
            text, _ = read_tag_command(self.nfc, timeout=100)
            if text in _EXIT_TAGS:
                raise _Exit()
        down = self.btn.value() == 0
        pressed = down and not self.was_down
        self.was_down = down
        ev = self.net.poll()
        if ev == ("press", 0):
            pressed = True
        elif ev == ("splat_lost", 0):
            self.lost = True
            self._icon(SHAPE_HOURGLASS, LOST_RGB)
            print("  soloecho: Splat lost; waiting")
            while self.lost:
                time.sleep_ms(LOOP_DELAY_MS)
                if self.net.poll() == ("splat_back", 0):
                    self.lost = False
                    print("  soloecho: Splat back")
                    raise _Replay()
                mt, _, _ = self.enow.poll()
                if mt in ("stop", "start_game"):
                    raise _Exit()
                self.frame += 1
                if self.frame % NFC_POLL_INTERVAL == 0:
                    text, _ = read_tag_command(self.nfc, timeout=100)
                    if text in _EXIT_TAGS:
                        raise _Exit()
        return pressed

    def _wait(self, ms):
        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < ms:
            self._tick()
            time.sleep_ms(LOOP_DELAY_MS)

    # ── phases ──
    def _show_step(self, c):
        color, note, rgb, tone = CHOICES[c]
        self.splat.play([color, note])
        self._fill(rgb)
        self.buz.beep(tone, 80)

    def watch(self, seq):
        self._icon(SHAPE_HOURGLASS, (40, 40, 40))
        self._wait(GAP_MS * 2)
        for c in seq:
            self._show_step(c)
            self._wait(STEP_MS)
            self.splat.off()
            self._fill(OFF)
            self._wait(GAP_MS)

    def repeat(self, seq):
        """True for a full repeat, False on a miss."""
        pick = 0
        for want in seq:
            self._icon(SHAPE_PLUS, CHOICES[pick][2])
            self.splat.color(CHOICES[pick][0])
            while True:
                tilt = _pick(self.accel)
                if tilt is not None and tilt != pick:
                    pick = tilt
                    self._icon(SHAPE_PLUS, CHOICES[pick][2])
                    self.splat.color(CHOICES[pick][0])
                if self._tick():
                    break
                time.sleep_ms(LOOP_DELAY_MS)
            if pick != want:
                return False
            self._show_step(pick)
            self._wait(STEP_MS // 2)
        return True

    def run(self):
        seq = [random.randint(0, 3)]
        while True:
            try:
                self.watch(seq)
                ok = self.repeat(seq)
                self.splat.off()
                if ok:
                    self._rainbow()
            except _Replay:
                continue
            if ok:
                self.buz.celebrate()
                seq.append(random.randint(0, 3))
            else:
                print(f"  soloecho: miss at length {len(seq)}")
                self._fill(RED)
                self.buz.error()
                time.sleep_ms(400)
                self._fill(CHOICES[0][2], n=min(len(seq) - 1, NUM_LEDS))
                time.sleep_ms(SCORE_MS)
                seq = [random.randint(0, 3)]


def play(nfc, leds, buz, accel, i2c, enow, batt=None, net=None):
    game = SoloEcho(nfc, leds, buz, accel, enow, net)
    buz.beep(523, 100)
    try:
        game.run()
    except _Exit:
        pass
    finally:
        leds.off()
