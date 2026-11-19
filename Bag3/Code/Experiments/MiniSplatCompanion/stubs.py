"""
stubs.py -- stand-ins for the wand hardware the Mini Splat Companion lacks
===========================================================================
Wand-contract games are called play(nfc, leds, buz, accel, i2c, enow, batt,
net). The mini has no NFC reader, buzzer or accelerometer, so main.py passes
these instead. Every method a game may call is a harmless no-op; a game that
needs the real thing simply sees nothing happen (no tag, no motion).
"""

import time


class _Null:
    def __getattr__(self, name):
        return self._noop

    def _noop(self, *args, **kwargs):
        return None


class NullBuzzer(_Null):
    def beep(self, freq=0, ms=0):
        # Keep the game's timing: a beep is a wait of ms.
        if ms:
            time.sleep_ms(ms)


class NullNfc(_Null):
    def read_passive_target(self, *args, **kwargs):
        return None

    def detect_tag(self, *args, **kwargs):
        return None, None


class NullAccel(_Null):
    def read(self):
        return (0.0, 0.0, 1.0)     # at rest, 1 g on z
