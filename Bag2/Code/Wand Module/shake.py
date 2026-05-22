"""
Shake Fill — Accelerometer Fill Game
====================================
Shake the wand harder to light more LEDs on the 5x5 matrix.
Level only goes up (your best shake). Press button to reset.

Entry points:
    play(nfc, leds, buz, accel, i2c, enow)  — called from main.py
    main()                                   — standalone testing
"""

import machine
import time
import math
import random
from machine import Pin

from pn532 import PN532
from nfc_reader import NfcReader
from leds import RED, GREEN, BLUE, YELLOW, PURPLE, PINK, OFF

# ─── Hardware Config ───
I2C_SDA, I2C_SCL = 22, 23
BUZZER_PIN, BUTTON_PIN, PN532_ADDR = 19, 0, 0x24

# ─── Game Config ───
COMMANDS = {"stop"}
NFC_POLL_INTERVAL = 10
LOOP_DELAY_MS = 40
NUM_LEDS = 25

PICK_COLORS = [RED, GREEN, BLUE, YELLOW, PURPLE, PINK]

SOUNDS = {
    'start': [(523, 80, 40), (659, 80, 40), (784, 120, 0)],
}


def _play_sound(buz, name):
    for freq, dur, gap in SOUNDS.get(name, []):
        buz.beep(freq, dur)
        if gap:
            time.sleep_ms(gap)


class ShakeGame:
    def __init__(self, nfc, leds, buz, accel, enow):
        self.nfc = nfc
        self.leds = leds
        self.buz = buz
        self.accel = accel
        self.enow = enow
        self.reader = NfcReader(nfc, COMMANDS)
        self.btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
        self._btn_was_down = (self.btn.value() == 0)
        self._frame = 0
        self.level = 0
        self.color = random.choice(PICK_COLORS)
        print("  Your color: %s" % (self.color,))

    def _check_stop(self):
        if self.enow:
            msg_type, _, _ = self.enow.poll()
            if msg_type == "stop":
                return True
        if self._frame % NFC_POLL_INTERVAL != 0:
            return False
        try:
            cmd, uid = self.reader.read_command(timeout=100)
            return cmd == "stop"
        except Exception:
            return False

    def _accel_mag(self):
        if self.accel is None:
            return 0
        try:
            x, y, z = self.accel.read()
            return math.sqrt(x * x + y * y + z * z) - 1
        except Exception:
            return 0

    def _check_button_reset(self):
        down = (self.btn.value() == 0)
        if down and not self._btn_was_down:
            time.sleep_ms(30)
            if self.btn.value() == 0:
                self._btn_was_down = True
                self.level = 0
                self.leds.off()
                return True
        elif not down and self._btn_was_down:
            self._btn_was_down = False
        return False

    def _render_level(self, level):
        self.leds.off()
        n = min(level, NUM_LEDS)
        for i in range(n):
            row = 4 - (i // 5)
            col = i % 5
            self.leds.np[row * 5 + col] = self.color
        self.leds.np.write()

    def run(self):
        print("  Shake harder to fill the matrix!")
        print("  Press button to reset. Tap STOP to exit.\n")

        while True:
            if self._check_stop():
                print("  Stop detected")
                return

            if self._check_button_reset():
                pass
            else:
                acc = min(NUM_LEDS, int(self._accel_mag() ** 3 * 1.5))
                if self.level < acc:
                    self.level = acc

            self._render_level(self.level)
            time.sleep_ms(LOOP_DELAY_MS)
            self._frame += 1


def play(nfc, leds, buz, accel, i2c, enow):
    _play_sound(buz, 'start')
    print("\n  === SHAKE FILL ===")
    try:
        ShakeGame(nfc, leds, buz, accel, enow).run()
    finally:
        leds.off()
        print("\n  === RETURNING TO PROGRAMMING MODE ===\n")


def main():
    """
    Standalone entry point for testing without main.py.
    Run directly: import shake; shake.main()
    """
    print("\n" + "=" * 45)
    print("  Shake Fill")
    print("=" * 45)

    i2c = machine.SoftI2C(sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=100_000)

    import brightness
    try:
        from opt3002 import OPT3002
        light = OPT3002(i2c)
        light.init()
        mult, lux = brightness.calibrate(light)
        if lux is not None:
            print("  Light: %.0f lux -> brightness x%.2f" % (lux, mult))
    except Exception as e:
        print("  [WARN] OPT3002: %s — brightness x1.00" % e)

    from leds import Leds
    from buzzer import Buzzer
    leds = Leds()
    buz = Buzzer(BUZZER_PIN)

    nfc = PN532(i2c, PN532_ADDR)
    try:
        ic, ver, rev = nfc.begin()
        print("  PN5%02X fw %d.%d — NFC ready" % (ic, ver, rev))
    except Exception as e:
        print("  NFC init failed: %s" % e)
        return

    accel = None
    try:
        from lis2dw12 import LIS2DW12, RANGE_4G
        accel = LIS2DW12(i2c)
        accel.init(fs_range=RANGE_4G)
        print("  Accelerometer OK")
    except Exception as e:
        print("  [WARN] Accel: %s" % e)

    from espnow_manager import ESPNowManager
    enow = ESPNowManager()
    enow.init()

    print()
    play(nfc, leds, buz, accel, i2c, enow)


if __name__ == "__main__":
    main()
