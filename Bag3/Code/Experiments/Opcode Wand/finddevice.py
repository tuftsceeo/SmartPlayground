"""
Find Device — hidden identify animation (ESP-NOW targeted only).

Triggered when the teacher clicks this wand in a device list. The hub/remote
broadcasts {"type":"start_game","name":"finddevice","mac":<this wand's MAC>};
espnow_manager.poll() delivers it only to the matching wand, which runs this.

Shows an obvious rainbow asterisk and beeps so the wand can be picked out of a
pile. Stops after 5 seconds, or when the wand button is pressed, or on any
stop/start_game. Not an NFC game — listed in game_tags.HIDDEN_TAGS only.

Standard game shape: play(nfc, leds, buz, accel, i2c, enow).
"""

import time
from machine import Pin

from leds import (
    RED, ORANGE, YELLOW, GREEN, CYAN, BLUE, PURPLE, MAGENTA, OFF, SHAPE_STAR,
)

BUTTON_PIN = 0          # active-low (PULL_UP); 0 == pressed
DURATION_MS = 5000      # auto-stop after 5 s
FRAME_MS = 60
BEEP_EVERY_FRAMES = 12  # ~ every 0.72 s
BEEP_FREQ = 1500
BEEP_MS = 60

_RAINBOW = (RED, ORANGE, YELLOW, GREEN, CYAN, BLUE, PURPLE, MAGENTA)


def play(nfc, leds, buz, accel, i2c, enow):
    print("\n  === FIND DEVICE (identify) ===")
    btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
    btn_was_down = (btn.value() == 0)
    try:
        if buz:
            buz.confirm()
        start = time.ticks_ms()
        frame = 0
        while time.ticks_diff(time.ticks_ms(), start) < DURATION_MS:
            # Exit on ESP-NOW stop / another start_game (force-switch).
            if enow:
                msg_type, _, _ = enow.poll()
                if msg_type in ("stop", "start_game"):
                    print("  Find: interrupted by %s" % msg_type)
                    return

            # Exit on a fresh button press.
            down = (btn.value() == 0)
            if down and not btn_was_down:
                print("  Find: stopped by button")
                return
            btn_was_down = down

            leds.show_shape(SHAPE_STAR, _RAINBOW[frame % len(_RAINBOW)])
            if buz and frame % BEEP_EVERY_FRAMES == 0:
                buz.beep(BEEP_FREQ, BEEP_MS)

            time.sleep_ms(FRAME_MS)
            frame += 1
        print("  Find: done (5s)")
    finally:
        # Beeps are one-shot (PWM deinits after each), so nothing to silence;
        # just clear the LEDs on the way out.
        leds.off()
        print("  === RETURNING TO PROGRAMMING MODE ===\n")


def main():
    """Standalone bench test: run the identify animation once."""
    import machine
    from leds import Leds
    from buzzer import Buzzer
    from espnow_manager import ESPNowManager

    leds = Leds()
    buz = Buzzer(19)
    enow = ESPNowManager()
    try:
        enow.init()
    except Exception:
        enow = None
    play(None, leds, buz, None, None, enow)


if __name__ == "__main__":
    main()
