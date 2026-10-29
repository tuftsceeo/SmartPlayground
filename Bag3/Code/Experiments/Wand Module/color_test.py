"""
Color Test — show every named color in leds.py as one pixel each
================================================================
Lights one LED per color, side-by-side, in spectrum order. Static
display — nothing animates, nothing cycles. Brightness is scaled
by brightness.MULTIPLIER (calibrated from ambient light), so what
you see here matches what games will render.

Layout on the 5x5 grid (row-major, 18 colors):
    row 0:  RED ROSE ORANGE AMBER YELLOW
    row 1:  LIME GREEN MINT TEAL CYAN
    row 2:  SKY BLUE INDIGO PURPLE MAGENTA
    row 3:  PINK PEACH WHITE  .    .
    row 4:  .    .    .      .    .

Run standalone:
    import color_test
    color_test.main()
"""

import machine
import time
from machine import Pin

import leds as L


BUTTON_PIN = 0


# Spectrum order — each entry is (name, color). One pixel per color,
# placed at successive LED indices on the 5x5 grid.
SEQUENCE = [
    ("RED",     L.RED),
    ("ROSE",    L.ROSE),
    ("ORANGE",  L.ORANGE),
    ("AMBER",   L.AMBER),
    ("YELLOW",  L.YELLOW),
    ("LIME",    L.LIME),
    ("GREEN",   L.GREEN),
    ("MINT",    L.MINT),
    ("TEAL",    L.TEAL),
    ("CYAN",    L.CYAN),
    ("SKY",     L.SKY),
    ("BLUE",    L.BLUE),
    ("INDIGO",  L.INDIGO),
    ("PURPLE",  L.PURPLE),
    ("MAGENTA", L.MAGENTA),
    ("PINK",    L.PINK),
    ("PEACH",   L.PEACH),
    ("WHITE",   L.WHITE),
]


def show(leds):
    """Light one LED per color in SEQUENCE, all others off. Static."""
    for i in range(leds.num):
        leds.np[i] = L.OFF
    for idx, (name, color) in enumerate(SEQUENCE):
        if idx < leds.num:
            leds.np[idx] = color
    leds.np.write()

    # Console map so you can identify each pixel by position
    print("\n  LED layout (index : name : raw RGB):")
    for idx, (name, color) in enumerate(SEQUENCE):
        if idx < leds.num:
            print("    %2d  %-8s %s" % (idx, name, color))


def main():
    """Standalone entry. Calibrates brightness, lights all colors, holds."""
    print("\n" + "=" * 45)
    print("  Color Test — 1 pixel per color, static")
    print("=" * 45)

    # Calibrate brightness from ambient light so what we display matches
    # how the games will render.
    try:
        from hubtype import HUB_CONFIG
        i2c = machine.SoftI2C(
            sda=Pin(HUB_CONFIG["i2c_sda"]),
            scl=Pin(HUB_CONFIG["i2c_scl"]),
            freq=100_000,
        )
        import brightness
        try:
            from opt3002 import OPT3002
            light = OPT3002(i2c)
            light.init()
            mult, lux = brightness.calibrate(light)
            if lux is not None:
                print("  Light: %.0f lux -> brightness x%.2f" % (lux, mult))
            else:
                print("  brightness x%.2f (no lux reading)" % mult)
        except Exception as e:
            print("  [WARN] OPT3002: %s — brightness x1.00" % e)
    except Exception as e:
        print("  [WARN] brightness setup skipped: %s" % e)

    from leds import Leds
    leds = Leds()

    show(leds)

    print("\n  Holding display. Press button or Ctrl-C to exit.")
    btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
    try:
        while True:
            if btn.value() == 0:
                time.sleep_ms(30)
                if btn.value() == 0:
                    while btn.value() == 0:
                        time.sleep_ms(10)
                    break
            time.sleep_ms(50)
    except KeyboardInterrupt:
        print("\n  Interrupted")
    finally:
        leds.off()
        print("  Done.")


if __name__ == "__main__":
    main()
