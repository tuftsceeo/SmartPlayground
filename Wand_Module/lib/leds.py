"""
LED Helpers — NeoPixel control and status display
===================================================
Handles all NeoPixel operations: solid colors, flashing,
pulsing, and programming/running status indicators.

Gesture triggers use LED 3 (shared for all gesture rules)
with a cyan color to indicate "gesture active".

Usage:
    from leds import Leds

    leds = Leds(pin=20, num=25)
    leds.solid(127, 0, 0)
    leds.pulse_color(0, 0, 127, duration_ms=600)
    leds.off()
"""

import math
import time
from neopixel import NeoPixel
import machine

# ─────────────────────────────────────────────
# TRIGGER LED INDICATORS
# Fixed triggers get dedicated LEDs.
# All gesture triggers share LED 3.
# LED 4 = green "ready" indicator.
# ─────────────────────────────────────────────
TRIGGER_ORDER = ["buttondown", "buttonup", "shake"]

TRIGGER_LED = {
    "buttondown": 0,
    "buttonup":   1,
    "shake":      2,
}

TRIGGER_COLOR_BRIGHT = {
    "buttondown": (0, 30, 0),     # red (GRB)
    "buttonup":   (0, 0, 30),     # blue
    "shake":      (0, 20, 20),    # purple
}

TRIGGER_COLOR_DIM = {
    "buttondown": (0, 6, 0),
    "buttonup":   (0, 0, 6),
    "shake":      (0, 4, 4),
}

GESTURE_LED          = 3
GESTURE_COLOR_BRIGHT = (15, 0, 15)   # cyan (GRB)
GESTURE_COLOR_DIM    = (3, 0, 3)

READY_LED   = 4
READY_COLOR = (10, 0, 0)  # green (GRB)


def _is_gesture_trigger(name):
    return name is not None and name.startswith("gesture:")


class Leds:
    def __init__(self, pin, num):
        self.np = NeoPixel(machine.Pin(pin), num)
        self.num = num

    # ── Basic operations ──

    def off(self):
        for i in range(self.num):
            self.np[i] = (0, 0, 0)
        self.np.write()

    def solid(self, r, g, b):
        for i in range(self.num):
            self.np[i] = (r, g, b)
        self.np.write()

    def flash(self, r, g, b, times=2, on_ms=120, off_ms=80):
        for _ in range(times):
            self.solid(r, g, b); time.sleep_ms(on_ms)
            self.off(); time.sleep_ms(off_ms)

    def pulse_color(self, r, g, b, duration_ms=600):
        steps = 20
        for s in range(steps):
            scale = math.sin(math.pi * s / steps)
            self.solid(int(r * scale), int(g * scale), int(b * scale))
            time.sleep_ms(duration_ms // steps)
        self.off()

    # ── Scanning animation ──

    def scan_animate(self, frame):
        center = self.num // 2
        radius = frame % 8
        for i in range(self.num):
            dist = abs(i - center)
            if dist == radius:
                self.np[i] = (15, 10, 20)
            elif dist == max(0, radius - 1):
                self.np[i] = (5, 3, 7)
            else:
                self.np[i] = (0, 0, 0)
        self.np.write()

    def scan_complete(self):
        self.solid(20, 15, 25)
        time.sleep_ms(80)
        self.off()

    # ── Status indicators ──

    def show_programming(self, rules, editing):
        """
        Show rule status on indicator LEDs during programming.
          LED 0-2: fixed triggers (buttondown, buttonup, shake)
          LED 3:   gesture (bright if any gesture rule has actions,
                   dim if currently editing a gesture trigger)
          LED 4:   green if at least one complete rule exists
        """
        for i in range(self.num):
            self.np[i] = (0, 0, 0)

        has_any_rule = False

        # Fixed triggers
        for trig in TRIGGER_ORDER:
            led_idx = TRIGGER_LED[trig]
            if trig in rules and len(rules[trig]) > 0:
                self.np[led_idx] = TRIGGER_COLOR_BRIGHT[trig]
                has_any_rule = True
            elif trig == editing:
                self.np[led_idx] = TRIGGER_COLOR_DIM[trig]

        # Gesture triggers — any gesture:xxx with actions lights LED 3 bright
        any_gesture_complete = False
        editing_gesture = False
        for key in rules:
            if _is_gesture_trigger(key) and len(rules[key]) > 0:
                any_gesture_complete = True
                break

        if _is_gesture_trigger(editing):
            editing_gesture = True

        if any_gesture_complete:
            self.np[GESTURE_LED] = GESTURE_COLOR_BRIGHT
            has_any_rule = True
        elif editing_gesture:
            self.np[GESTURE_LED] = GESTURE_COLOR_DIM

        if has_any_rule:
            self.np[READY_LED] = READY_COLOR

        self.np.write()

    def show_running(self, rules):
        """
        During running: dim color for each active trigger, all others off.
        """
        for i in range(self.num):
            self.np[i] = (0, 0, 0)

        for trig in TRIGGER_ORDER:
            if trig in rules and len(rules[trig]) > 0:
                led_idx = TRIGGER_LED[trig]
                self.np[led_idx] = TRIGGER_COLOR_DIM[trig]

        # Any gesture trigger active?
        for key in rules:
            if _is_gesture_trigger(key) and len(rules[key]) > 0:
                self.np[GESTURE_LED] = GESTURE_COLOR_DIM
                break

        self.np.write()

    # ── Battery display ──

    def show_battery_level(self, soc):
        soc_clamped = max(0, min(100, soc))
        lit = int(soc_clamped / 100 * self.num)

        if soc_clamped > 50:
            r, g, b = 0, 40, 0
        elif soc_clamped > 20:
            r, g, b = 40, 25, 0
        else:
            r, g, b = 40, 0, 0

        for i in range(self.num):
            self.np[i] = (r, g, b) if i < lit else (0, 0, 0)
        self.np.write()

        return r, g, b, lit

    def fade_out_battery(self, r, g, b, lit):
        for step in range(10, -1, -1):
            scale = step / 10
            for i in range(self.num):
                if i < lit:
                    self.np[i] = (int(r * scale), int(g * scale), int(b * scale))
                else:
                    self.np[i] = (0, 0, 0)
            self.np.write()
            time.sleep_ms(40)
        self.off()