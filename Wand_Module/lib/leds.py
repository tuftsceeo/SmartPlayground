"""
LED Helpers — NeoPixel control and status display
===================================================
Handles all NeoPixel operations: solid colors, flashing,
pulsing, and programming/running status indicators.

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
# Each trigger gets a dedicated LED + color identity
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

READY_LED   = 3
READY_COLOR = (10, 0, 0)  # green (GRB)


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
        """
        Call repeatedly during tag scanning.
        Radiates outward from center LED in white/cyan.
        frame should increment each call.
        """
        center = self.num // 2
        radius = frame % 8
        for i in range(self.num):
            dist = abs(i - center)
            if dist == radius:
                self.np[i] = (15, 10, 20)   # cyan-white (GRB)
            elif dist == max(0, radius - 1):
                self.np[i] = (5, 3, 7)      # dim trail
            else:
                self.np[i] = (0, 0, 0)
        self.np.write()

    def scan_complete(self):
        """Brief bright flash to signal scan finished."""
        self.solid(20, 15, 25)  # bright cyan-white
        import time
        time.sleep_ms(80)
        self.off()

    # ── Status indicators ──

    def show_programming(self, rules, editing):
        """
        Show rule status on indicator LEDs during programming.
          LED 0-2: one per trigger type
            - bright = rule has actions
            - dim = currently editing (no actions yet)
            - off = no rule
          LED 3: green if at least one complete rule exists
        """
        for i in range(self.num):
            self.np[i] = (0, 0, 0)

        has_any_rule = False
        for trig in TRIGGER_ORDER:
            led_idx = TRIGGER_LED[trig]
            if trig in rules and len(rules[trig]) > 0:
                self.np[led_idx] = TRIGGER_COLOR_BRIGHT[trig]
                has_any_rule = True
            elif trig == editing:
                self.np[led_idx] = TRIGGER_COLOR_DIM[trig]

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

        self.np.write()

    # ── Battery display ──

    def show_battery_level(self, soc):
        """
        Fill LEDs proportional to state of charge.
        Returns (r, g, b, lit) for fade-out use.
        """
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
        """Fade out battery display."""
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