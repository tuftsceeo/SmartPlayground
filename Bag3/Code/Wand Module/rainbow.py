"""
Rainbow Show — Battery Then Rainbow Display
===========================================
Shows battery level on the LED matrix, then a static rainbow pattern.
Tap STOP or station stop to exit.

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

_EXIT_TAGS = exit_tags_excluding("rainbow")
from leds import RED, ORANGE, YELLOW, GREEN, BLUE, PURPLE, PINK, GREEN_DIM

# ─── Hardware Config ───
I2C_SDA, I2C_SCL = 22, 23
BUZZER_PIN, BUTTON_PIN, PN532_ADDR = 19, 0, 0x24

# ─── Game Config ───
COMMANDS = _EXIT_TAGS
NFC_POLL_INTERVAL = 10
LOOP_DELAY_MS = 40
NUM_LEDS = 25

RAINBOW = [RED, ORANGE, YELLOW, GREEN, BLUE, PURPLE, PINK]

SOUNDS = {
    'start': [(523, 80, 40), (659, 80, 40), (784, 120, 0)],
}


def _play_sound(buz, name):
    for freq, dur, gap in SOUNDS.get(name, []):
        buz.beep(freq, dur)
        if gap:
            time.sleep_ms(gap)


class RainbowGame:
    def __init__(self, nfc, leds, buz, enow, batt):
        self.nfc = nfc
        self.leds = leds
        self.buz = buz
        self.enow = enow
        self.batt = batt
        self.reader = NfcReader(nfc, COMMANDS)
        self._frame = 0
        self._show_battery_bar()
        time.sleep_ms(2000)
        self._show_rainbow()

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

    def _show_battery_bar(self):
        soc = 100
        if self.batt is not None:
            try:
                _, soc = self.batt.read_all()
                soc = max(0, min(100, int(soc)))
            except Exception:
                pass
        lit = max(1, min(NUM_LEDS, int(soc / 100.0 * NUM_LEDS)))
        print("  Battery: %d%% (%d LEDs)" % (soc, lit))
        self.leds.off()
        for i in range(lit):
            row = 4 - (i // 5)
            col = i % 5
            self.leds.np[row * 5 + col] = GREEN_DIM
        self.leds.np.write()

    def _show_rainbow(self):
        for i in range(NUM_LEDS):
            self.leds.np[i] = RAINBOW[i % len(RAINBOW)]
        self.leds.np.write()

    def run(self):
        print("  Rainbow display active.")
        print("  Tap STOP tag or station stop to exit.\n")

        while True:
            if self._check_stop():
                print("  Stop detected")
                return
            time.sleep_ms(LOOP_DELAY_MS)
            self._frame += 1


def play(nfc, leds, buz, accel, i2c, enow, batt=None):
    _play_sound(buz, 'start')
    print("\n  === RAINBOW SHOW ===")
    try:
        RainbowGame(nfc, leds, buz, enow, batt).run()
    finally:
        leds.off()
        print("\n  === RETURNING TO PROGRAMMING MODE ===\n")


def main():
    """
    Standalone entry point for testing without main.py.
    Run directly: import rainbow; rainbow.main()
    """
    print("\n" + "=" * 45)
    print("  Rainbow Show")
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

    batt = None
    try:
        from max17048 import MAX17048
        batt = MAX17048(i2c)
        v, s = batt.read_all()
        print("  Battery gauge OK (%.2f V, %d%%)" % (v, s))
    except Exception as e:
        print("  [WARN] Battery: %s" % e)

    from espnow_manager import ESPNowManager
    enow = ESPNowManager()
    enow.init()

    print()
    play(nfc, leds, buz, None, i2c, enow, batt)


if __name__ == "__main__":
    main()
