"""dial_input.py — encoder + button + touch -> one non-blocking intent queue.

Replaces buttons.py. The server never cares which source produced an intent;
LVGL touch callbacks only enqueue, and the server drains from its own loop
so mode-transition reasoning stays single-threaded.

Intents:
    NEXT  encoder CW, or a touch on the next control
    PREV  encoder CCW
    ACT   short button click, or a tap on the focused / primary control
    BACK  tap on CANCEL / CLOSE / back control
    EXIT  button held SERVE_EXIT_MS, or a tap on the SERVE screen's CLOSE
"""

import time

import M5

# Mirror bbox_server.SERVE_EXIT_MS — leaving SERVE must not fire from a bump.
SERVE_EXIT_MS = 1000

# A fast flick can produce a large delta; cap so one update cannot skip the
# whole list. Dial_Music.py discarded magnitude entirely — we honour it.
ENCODER_CAP = 8

# Most time one poll gap may add to a hold (ms). A long gap means the loop
# was blocked (LVGL redraws inside M5.update()), not that the button was
# watched down for that long; counting it turned short clicks into holds.
# NFC Station addition.
MAX_POLL_GAP_MS = 100

# A press released after this long but before SERVE_EXIT_MS is a failed
# hold and emits nothing (not ACT). station_ui shows the hold ring from
# the same point, so "ring visible" means "this will not be a click".
# NFC Station addition.
HOLD_MAYBE_MS = 500

# Screen taps within this long of a knob turn or button activity (before or
# after) are dropped: a thumb on the button or knob brushes the touch panel.
# Taps are held this long before they are accepted. NFC Station addition.
TAP_GUARD_MS = 200

NEXT = "next"
PREV = "prev"
ACT = "act"
BACK = "back"
EXIT = "exit"


class DialInput:
    def __init__(self):
        self._queue = []
        self._taps = []             # (tap intent, ticks) awaiting TAP_GUARD_MS
        self._physical_at = -100000
        self._rotary = None
        self._last_rotary = 0
        self._btn_pressed_at = 0
        self._held_ms = 0
        self._pending_ms = 0
        self._last_poll = 0
        self._btn_was_down = False
        self._exit_emitted = False

    def begin(self):
        """Call once after M5.begin() — Rotary needs the vendor bring-up."""
        from hardware import Rotary
        self._rotary = Rotary()
        try:
            self._rotary.reset_rotary_value()
        except Exception as e:
            print("# rotary reset err: %s" % str(e))
        self._last_rotary = 0
        try:
            self._last_rotary = self._rotary.get_rotary_value()
        except Exception:
            pass

    def enqueue(self, intent):
        """LVGL callbacks post intents here; never mutate server state.

        Screen taps ("tap:<i>") are held TAP_GUARD_MS and dropped if a knob
        turn or button activity falls within TAP_GUARD_MS of them.
        """
        if not intent:
            return
        if intent.startswith("tap:"):
            self._taps.append((intent, time.ticks_ms()))
        else:
            self._queue.append(intent)

    def update(self):
        """Advance M5 + encoder + button. Call once per main-loop iteration."""
        M5.update()
        self._poll_encoder()
        self._poll_button()
        self._release_taps()

    def _mark_physical(self):
        self._physical_at = time.ticks_ms()

    def _release_taps(self):
        if not self._taps:
            return
        now = time.ticks_ms()
        keep = []
        for intent, t in self._taps:
            if abs(time.ticks_diff(t, self._physical_at)) <= TAP_GUARD_MS:
                continue                    # brushed while turning/pressing
            if time.ticks_diff(now, t) >= TAP_GUARD_MS:
                self._queue.append(intent)
            else:
                keep.append((intent, t))
        self._taps = keep

    def _poll_encoder(self):
        if self._rotary is None:
            return
        try:
            if not self._rotary.get_rotary_status():
                return
            new_val = self._rotary.get_rotary_value()
        except Exception as e:
            print("# rotary err: %s" % str(e))
            return
        delta = new_val - self._last_rotary
        self._last_rotary = new_val
        if delta == 0:
            return
        self._mark_physical()
        n = abs(delta)
        if n > ENCODER_CAP:
            n = ENCODER_CAP
        intent = NEXT if delta > 0 else PREV
        for _ in range(n):
            self._queue.append(intent)

    def _poll_button(self):
        # Encoder press is BtnA on Dial family hardware (Dial_Music.py).
        # If Phase 0 finds a distinct side button, H6 may add BtnB as BACK.
        try:
            down = M5.BtnA.isPressed()
        except Exception as e:
            raise RuntimeError("M5.BtnA unavailable: %s" % str(e))
        now = time.ticks_ms()
        if down or self._btn_was_down:
            self._mark_physical()       # pressed, held, or just released
        if down and not self._btn_was_down:
            self._btn_pressed_at = now
            self._held_ms = 0
            self._pending_ms = 0
            self._exit_emitted = False
        elif down:
            gap = time.ticks_diff(now, self._last_poll)
            # Credit a long gap only once a later poll confirms the button
            # is still down: right after a blocking call the sample can be
            # stale (a click already released), but a real hold through a
            # blocking NFC read must still reach SERVE_EXIT_MS.
            self._held_ms += min(gap, MAX_POLL_GAP_MS) + self._pending_ms
            self._pending_ms = max(gap - MAX_POLL_GAP_MS, 0)
        else:
            self._pending_ms = 0
        self._last_poll = now
        if down:
            held = self._held_ms
            if held >= SERVE_EXIT_MS and not self._exit_emitted:
                self._queue.append(EXIT)
                self._exit_emitted = True
        elif self._btn_was_down:
            # Release: a short press is ACT. Nothing if a hold already
            # emitted EXIT, or the press reached HOLD_MAYBE_MS (failed hold).
            if not self._exit_emitted and self._held_ms < HOLD_MAYBE_MS:
                self._queue.append(ACT)
        self._btn_was_down = down

    def clear(self):
        """Drop pending intents and restart the hold clock.

        Call on every mode change so a hold that caused the switch does not
        immediately read as a hold (or an ACT on release) in the new mode.
        A press still held here is marked spent: its release, however long
        after, emits nothing. (NFC Station fix; BroadcastDial's copy resets
        the flag to False, so the release of a hold that changed screens
        reads as an ACT there.)
        """
        self._queue = []
        self._taps = []
        self._btn_pressed_at = time.ticks_ms()
        self._held_ms = 0
        self._pending_ms = 0
        self._last_poll = self._btn_pressed_at
        try:
            self._btn_was_down = M5.BtnA.isPressed()
        except Exception:
            self._btn_was_down = False
        self._exit_emitted = self._btn_was_down

    def pop(self):
        """Next intent, or None. Non-blocking."""
        if self._queue:
            return self._queue.pop(0)
        return None

    def hold_fraction(self):
        """0.0-1.0 progress of the current press toward EXIT, or None when
        the button is up or EXIT has already fired. NFC Station addition;
        not in BroadcastDial's copy."""
        if not self._btn_was_down or self._exit_emitted:
            return None
        return min(self._held_ms / SERVE_EXIT_MS, 1.0)

    def peek(self):
        """Next intent without removing it, or None. NFC Station addition."""
        if self._queue:
            return self._queue[0]
        return None

    def peek_exit(self):
        """True if an EXIT is pending (does not consume). For should_abort."""
        return EXIT in self._queue

    def take(self, intent):
        """Remove the first matching intent if present. Returns True if removed."""
        try:
            i = self._queue.index(intent)
        except ValueError:
            return False
        self._queue.pop(i)
        return True
