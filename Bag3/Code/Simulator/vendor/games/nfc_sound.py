"""
NFC Bell Choir — Tap Note Tags, Hold Button to Play
===================================================
Scan note NFC tags to pick your bell. Hold button to play. Tap STOP to exit.

Entry points:
    play(nfc, leds, buz, accel, i2c, enow)  — called from main.py
    main()                                   — standalone testing
"""

import machine
import time
import random
from machine import Pin

from pn532 import PN532
from nfc_reader import NfcReader
from game_tags import exit_tags_excluding

_EXIT_TAGS = exit_tags_excluding("nfcsound")
from buzzer import NOTE_FREQ
from leds import RED, ORANGE, YELLOW, GREEN, BLUE, PURPLE, PINK, WHITE, OFF

# ─── Hardware Config ───
I2C_SDA, I2C_SCL = 22, 23
BUZZER_PIN, BUTTON_PIN, PN532_ADDR = 19, 0, 0x24

# ─── Game Config ───
COMMANDS = {"notec", "noted", "notee", "notef", "noteg", "notea", "noteb"} | _EXIT_TAGS
NFC_POLL_INTERVAL = 5
LOOP_DELAY_MS = 40
BEEP_MS = 80

# Map NFC tag names to display note keys
TAG_TO_NOTE = {
    "notec": "C4", "noted": "D4", "notee": "E4", "notef": "F4",
    "noteg": "G4", "notea": "A4", "noteb": "B4",
}

NOTES = {
    'C4': 262, 'D4': 294, 'E4': 330, 'F4': 349,
    'G4': 392, 'A4': 440, 'B4': 494, 'C5': 523,
}

NOTE_COLORS = {
    'C4': RED, 'D4': ORANGE, 'E4': YELLOW, 'F4': GREEN,
    'G4': BLUE, 'A4': PURPLE, 'B4': PINK, 'C5': WHITE,
}

SOUNDS = {
    'start': [(523, 80, 40), (659, 80, 40), (784, 120, 0)],
}


def _play_sound(buz, name):
    for freq, dur, gap in SOUNDS.get(name, []):
        buz.beep(freq, dur)
        if gap:
            time.sleep_ms(gap)


class NfcSoundGame:
    def __init__(self, nfc, leds, buz, enow):
        self.nfc = nfc
        self.leds = leds
        self.buz = buz
        self.enow = enow
        self.reader = NfcReader(nfc, COMMANDS)
        self.btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
        self._btn_was_down = (self.btn.value() == 0)
        self._frame = 0
        self._assign_random_note()

    def _assign_random_note(self):
        self.note = random.choice(list(NOTES.keys()))
        self.frequency = NOTES[self.note]
        print("  You were assigned %s (%d Hz)" % (self.note, self.frequency))
        print("  Tap a note tag to change your bell.\n")

    def _set_note_from_tag(self, tag):
        if tag not in TAG_TO_NOTE:
            return
        self.note = TAG_TO_NOTE[tag]
        if tag in NOTE_FREQ:
            self.frequency = NOTE_FREQ[tag]
        else:
            self.frequency = NOTES.get(self.note, 440)
        print("  Note changed to %s" % self.note)
        self.buz.beep(self.frequency, 120)

    def _check_stop(self):
        if self.enow:
            msg_type, _, _ = self.enow.poll()
            if msg_type in ("stop", "start_game"):
                return True
        if self._frame % NFC_POLL_INTERVAL != 0:
            return False
        try:
            cmd, uid = self.reader.read_command(timeout=100)
            if cmd in _EXIT_TAGS:
                return True
            if cmd in TAG_TO_NOTE:
                self._set_note_from_tag(cmd)
        except Exception:
            pass
        return False

    def run(self):
        print("  Hold button to play your note!")
        print("  Tap STOP tag or station stop to exit.\n")

        while True:
            if self._check_stop():
                print("  Stop detected")
                return

            btn_down = (self.btn.value() == 0)
            if btn_down:
                self.buz.beep(self.frequency, BEEP_MS)
                self.leds.fill(NOTE_COLORS.get(self.note, WHITE))
            else:
                self.leds.off()

            time.sleep_ms(LOOP_DELAY_MS)
            self._frame += 1


def play(nfc, leds, buz, accel, i2c, enow):
    _play_sound(buz, 'start')
    print("\n  === NFC BELL CHOIR ===")
    try:
        NfcSoundGame(nfc, leds, buz, enow).run()
    finally:
        leds.off()
        print("\n  === RETURNING TO PROGRAMMING MODE ===\n")


def main():
    """
    Standalone entry point for testing without main.py.
    Run directly: import nfc_sound; nfc_sound.main()
    """
    print("\n" + "=" * 45)
    print("  NFC Bell Choir")
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

    from espnow_manager import ESPNowManager
    enow = ESPNowManager()
    enow.init()

    print()
    play(nfc, leds, buz, None, i2c, enow)


if __name__ == "__main__":
    main()
