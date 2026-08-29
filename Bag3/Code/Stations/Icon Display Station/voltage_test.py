"""
Icon Display Bring-Up — LED Count vs. Voltage Sag Test
=========================================================
Board: Seeed XIAO ESP32-C6, same LED strip expansion board as
Slide Score Station.

Purpose: before wiring up the real 16x16 (256-pixel) icon matrix,
find how many pixels can be driven at 50% intensity before the strip
runs out of headroom -- dimming, color shift (usually a green/red
tint on the far pixels first), or flicker/reset as the 5V rail sags.

This is a standalone bring-up diagnostic, not a station. It does not
touch hubtype.py or espnow_manager, and is not meant to be left
installed as main.py -- copy it up temporarily, run it, then remove it.

Wiring: identical to Slide Score Station --
    ESP32-C6 GPIO0 (A0) -- NeoPixel matrix DIN

Probing voltage: this board has no onboard fuel gauge (score_board
hubtype has has_battery=False, unlike the wand's MAX17048), so this
script does not measure voltage on its own by default. Either:
  (a) probe the 5V/DIN rail with a multimeter while the ramp holds at
      each step (the printed count + hold window is the cue), or
  (b) wire a resistor divider from 5V into an ADC-capable pin and set
      HAS_ADC_PROBE = True + ADC_PIN below for it to log automatically.

Known scale difference vs. Slide Score Station: that station drives a
BTF-LIGHTING WS2812B "Pebble Pixel" seed string, 40px (~2.4A @ 100%
white worst case). This matrix is a BTF-LIGHTING WS2812B 5050 SMD
16x16, 256px (~15.4A @ 100% white, ~7.7A @ this script's 50% level) --
~6x the load on the same driver board. That board (wiki.seeedstudio.com/
led_driver_board) is itself only rated 5V/3A on its output terminal,
independent of the wall adapter feeding it -- ~100px at 50% intensity
is roughly where that rating alone runs out, well before all 256.
Ramp degrading before reaching the end is expected from a single feed
point; a second 5V injection point partway down the matrix is the
standard fix if the full 256 needs to run at once.

Measured 2026-08-25 (known-good driver board, single feed point):
    7 rows (112px) lit safely @ 50% white (~3.36A)
    8 rows (128px) fails                 (~3.84A)
This brackets the board's rated 5V/3A output almost exactly -- treat
~7 rows @ 50% through a single feed as this board's real ceiling, not
a bug to chase further. To run the full 256px at once, either drop
intensity to ~22% (same current budget, all pixels) or add a second
5V injection point around row 8 wired directly from the supply
(bypassing the driver board's own terminal) instead of raising the
feed-point limit.

Run from the REPL:
    import voltage_test
    voltage_test.main()          # full ramp, 16 pixels at a time
    voltage_test.hold(120)       # jump straight to 120 lit, hold for probing
"""

import machine
import neopixel
import time

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
DATA_PIN    = 0     # GPIO0 = A0 screw terminal on the LED Driver Board (same as Slide Score Station)
                     # GPIO23 = D5 Grove connector on the same board -- different physical pin,
                     # see https://wiki.seeedstudio.com/led_driver_board/
NUM_PIXELS  = 256    # 16x16 matrix
STEP        = 16     # ramp one "row" at a time
HOLD_MS     = 4000    # time to hold each step for a multimeter/eyeball read
INTENSITY   = 0.5     # 50% -- the level under test

# Rows cycle through this instead of solid white -- most real icon
# colors only light 1-2 channels near-full, not all three, so this is
# a more realistic load than the white worst-case test. Same 6-color
# rotation as Slide Score Station's RAINBOW_ROWS.
RAINBOW_ROWS = [
    (255, 0, 0), (255, 100, 0), (200, 200, 0),
    (0, 255, 0), (0, 0, 255), (130, 0, 255),
]

