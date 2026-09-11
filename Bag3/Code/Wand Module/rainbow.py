"""
Rainbow Show -- battery level for two seconds, then a static rainbow.

The battery bar is why this game once needed a special case in main.py: it was
the only one handed the gauge. dev.batt carries it now, like any other
peripheral.

Entry point:
    play(dev)
"""

from leds import RED, ORANGE, YELLOW, GREEN, BLUE, PURPLE, PINK, GREEN_DIM

LOOP_MS = 40
NUM_LEDS = 25
HOLD_MS = 2000

RAINBOW = (RED, ORANGE, YELLOW, GREEN, BLUE, PURPLE, PINK)


def _show_battery_bar(dev):
    _, soc = dev.batt.read_all()
    soc = max(0, min(100, int(soc)))
    lit = max(1, min(NUM_LEDS, int(soc / 100.0 * NUM_LEDS)))
    print("  Battery: %d%% (%d LEDs)" % (soc, lit))
    dev.leds.off()
    for i in range(lit):
        row = 4 - (i // 5)
        dev.leds.np[row * 5 + (i % 5)] = GREEN_DIM
    dev.leds.np.write()


def _show_rainbow(dev):
    for i in range(NUM_LEDS):
        dev.leds.np[i] = RAINBOW[i % len(RAINBOW)]
    dev.leds.np.write()


def play(dev):
    dev.buz.start()
    print("\n  === RAINBOW SHOW ===")

    _show_battery_bar(dev)
    dev.tick(HOLD_MS)
    _show_rainbow(dev)
    print("  Rainbow display active.\n")

    while dev.running():
        dev.tick(LOOP_MS)


def main():
    import bench
    play(bench.device())


if __name__ == "__main__":
    main()
