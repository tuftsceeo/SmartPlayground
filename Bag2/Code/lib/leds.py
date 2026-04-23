"""
LED Helpers — NeoPixel control and status display
===================================================
Auto-configures from hubtype. Works on any device.

Usage:
    from leds import Leds
    leds = Leds()           # auto from hubtype
    leds = Leds(pin=21, num=18)  # override
"""

import math
import time
from neopixel import NeoPixel
import machine

from hubtype import HUB_CONFIG

TRIGGER_ORDER = ["buttondown", "buttonup", "shake"]

TRIGGER_LED = {"buttondown": 0, "buttonup": 1, "shake": 2}

TRIGGER_COLOR_BRIGHT = {
    "buttondown": (0, 30, 0),
    "buttonup":   (0, 0, 30),
    "shake":      (0, 20, 20),
}

TRIGGER_COLOR_DIM = {
    "buttondown": (0, 6, 0),
    "buttonup":   (0, 0, 6),
    "shake":      (0, 4, 4),
}

GESTURE_LED          = 3
GESTURE_COLOR_BRIGHT = (15, 0, 15)
GESTURE_COLOR_DIM    = (3, 0, 3)

SC_LED               = 4
SC_COLOR_BRIGHT      = (15, 15, 0)
SC_COLOR_DIM         = (3, 3, 0)

READY_LED   = 5
READY_COLOR = (5, 0, 0)

# Inner 3x3 ring on 5x5 grid (rows 1-3, cols 1-3)
INNER_RING = [6, 7, 8, 11, 12, 13, 16, 17, 18]

# Boot status LED positions (top-left corner: LEDs 0, 1, 2)
BOOT_LED_POWER  = 0
BOOT_LED_BATT   = 1
BOOT_LED_READY  = 2


def _is_gesture(name):
    return name is not None and name.startswith("gesture:")

def _is_sc(name):
    return name is not None and name.startswith("SC:")


def battery_color(soc):
    """Return (r, g, b) for a given state-of-charge percentage."""
    if soc > 75:
        return (0, 5, 0)       # green
    elif soc > 30:
        return (5, 2, 0)      # yellow
    elif soc > 10:
        return (5, 0, 0)       # red
    else:
        return (5, 0, 0)       # red (caller handles flashing for <10%)