# Rule-of-thumb: WS2812-style pixels draw ~20mA per channel at full
# (255) grayscale, and current scales ~linearly with the value written.
# Purely for context printed alongside each step -- not a substitute
# for a real meter.
MA_PER_CHANNEL_AT_FULL = 20

# Optional ADC voltage-divider probe -- off unless you've wired one.
HAS_ADC_PROBE = False
ADC_PIN       = 2    # A2 / GPIO2 on the XIAO C6, change to match your divider
DIVIDER_RATIO = 2.0  # (R1+R2)/R2 -- multiply the ADC reading by this to get rail volts

# ─────────────────────────────────────────────
# HARDWARE
# ─────────────────────────────────────────────
strip = neopixel.NeoPixel(machine.Pin(DATA_PIN), NUM_PIXELS)

probe = None
if HAS_ADC_PROBE:
    try:
        probe = machine.ADC(machine.Pin(ADC_PIN))
        probe.atten(machine.ADC.ATTN_11DB)  # full 0-3.3V range
    except Exception as e:
        print("  [WARN] ADC probe unavailable on pin %d: %s" % (ADC_PIN, str(e)))
        probe = None


def read_probe_voltage():
    """Return the estimated rail voltage from the divider, or None if unavailable."""
    if probe is None:
        return None
    try:
        raw_v = probe.read_uv() / 1_000_000
    except AttributeError:
        raw_v = (probe.read_u16() / 65535) * 3.3
    except Exception:
        return None
    return raw_v * DIVIDER_RATIO


# ─────────────────────────────────────────────
# STRIP HELPERS
# ─────────────────────────────────────────────
def row_color(i):
    """Scaled rainbow color for whichever row pixel `i` falls in."""
    r, g, b = RAINBOW_ROWS[(i // STEP) % len(RAINBOW_ROWS)]
    return (int(r * INTENSITY), int(g * INTENSITY), int(b * INTENSITY))


def light_count(count):
    """Light the first `count` pixels in rainbow rows, the rest off."""
    for i in range(NUM_PIXELS):
        strip[i] = row_color(i) if i < count else (0, 0, 0)
    strip.write()


def clear():
    for i in range(NUM_PIXELS):
        strip[i] = (0, 0, 0)
    strip.write()


# ─────────────────────────────────────────────
# TEST MODES
# ─────────────────────────────────────────────
def hold(count, hold_ms=None):
    """Light `count` pixels in rainbow rows and hold, for manual probing."""
    count = max(0, min(NUM_PIXELS, count))
    light_count(count)
    est_ma = round(sum(sum(row_color(i)) for i in range(count)) * MA_PER_CHANNEL_AT_FULL / 255)
    v = read_probe_voltage()
    if v is not None:
        print("  %3d / %d px lit (rainbow) -- est %dmA -- probe %.2fV" % (count, NUM_PIXELS, est_ma, v))
    else:
        print("  %3d / %d px lit (rainbow) -- est %dmA -- probe the rail now" % (count, NUM_PIXELS, est_ma))
    if hold_ms:
        time.sleep_ms(hold_ms)


def main():
    print("\n" + "=" * 50)
    print("  Icon Display Bring-Up -- Voltage Sag Test")
    print("  %d px, step %d, %dms/hold, intensity %.0f%%" % (NUM_PIXELS, STEP, HOLD_MS, INTENSITY * 100))
    print("=" * 50)
    print("  Watch the far end of the matrix for dimming/color shift.")
    print("  Ctrl-C at any point stops the ramp at the last count shown.\n")

    last_count = 0
    try:
        for count in range(STEP, NUM_PIXELS + 1, STEP):
            hold(count, HOLD_MS)
            last_count = count
    except KeyboardInterrupt:
        print("\n  Stopped by user at %d / %d px lit." % (last_count, NUM_PIXELS))
    else:
        print("\n  Ramp complete -- reached full %d px without aborting." % NUM_PIXELS)
        print("  If everything still looked/read clean at full count, 50%% is safe for this supply.")
    finally:
        clear()
        print("  Strip cleared.")


if __name__ == "__main__":
    main()
