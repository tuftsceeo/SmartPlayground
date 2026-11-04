"""
power_led.py — discrete power-status LED (Bag3)
================================================
Bag3 adds a single status LED wired to a GPIO (default Pin 2) that
indicates the board is powered. It is independent of the 6×10 NeoPixel
matrix.

Behavior:
    • Solid ON whenever the board is running and the battery is healthy.
    • ~1 Hz blink when the battery state-of-charge is low, so a dying
      battery is obvious at a glance even when the matrix is off/asleep.

Usage:
    from power_led import PowerLed
    pled = PowerLed()        # auto from hubtype (power_led_pin)
    pled.on()                # solid at boot

    # In the idle/event loop, once per frame:
    pled.update(soc=last_soc, frame=idle_frame)

If the configured hub has no power LED (has_power_led falsy / no pin),
PowerLed becomes a no-op so the same code runs on every device.
"""

import machine
from hubtype import HUB_CONFIG

# SOC (%) at/below which the LED blinks instead of holding solid.
LOW_SOC = 10
# Loop frames per blink half-cycle. At a ~200ms idle loop this is ~1 Hz.
_BLINK_FRAMES = 5


class PowerLed:
    def __init__(self, pin=None):
        if pin is None:
            pin = HUB_CONFIG.get("power_led_pin")
        # Treat a missing pin (or has_power_led False) as "no LED present".
        self._enabled = pin is not None and HUB_CONFIG.get("has_power_led", False)
        self._pin = machine.Pin(pin, machine.Pin.OUT, value=0) if self._enabled else None
        self._state = 0

    def _set(self, value):
        if self._pin is not None:
            self._pin.value(value)
            self._state = value

    def on(self):
        """Hold the LED solid on (board powered, battery healthy)."""
        self._set(1)

    def off(self):
        """Turn the LED off (e.g. on shutdown)."""
        self._set(0)

    def update(self, soc=100, frame=0):
        """
        Refresh the LED for one loop iteration.

        soc:   latest battery state-of-charge percentage.
        frame: a monotonically increasing loop counter (drives the blink).

        Solid on when soc > LOW_SOC; blinks ~1 Hz at or below it.
        """
        if not self._enabled:
            return
        if soc > LOW_SOC:
            self._set(1)
        else:
            self._set(1 if (frame // _BLINK_FRAMES) % 2 == 0 else 0)
