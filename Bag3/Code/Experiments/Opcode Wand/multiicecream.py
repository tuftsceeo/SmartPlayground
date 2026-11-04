"""
Multi Ice Cream — Three Scoop Shop
==================================
Build up to three scoops of virtual ice cream: count button presses upright, flip to commit each
scoop. Center column shows count while scooping. Tap STOP to exit.

Entry points:
    play(nfc, leds, buz, accel, i2c, enow)  — called from main.py
    main()                                   — standalone testing
"""

import machine
import time
from machine import Pin

from pn532 import PN532
from nfc_reader import NfcReader
from game_tags import exit_tags_excluding

_EXIT_TAGS = exit_tags_excluding("multiicecream")
from leds import PURPLE, PINK, BLUE, GREEN, YELLOW, ORANGE, RED, WHITE, OFF

# ─── Hardware Config ───
I2C_SDA, I2C_SCL = 22, 23
BUZZER_PIN, BUTTON_PIN, PN532_ADDR = 19, 0, 0x24

# ─── Game Config ───
COMMANDS = _EXIT_TAGS
NFC_POLL_INTERVAL = 10
LOOP_DELAY_MS = 40

UPRIGHT_THRESHOLD = 0.7
UPSIDEDOWN_THRESHOLD = -0.7

NUM_SCOOPS = 3
COUNT_BAR_LEN = 5
COUNT_COLUMN = [2, 7, 12, 17, 22]

# Scoop LED ranges on 5x5 (start inclusive, end exclusive)
SCOOP_RANGES = [(0, 10), (10, 15), (15, 25)]

SCOOP_RAMP = [RED, ORANGE, YELLOW, GREEN, BLUE, PINK, PURPLE, WHITE]

SOUNDS = {
    'start': [(523, 80, 40), (659, 80, 40), (784, 120, 0)],
    'scoop': [(880, 60, 30), (1100, 80, 0)],
}


def _play_sound(buz, name):
    for freq, dur, gap in SOUNDS.get(name, []):
        buz.beep(freq, dur)
        if gap:
            time.sleep_ms(gap)


def _color_from_count(count):
    if count < 1:
        return WHITE
    if count >= 8:
        return WHITE
    return SCOOP_RAMP[count - 1]


class MultiIceCreamGame:
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
        self._reset_cycle(full=True)

    def _reset_cycle(self, full=False):
        self.button_count = 0
        self.scoop_index = 0
        self.scoop_colors = [None] * NUM_SCOOPS
        self.counting_mode = False
        self.state = 'Upright'
        if full:
            self.leds.fill(WHITE)

    def _restart_for_new_cycle(self):
        self.button_count = 0
        self.scoop_index = 0
        self.scoop_colors = [None] * NUM_SCOOPS
        self.counting_mode = False

    def _check_stop(self):
        if self.enow:
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

    def _render_committed(self):
        self.leds.off()
        for s in range(NUM_SCOOPS):
            c = self.scoop_colors[s]
            if c is None:
                continue
            start, end = SCOOP_RANGES[s]
            for i in range(start, end):
                self.leds.np[i] = c
        self.leds.np.write()

    def _render_count_bar(self):
        self.leds.off()
        n = min(self.button_count, COUNT_BAR_LEN)
        for i in range(n):
            self.leds.np[COUNT_COLUMN[i]] = WHITE
        self.leds.np.write()

    def _check_button_press(self):
        down = (self.btn.value() == 0)
        if down and not self._btn_was_down and self.state == 'Upright':
            time.sleep_ms(30)
            if self.btn.value() == 0:
                while self.btn.value() == 0:
                    time.sleep_ms(10)
                self._btn_was_down = True

                if self.scoop_index >= NUM_SCOOPS:
                    self._restart_for_new_cycle()

                self.button_count += 1
                self.counting_mode = True
                self._render_count_bar()
                return True
        elif not down:
            self._btn_was_down = False
        return False

    def _read_orientation(self):
        if self.accel is None:
            return
        try:
            x, y, z = self.accel.read()
            if self.state == 'Upright':
                if x < UPSIDEDOWN_THRESHOLD:
                    self.state = 'Upside_down'
            elif self.state == 'Upside_down':
                if x > UPRIGHT_THRESHOLD:
                    self.state = 'Upright'
                    if self.scoop_index < NUM_SCOOPS and self.counting_mode:
                        chosen = _color_from_count(self.button_count)
                        self.scoop_colors[self.scoop_index] = chosen
                        self.scoop_index += 1
                        self.button_count = 0
                        self.counting_mode = False
                        _play_sound(self.buz, 'scoop')
                    self._render_committed()
        except Exception as e:
            print("  Accel err: %s" % str(e))

    def run(self):
        print("  Make 3 scoops: press to count, flip to commit each.")
        print("  Tap STOP tag or station stop to exit.\n")

        while True:
            if self._check_stop():
                print("  Stop detected")
                return

            self._check_button_press()
            self._read_orientation()

            if not self.counting_mode and self.scoop_index < NUM_SCOOPS:
                if self.scoop_index == 0 and self.scoop_colors[0] is None:
                    self.leds.fill(WHITE)
                elif self.scoop_index > 0 or any(self.scoop_colors):
                    self._render_committed()

            time.sleep_ms(LOOP_DELAY_MS)
            self._frame += 1


def play(nfc, leds, buz, accel, i2c, enow):
    _play_sound(buz, 'start')
    print("\n  === MULTI ICE CREAM ===")
    try:
        MultiIceCreamGame(nfc, leds, buz, accel, enow).run()
    finally:
        leds.off()
        print("\n  === RETURNING TO PROGRAMMING MODE ===\n")


def main():
    """
    Standalone entry point for testing without main.py.
    Run directly: import multiicecream; multiicecream.main()
    """
    print("\n" + "=" * 45)
    print("  Multi Ice Cream")
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
