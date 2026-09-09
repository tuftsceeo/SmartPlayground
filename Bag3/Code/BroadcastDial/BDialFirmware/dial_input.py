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

NEXT = "next"
PREV = "prev"
ACT = "act"
BACK = "back"
EXIT = "exit"


class DialInput:
    def __init__(self):
        self._queue = []
        self._rotary = None
        self._last_rotary = 0
        self._btn_pressed_at = 0
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
        """LVGL callbacks post intents here; never mutate server state."""
        if intent:
            self._queue.append(intent)

    def update(self):
        """Advance M5 + encoder + button. Call once per main-loop iteration."""
        M5.update()
        self._poll_encoder()
        self._poll_button()

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
        if down and not self._btn_was_down:
            self._btn_pressed_at = now
            self._exit_emitted = False
        if down:
            held = time.ticks_diff(now, self._btn_pressed_at)
            if held >= SERVE_EXIT_MS and not self._exit_emitted:
                self._queue.append(EXIT)
                self._exit_emitted = True
        elif self._btn_was_down:
            # Release: short press is ACT unless a hold already emitted EXIT.
            if not self._exit_emitted:
                self._queue.append(ACT)
        self._btn_was_down = down

    def clear(self):
        """Drop pending intents and restart the hold clock.

        Call on every mode change so a hold that caused the switch does not
        immediately read as a hold (or an ACT on release) in the new mode.
        """
        self._queue = []
        self._btn_pressed_at = time.ticks_ms()
        try:
            self._btn_was_down = M5.BtnA.isPressed()
        except Exception:
            self._btn_was_down = False
        self._exit_emitted = False

    def pop(self):
        """Next intent, or None. Non-blocking."""
        if self._queue:
            return self._queue.pop(0)
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
