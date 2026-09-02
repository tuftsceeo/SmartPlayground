"""
buttons.py — B1/B2 edge + hold timing for the Box's two side buttons.

Supersedes the ad-hoc NFC_TRIGGER_PIN Pin object in bbox_server.py: B1 is
the write/confirm/scan button (StickS3 "Key1", G11), B2 is scroll ("Key2",
G12). Both are momentary, active-low against an internal pull-up.

Usage: call update() once per main loop iteration; b1_down()/b1_held_ms()/
b2_pressed() then read the debounced state as of that call. Call clear() on
a mode change so a latched edge or an in-progress hold does not carry over.
"""

import time
import machine

B1_PIN = 11  # G11 "Key1" -- scan / write / confirm
B2_PIN = 12  # G12 "Key2" -- scroll

DEBOUNCE_MS = 20


class Buttons:
    def __init__(self, b1_pin=B1_PIN, b2_pin=B2_PIN):
        self._available = False
        self._b1 = None
        self._b2 = None
        try:
            self._b1 = machine.Pin(b1_pin, machine.Pin.IN, machine.Pin.PULL_UP)
            self._b2 = machine.Pin(b2_pin, machine.Pin.IN, machine.Pin.PULL_UP)
            self._available = True
        except Exception as e:
            print("# Buttons init failed (pins %d/%d): %s" % (b1_pin, b2_pin, str(e)))
            self._b1 = None
            self._b2 = None
            self._available = False

        # Debounced state, updated only in update().
        self._b1_down = False
        self._b1_raw_down = False
        self._b1_raw_since = 0
        self._b1_pressed_at = 0

        self._b2_raw_down = False
        self._b2_raw_since = 0
        self._b2_down = False
        self._b2_edge = False  # one-shot rising-edge flag, cleared on read

    def available(self):
        """False if Pin construction failed.

        Accessors then report False rather than guessing. Deciding what to do
        about absent buttons is the caller's: bbox_server treats
        available() == False as "B1 held" so a box with dead side keys can
        still write cards.
        """
        return self._available

    def clear(self):
        """Drop any latched B2 edge and restart B1's hold clock.

        Call on every mode change. b2_pressed() latches in update() and is
        only cleared by a read, so a press made while B2 is unused (SERVE
        mode) would otherwise fire as a stale scroll on the next entry to
        WRITE. Same for a B1 hold that began in the previous mode: the hold
        that triggered the mode change must not immediately count as a hold
        in the new one.
        """
        self._b2_edge = False
        self._b1_pressed_at = time.ticks_ms()

    def update(self):
        """Sample both pins and advance debounced edge/hold state. Call once
        per main loop iteration."""
        if not self._available:
            return
        now = time.ticks_ms()
        self._update_b1(now)
        self._update_b2(now)

    def _update_b1(self, now):
        raw = self._b1.value() == 0  # active-low against pull-up
        if raw != self._b1_raw_down:
            self._b1_raw_down = raw
            self._b1_raw_since = now
        elif time.ticks_diff(now, self._b1_raw_since) >= DEBOUNCE_MS:
            if raw and not self._b1_down:
                self._b1_pressed_at = now
            self._b1_down = raw

    def _update_b2(self, now):
        raw = self._b2.value() == 0  # active-low against pull-up
        if raw != self._b2_raw_down:
            self._b2_raw_down = raw
            self._b2_raw_since = now
        elif time.ticks_diff(now, self._b2_raw_since) >= DEBOUNCE_MS:
            if raw and not self._b2_down:
                self._b2_edge = True  # latch; cleared by b2_pressed()
            self._b2_down = raw

    def b1_down(self):
        """Debounced level: True while B1 is held down."""
        if not self._available:
            return False
        return self._b1_down

    def b1_held_ms(self):
        """Milliseconds since the debounced B1 press edge; 0 when up."""
        if not self._available or not self._b1_down:
            return 0
        return time.ticks_diff(time.ticks_ms(), self._b1_pressed_at)

    def b2_pressed(self):
        """One-shot rising edge on B2: True at most once per physical press,
        cleared on read."""
        if not self._available:
            return False
        if self._b2_edge:
            self._b2_edge = False
            return True
        return False
