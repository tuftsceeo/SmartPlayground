"""
Icon Display Bring-Up — Single-Pixel Sanity Check
=====================================================
Board: Seeed XIAO ESP32-C6, same LED strip expansion board as
Slide Score Station.

Purpose: voltage_test.py's ramp assumes the wiring/data line already
works. If nothing lights up at all, back off to the simplest possible
case first -- one pixel, cycling through obvious colors -- before
blaming voltage. This script has no ramp, no count math, nothing to
misconfigure: just pin, power, one pixel.

If this pixel doesn't light either:
  - Check which connector the strip's DIN is actually plugged into.
    The Seeed LED Driver Board (wiki.seeedstudio.com/led_driver_board)
    has TWO independent data pins: the A0 screw terminal is GPIO0,
    the D5 Grove socket is GPIO23. Wrong connector for the DATA_PIN
    set below looks identical to "nothing works."
  - Check DIN is on the strip's IN end, not OUT (some strips are
    directional and silently do nothing if fed backwards).
  - Check the strip has 5V + GND from the expansion board, not just
    the data wire -- NeoPixels don't light off signal alone.

Wiring: identical to Slide Score Station --
    ESP32-C6 GPIO0 (A0) -- NeoPixel strip DIN (pixel 0 only, for now)

Run from the REPL:
    import single_pixel_test
    single_pixel_test.main()
"""

import machine
import neopixel
import time

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
DATA_PIN  = 0   # GPIO0 = A0 screw terminal on the LED Driver Board (what Slide Score Station uses)
                # GPIO23 = D5 Grove connector on the same board -- try this if A0 stays dark
                # (per https://wiki.seeedstudio.com/led_driver_board/ these are two different pins)
NUM_PIXELS = 1   # just the first pixel on the strip you have on hand right now

COLORS = (
    ("red",   (255, 0, 0)),
    ("green", (0, 255, 0)),
    ("blue",  (0, 0, 255)),
    ("white", (255, 255, 255)),
)
STEP_MS = 800

# ─────────────────────────────────────────────
# HARDWARE
# ─────────────────────────────────────────────
strip = neopixel.NeoPixel(machine.Pin(DATA_PIN), NUM_PIXELS)


def off():
    strip[0] = (0, 0, 0)
    strip.write()


def main():
    print("\n" + "=" * 50)
    print("  Icon Display Bring-Up -- Single-Pixel Sanity Check")
    print("  GPIO%d, 1 pixel, cycling red/green/blue/white" % DATA_PIN)
    print("=" * 50)
    print("  Nothing lighting up at all? See the header comment for")
    print("  wiring/pin checks. Ctrl-C to stop.\n")

    try:
        while True:
            for name, rgb in COLORS:
                strip[0] = rgb
                strip.write()
                print("  pixel 0 -> %s" % name)
                time.sleep_ms(STEP_MS)
    except KeyboardInterrupt:
        print("\n  Stopped.")
    finally:
        off()
        print("  Pixel cleared.")


if __name__ == "__main__":
    main()
