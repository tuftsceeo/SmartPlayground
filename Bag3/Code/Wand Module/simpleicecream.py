"""
Simple Ice Cream -- press to add scoops, flip over to serve.

While upright, each button press adds a scoop and lights one more pixel on the
bottom row. Flipping the wand upside-down and back reveals the colour that
scoop count earns, then resets to an empty cone.

Entry point:
    play(dev)
"""

from leds import (
    RED, ORANGE, YELLOW, GREEN, BLUE, PINK, PURPLE, WHITE,
    SHAPE_BOT_ROW,
)

LOOP_MS = 40

UPRIGHT_X = 0.7
UPSIDEDOWN_X = -0.7

# scoop count 1..7 -> colour; 8 or more is white
SCOOP_RAMP = (RED, ORANGE, YELLOW, GREEN, BLUE, PINK, PURPLE, WHITE)


def _color_for(count):
    if count < 1 or count >= 8:
        return WHITE
    return SCOOP_RAMP[count - 1]


class IceCream:
    def __init__(self, dev):
        self.dev = dev
        self.count = 0
        self.upright = True
        self.btn_down = (dev.button.value() == 0)
        dev.leds.fill(WHITE)

    def scoop(self):
        """One press while upright adds a scoop. Returns True on a new press."""
        down = (self.dev.button.value() == 0)
        pressed = down and not self.btn_down and self.upright
        self.btn_down = down
        if not pressed:
            return False
        self.count += 1
        lit = min(self.count, len(SHAPE_BOT_ROW))
        self.dev.leds.show_shape(SHAPE_BOT_ROW[:lit], WHITE)
        return True

    def orientation(self):
        """Serve the cone when the wand is flipped over and back upright."""
        x, _y, _z = self.dev.accel.read()
        if self.upright:
            if x < UPSIDEDOWN_X:
                self.upright = False
            return
        if x <= UPRIGHT_X:
            return
        self.upright = True
        self.dev.leds.fill(_color_for(self.count))
        self.dev.buz.success()
        self.count = 0
        self.dev.leds.fill(WHITE)


def play(dev):
    dev.buz.start()
    print("\n  === SIMPLE ICE CREAM ===")
    print("  Press the button while upright to count scoops.")
    print("  Flip upside-down and back to serve.\n")

    game = IceCream(dev)
    while dev.running():
        game.scoop()
        game.orientation()
        dev.tick(LOOP_MS)


def main():
    import bench
    play(bench.device())


if __name__ == "__main__":
    main()
