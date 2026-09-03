"""
buttons.py — B1/B2 via the M5Unified BtnA/BtnB objects.

Confirmed on hardware 2026-09-02: this unit has exactly two physical
buttons. The large front button is BtnA -- B1: write / confirm / scan.
The small side button is BtnB -- B2: scroll. Both are read straight from
the vendor's M5.BtnA / M5.BtnB objects, which already debounce -- this
module does not touch raw GPIO and there is no fallback path. If M5.BtnA
or M5.BtnB is unavailable this raises instead of degrading quietly; a
prototype is easier to debug when a broken input is a loud crash, not a
mode nobody can see.

Usage: call update() once per main loop iteration (this is what advances
M5's own button state via M5.update()); b1_down()/b1_held_ms()/b2_pressed()
then read that state. Call clear() on a mode change so a hold that caused
the switch does not immediately read as a hold in the new mode.
"""

import time
import M5


class Buttons:
    def __init__(self):
        self._b1_pressed_at = 0
        self._b1_was_down = False

    def update(self):
        """Advance M5's button state. Call once per main loop iteration."""
        M5.update()
        down = M5.BtnA.isPressed()
        if down and not self._b1_was_down:
            self._b1_pressed_at = time.ticks_ms()
        self._b1_was_down = down

    def clear(self):
        """Restart B1's hold clock. Call on every mode change."""
        self._b1_pressed_at = time.ticks_ms()
        self._b1_was_down = M5.BtnA.isPressed()

    def b1_down(self):
        """True while B1 (BtnA) is held down."""
        return M5.BtnA.isPressed()

    def b1_held_ms(self):
        """Milliseconds since B1 was pressed; 0 when up."""
        if not M5.BtnA.isPressed():
            return 0
        return time.ticks_diff(time.ticks_ms(), self._b1_pressed_at)

    def b2_pressed(self):
        """One-shot: True on the update() cycle B2 (BtnB) was pressed."""
        return M5.BtnB.wasPressed()