class Leds:
    def __init__(self, pin=None, num=None):
        if pin is None:
            pin = HUB_CONFIG.get("led_pin", 20)
        if num is None:
            num = HUB_CONFIG.get("num_leds", 25)
        self.np = NeoPixel(machine.Pin(pin), num)
        self.num = num

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

    def breathe(self, r, g, b, frame):
        brightness = (math.sin(frame * 0.08) + 1) / 2
        self.solid(int(r * brightness), int(g * brightness), int(b * brightness))

    # ══════════════════════════════════════════
    # BOOT SEQUENCE LEDs
    # ══════════════════════════════════════════

    def boot_power(self):
        """
        Step 1: Light LED 0 white immediately on power-up.
        Called before any I2C/NFC/sensor initialization.
        """
        self.np[BOOT_LED_POWER] = (40, 40, 40)  # white
        self.np.write()

    def boot_battery(self, soc):
        """
        Step 2: Show battery level on LEDs 0 and 1.
        Green >75%, yellow 30-75%, red 10-30%, flashing red <10%.
        For <10%: blinks 5 times (0.1s on, 0.1s off) then stays solid.
        """
        color = battery_color(soc)

        if soc <= 10:
            # Flash red 5 times
            for _ in range(5):
                self.np[BOOT_LED_POWER] = color
                self.np[BOOT_LED_BATT] = color
                self.np.write()
                time.sleep_ms(100)
                self.np[BOOT_LED_POWER] = (0, 0, 0)
                self.np[BOOT_LED_BATT] = (0, 0, 0)
                self.np.write()
                time.sleep_ms(100)

        # Settle to solid
        self.np[BOOT_LED_POWER] = color
        self.np[BOOT_LED_BATT] = color
        self.np.write()

    def boot_ready(self, soc):
        """
        Step 3: All init complete — light LED 2 in same battery color.
        """
        color = battery_color(soc)
        self.np[BOOT_LED_READY] = color
        self.np.write()

    def boot_clear(self):
        """Clear boot LEDs (0, 1, 2) before entering idle mode."""
        self.np[BOOT_LED_POWER] = (0, 0, 0)
        self.np[BOOT_LED_BATT] = (0, 0, 0)
        self.np[BOOT_LED_READY] = (0, 0, 0)
        self.np.write()

    # ══════════════════════════════════════════
    # IDLE — battery-colored inner ring
    # ══════════════════════════════════════════

    def idle_default(self, soc):
        """
        Default idle: inner 3x3 ring lit with battery charge color.
        Static — no pulsing, no breathing.
        If battery <10%, center LED blinks red (call idle_low_blink instead).
        """
        color = battery_color(soc)
        for i in range(self.num):
            if i in INNER_RING:
                self.np[i] = color
            else:
                self.np[i] = (0, 0, 0)
        self.np.write()

    def idle_low_blink(self, frame):
        """
        Battery <10% idle: center LED (12) blinks red.
        All other LEDs off. Toggle every ~5 frames (~1s at 200ms loop).
        """
        center = self.num // 2  # LED 12
        on = ((frame // 5) % 2) == 0
        for i in range(self.num):
            if i == center and on:
                self.np[i] = (40, 0, 0)  # red
            else:
                self.np[i] = (0, 0, 0)
        self.np.write()

    def idle_sleep(self):
        """
        NFC sleeping (30s idle): single static blue dot on center LED.
        No breathing, no pulsing — just a steady blue indicator.
        """
        center = self.num // 2  # LED 12
        for i in range(self.num):
            if i == center:
                self.np[i] = (0, 0, 5)  # dim blue
            else:
                self.np[i] = (0, 0, 0)
        self.np.write()

    # ══════════════════════════════════════════
    # LEGACY IDLE (kept for reference, no longer default)
    # ══════════════════════════════════════════

    def breathe_idle(self, frame):
        """
        Soft breathing glow across all LEDs to show the wand is on.
        Very dim purple-white tint — visible but not blinding.
        """
        phase = (math.sin(frame * 0.06) + 1) / 2  # 0..1
        level = 2 + int(6 * phase)  # range 2..8
        r = level
        g = int(level * 0.6)
        b = level
        for i in range(self.num):
            self.np[i] = (r, g, b)
        self.np.write()

    def breathe_sleep(self, frame):
        """
        Even dimmer single-pixel breathing — NFC is sleeping.
        Only center LED breathes, minimal power draw.
        """
        phase = (math.sin(frame * 0.04) + 1) / 2
        level = 1 + int(4 * phase)  # range 1..5
        center = self.num // 2
        for i in range(self.num):
            if i == center:
                self.np[i] = (0, 0, level)
            else:
                self.np[i] = (0, 0, 0)
        self.np.write()

    # ── Scanning (wand) ──

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

    # ── Programming indicators (wand, needs >=6 LEDs) ──

    def show_programming(self, rules, editing):
        for i in range(self.num):
            self.np[i] = (0, 0, 0)
        if self.num < 6:
            self.np.write(); return

        has_any = False
        for trig in TRIGGER_ORDER:
            idx = TRIGGER_LED[trig]
            if trig in rules and len(rules[trig]) > 0:
                self.np[idx] = TRIGGER_COLOR_BRIGHT[trig]
                has_any = True
            elif trig == editing:
                self.np[idx] = TRIGGER_COLOR_DIM[trig]

        if GESTURE_LED < self.num:
            gc = False
            for k in rules:
                if _is_gesture(k) and len(rules[k]) > 0:
                    gc = True; break
            if gc:
                self.np[GESTURE_LED] = GESTURE_COLOR_BRIGHT
                has_any = True
            elif _is_gesture(editing):
                self.np[GESTURE_LED] = GESTURE_COLOR_DIM

        if SC_LED < self.num:
            sc = False
            for k in rules:
                if _is_sc(k) and len(rules[k]) > 0:
                    sc = True; break
            if sc:
                self.np[SC_LED] = SC_COLOR_BRIGHT
                has_any = True
            elif _is_sc(editing):
                self.np[SC_LED] = SC_COLOR_DIM

        if has_any and READY_LED < self.num:
            self.np[READY_LED] = READY_COLOR
        self.np.write()

    def show_running(self, rules):
        for i in range(self.num):
            self.np[i] = (0, 0, 0)
        for trig in TRIGGER_ORDER:
            if trig in rules and len(rules[trig]) > 0:
                idx = TRIGGER_LED[trig]
                if idx < self.num:
                    self.np[idx] = TRIGGER_COLOR_DIM[trig]
        if GESTURE_LED < self.num:
            for k in rules:
                if _is_gesture(k) and len(rules[k]) > 0:
                    self.np[GESTURE_LED] = GESTURE_COLOR_DIM; break
        if SC_LED < self.num:
            for k in rules:
                if _is_sc(k) and len(rules[k]) > 0:
                    self.np[SC_LED] = SC_COLOR_DIM; break
        self.np.write()

    # ── Battery (adaptive) ──

    def show_battery_level(self, soc):
        soc_c = max(0, min(100, soc))
        lit = max(1, int(soc_c / 100 * self.num))
        if soc_c > 50:
            r, g, b = 0, 40, 0
        elif soc_c > 20:
            r, g, b = 40, 25, 0
        else:
            r, g, b = 40, 0, 0
        for i in range(self.num):
            self.np[i] = (r, g, b) if i < lit else (0, 0, 0)
        self.np.write()
        return r, g, b, lit

    def fade_out_battery(self, r, g, b, lit):
        for step in range(10, -1, -1):
            sc = step / 10
            for i in range(self.num):
                if i < lit:
                    self.np[i] = (int(r * sc), int(g * sc), int(b * sc))
                else:
                    self.np[i] = (0, 0, 0)
            self.np.write()
            time.sleep_ms(40)
        self.off()