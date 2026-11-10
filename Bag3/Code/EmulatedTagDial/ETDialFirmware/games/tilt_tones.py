"""
Tilt Tones — Play musical notes by tilting the wand in different directions
============================================================================
Hold the wand and tilt it left, right, forward, back, upside-down, or shake
it to play different notes. Each orientation lights up a different color!

Entry points:
    play(nfc, leds, buz, accel, i2c, enow, batt=None)  — called from main.py
    main()                                             — standalone testing

DO NOT shorten play(). main.py always passes 7 positional arguments.
"""

import machine
import time
import math
from machine import Pin

from pn532 import PN532
from nfc_reader import NfcReader
from game_tags import exit_tags_excluding

_EXIT_TAGS = exit_tags_excluding("jumpin")

from leds import (
    OFF, RED, GREEN, BLUE, YELLOW, PURPLE, ORANGE, TEAL, WHITE, PINK,
    SHAPE_ARROW_UP, SHAPE_ARROW_DN, SHAPE_ARROW_L, SHAPE_ARROW_R,
    SHAPE_STAR, SHAPE_LIGHTNING, SHAPE_HEART,
)

# ─── Hardware Config ───────────────────────────────────────────────
I2C_SDA    = 22
I2C_SCL    = 23
BUZZER_PIN = 19
BUTTON_PIN = 0
PN532_ADDR = 0x24

# ─── Game Config ───────────────────────────────────────────────────
COMMANDS          = _EXIT_TAGS
NFC_POLL_INTERVAL = 10
LOOP_DELAY_MS     = 60

TILT_THRESHOLD  = 0.5
SHAKE_THRESHOLD = 1.5

# ─── Orientation → (note_hz, duration_ms, color, shape, label) ─────
# Wand upright (tip up):  x ≈ -1.0
# Handle up (upside-down): x ≈ +1.0
# Left side up:           y ≈ +1.0
# Right side up:          y ≈ -1.0
# Face up:                z ≈ -1.0
# Back up:                z ≈ +1.0

ORIENTATIONS = [
    # (check_fn,  freq, dur,  color,   shape,          label)
    ("tip_up",    523,  200,  GREEN,   SHAPE_ARROW_UP, "Tip Up   C5"),
    ("handle_up", 659,  200,  ORANGE,  SHAPE_ARROW_DN, "Handle Up E5"),
    ("left_up",   784,  200,  BLUE,    SHAPE_ARROW_L,  "Left Up  G5"),
    ("right_up",  880,  200,  YELLOW,  SHAPE_ARROW_R,  "Right Up A5"),
    ("face_up",   1047, 200,  PURPLE,  SHAPE_STAR,     "Face Up  C6"),
    ("back_up",   392,  200,  TEAL,    SHAPE_HEART,    "Back Up  G4"),
    ("shake",     1319, 150,  RED,     SHAPE_LIGHTNING,"Shake!   E6"),
]


