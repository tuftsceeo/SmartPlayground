"""
power_led.py — discrete power/status LED on GPIO 2 (Bag3 wand).

Plain digital pin until start(), which runs after radio bring-up and light
calibration: it switches to PWM, scales to brightness.MULTIPLIER and steps
patterns from a 100 ms timer. No-op when the hub has no power LED.
"""

import machine
import brightness
from hubtype import HUB_CONFIG

# Full scale follows brightness.MULTIPLIER (diffuser gain removed): LED_FLOOR
# at MIN_MULT (indoor) up to 1.0 at MAX_MULT (sunlight).
LED_FLOOR = 0.03
READY = 0.8
DIM = 0.5
LOW_SOC = 20
CRITICAL_SOC = 10

# Levels (fraction of full scale) per 100 ms step.
_ON = (READY,)
_OFF = (0,)
_ASLEEP = (DIM,) + (0,) * 39                          # blip every 4 s
_LOW = (READY, 0, READY) + (0,) * 17                  # double blip every 2 s
_CRITICAL = (READY, READY, 0, 0)                      # 2.5 Hz
_FAIL = (1, 1, 1, 1, 1, 0, 0, 1, 0, 0) + (0,) * 6     # long-short


class PowerLed:
    def __init__(self, pin=None):
        if pin is None:
            pin = HUB_CONFIG.get("power_led_pin")
        self._enabled = pin is not None and HUB_CONFIG.get("has_power_led", False)
        self._pin = machine.Pin(pin, machine.Pin.OUT, value=0) if self._enabled else None
        self._pwm = None
        self._full = 65535
        self._mult = None
        self._pat = _ON
        self._step = 0

    def on(self):
        if self._pin is not None and self._pwm is None:
            self._pin.value(1)

    def start(self):
        if self._pin is None or self._pwm is not None:
            return
        self._pwm = machine.PWM(self._pin, freq=1000, duty_u16=0)
        self._follow()
        self._show(_ON)
        machine.Timer(0).init(period=100, callback=self._tick)

    def _follow(self):
        # Re-scale when brightness.MULTIPLIER changed (boot or a game's calibrate).
        m = brightness.MULTIPLIER
        if m == self._mult:
            return
        self._mult = m
        lo, hi = brightness.MIN_MULT, brightness.MAX_MULT
        t = (m / brightness.GAIN - lo) / (hi - lo) if hi > lo else 1
        t = 0 if t < 0 else (1 if t > 1 else t)
        self._full = int(65535 * (LED_FLOOR + t * (1 - LED_FLOOR)))
        if self._pat is not None:
            self._write(self._pat[self._step])

    def _show(self, pat):
        if pat is not self._pat:
            self._pat = pat
            self._step = 0
            self._write(pat[0])

    def _write(self, level):
        if self._pwm is not None:
            self._pwm.duty_u16(int(self._full * level))

    def _tick(self, _t):
        pat = self._pat
        if pat is not None and len(pat) > 1:
            self._step = (self._step + 1) % len(pat)
            self._write(pat[self._step])

    def _battery(self, soc, normal):
        if soc <= CRITICAL_SOC:
            return _CRITICAL
        if soc <= LOW_SOC:
            return _LOW
        return normal

    def idle(self, soc=100):
        self._follow()
        self._show(self._battery(soc, _ON))

    def asleep(self, soc=100):
        self._follow()
        self._show(self._battery(soc, _ASLEEP))

    def game(self):
        self._show(_OFF)

    def boot_fail(self):
        self._show(_FAIL)

    def flicker(self):
        # One step of radio-activity flicker; call repeatedly (e.g. per chunk).
        self._pat = None
        self._write(DIM if self._step else 0)
        self._step ^= 1

    def off(self):
        self._show(_OFF)
        if self._pwm is None and self._pin is not None:
            self._pin.value(0)