class TiltTonesGame:
    def __init__(self, nfc, leds, buz, accel, enow):
        self.nfc    = nfc
        self.leds   = leds
        self.buz    = buz
        self.accel  = accel
        self.enow   = enow

        self.reader = NfcReader(nfc, COMMANDS)
        self.btn    = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
        self._btn_was_down = (self.btn.value() == 0)

        self._frame       = 0
        self._last_orient = None   # avoid replaying the same note non-stop
        self._hold_frames = 0      # frames since orientation changed

    # ── Exit check ────────────────────────────────────────────────
    def _check_stop(self):
        msg_type, _, _ = self.enow.poll()
        if msg_type in ("stop", "start_game"):
            return True
        if self._frame % NFC_POLL_INTERVAL != 0:
            return False
        try:
            cmd, uid = self.reader.read_command(timeout=100)
            return cmd in _EXIT_TAGS
        except Exception:
            return False

    # ── Orientation detection ─────────────────────────────────────
    def _detect_orientation(self, x, y, z):
        mag = math.sqrt(x*x + y*y + z*z)
        if mag > SHAKE_THRESHOLD:
            return "shake"
        if x < -TILT_THRESHOLD and abs(y) < TILT_THRESHOLD and abs(z) < TILT_THRESHOLD:
            return "tip_up"
        if x > TILT_THRESHOLD and abs(y) < TILT_THRESHOLD and abs(z) < TILT_THRESHOLD:
            return "handle_up"
        if y > TILT_THRESHOLD and abs(x) < TILT_THRESHOLD:
            return "left_up"
        if y < -TILT_THRESHOLD and abs(x) < TILT_THRESHOLD:
            return "right_up"
        if z < -TILT_THRESHOLD and abs(x) < TILT_THRESHOLD:
            return "face_up"
        if z > TILT_THRESHOLD and abs(x) < TILT_THRESHOLD:
            return "back_up"
        return None   # neutral / in-between

    def _play_orient(self, orient_key):
        for entry in ORIENTATIONS:
            if entry[0] == orient_key:
                _, freq, dur, color, shape, label = entry
                print("  %s -> %d Hz" % (label, freq))
                self.leds.show_shape(shape, color)
                self.buz.beep(freq, dur)
                return

    # ── Main loop ─────────────────────────────────────────────────
    def run(self):
        # Idle: breathe white while waiting for a tilt
        self.leds.fill(WHITE)
        time.sleep_ms(200)
        self.leds.off()

        while True:
            if self._check_stop():
                return

            orient = None
            if self.accel:
                try:
                    x, y, z = self.accel.read()
                    orient = self._detect_orientation(x, y, z)
                except Exception:
                    pass

            if orient is not None:
                if orient != self._last_orient:
                    # New orientation — play note immediately
                    self._last_orient = orient
                    self._hold_frames = 0
                    self._play_orient(orient)
                else:
                    # Same orientation held — repeat note every ~1 second
                    self._hold_frames += 1
                    if self._hold_frames >= 16:   # 16 * 60ms ≈ 1 s
                        self._hold_frames = 0
                        self._play_orient(orient)
            else:
                # Neutral — show idle breathe, reset last orientation
                if self._last_orient is not None:
                    self._last_orient = None
                    self._hold_frames = 0
                self.leds.breathe(60, 60, 80, self._frame)

            time.sleep_ms(LOOP_DELAY_MS)
            self._frame += 1


def play(nfc, leds, buz, accel, i2c, enow, batt=None):
    """Called from main.py when the 'jumpin' tag is tapped."""
    # Entry fanfare — descending then up (unique to Tilt Tones)
    buz.beep(784, 80); time.sleep_ms(30)
    buz.beep(659, 80); time.sleep_ms(30)
    buz.beep(523, 80); time.sleep_ms(30)
    buz.beep(659, 80); time.sleep_ms(30)
    buz.beep(784, 120)

    print("\n  === TILT TONES ===")
    print("  Tilt the wand to play notes!")
    try:
        TiltTonesGame(nfc, leds, buz, accel, enow).run()
    finally:
        leds.off()
        print("\n  === RETURNING TO PROGRAMMING MODE ===\n")


def main():
    """Standalone entry — run directly: import jumpin; jumpin.main()"""
    i2c = machine.SoftI2C(sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=100_000)

    import brightness
    try:
        from opt3002 import OPT3002
        light = OPT3002(i2c); light.init()
        mult, lux = brightness.calibrate(light)
        if lux is not None:
            print("  Light: %.0f lux -> brightness x%.2f" % (lux, mult))
    except Exception as e:
        print("  [WARN] OPT3002: %s" % e)

    from leds import Leds
    from buzzer import Buzzer
    leds = Leds()
    buz  = Buzzer(BUZZER_PIN)

    nfc = PN532(i2c, PN532_ADDR)
    try:
        ic, ver, rev = nfc.begin()
        print("  PN5%02X fw %d.%d" % (ic, ver, rev))
    except Exception as e:
        print("  NFC init failed: %s" % e); return

    accel = None
    try:
        from lis2dw12 import LIS2DW12, RANGE_4G
        accel = LIS2DW12(i2c); accel.init(fs_range=RANGE_4G)
        print("  Accelerometer OK")
    except Exception as e:
        print("  [WARN] Accel: %s" % e)

    from espnow_manager import ESPNowManager
    enow = ESPNowManager(); enow.init()

    play(nfc, leds, buz, accel, i2c, enow, None)


if __name__ == "__main__":
    main()