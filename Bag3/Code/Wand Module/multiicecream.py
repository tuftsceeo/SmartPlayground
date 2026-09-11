"""
Multi Ice Cream -- build a three-scoop cone.

Press the button to count, flip the wand over and back to commit that count as
one scoop's colour. The centre column shows the running count while scooping;
the whole grid shows the cone once scoops are committed. A fourth press after
three scoops starts a new cone.

Entry point:
    play(dev)
"""

from leds import (
    RED, ORANGE, YELLOW, GREEN, BLUE, PINK, PURPLE, WHITE,
    SHAPE_COL3,
)

LOOP_MS = 40

UPRIGHT_X = 0.7
UPSIDEDOWN_X = -0.7

NUM_SCOOPS = 3

# Grid rows each scoop occupies, bottom scoop first.
SCOOP_PIXELS = (
    tuple(range(15, 25)),
    tuple(range(10, 15)),
    tuple(range(0, 10)),
)

# press count 1..7 -> colour; 8 or more is white
SCOOP_RAMP = (RED, ORANGE, YELLOW, GREEN, BLUE, PINK, PURPLE, WHITE)


def _color_for(count):
    if count < 1 or count >= 8:
        return WHITE
    return SCOOP_RAMP[count - 1]


class Cone:
    def __init__(self, dev):
        self.dev = dev
        self.upright = True
        self.btn_down = (dev.button.value() == 0)
        self.new_cone()
        dev.leds.fill(WHITE)

    def new_cone(self):
        self.count = 0
        self.filled = 0
        self.colors = [None] * NUM_SCOOPS
        self.counting = False

    def render(self):
        """Draw every committed scoop; an empty cone is plain white."""
        if not self.filled:
            self.dev.leds.fill(WHITE)
            return
        pattern = {}
        for i in range(self.filled):
            pattern.setdefault(self.colors[i], []).extend(SCOOP_PIXELS[i])
        self.dev.leds.show_pattern(pattern)

    def scoop(self):
        """One press adds to the count, or starts a new cone after the third."""
        down = (self.dev.button.value() == 0)
        pressed = down and not self.btn_down and self.upright
        self.btn_down = down
        if not pressed:
            return
        if self.filled >= NUM_SCOOPS:
            self.new_cone()
        self.count += 1
        self.counting = True
        lit = min(self.count, len(SHAPE_COL3))
        self.dev.leds.show_shape(SHAPE_COL3[:lit], WHITE)

    def orientation(self):
        """Flipping over and back commits the current count as a scoop."""
        x, _y, _z = self.dev.accel.read()
        if self.upright:
            if x < UPSIDEDOWN_X:
                self.upright = False
            return
        if x <= UPRIGHT_X:
            return
        self.upright = True
        if self.counting and self.filled < NUM_SCOOPS:
            self.colors[self.filled] = _color_for(self.count)
            self.filled += 1
            self.count = 0
            self.counting = False
            self.dev.buz.confirm()
        self.render()


def play(dev):
    dev.buz.start()
    print("\n  === MULTI ICE CREAM ===")
    print("  Press to count, flip to commit. Three scoops to a cone.\n")

    cone = Cone(dev)
    while dev.running():
        cone.scoop()
        cone.orientation()
        dev.tick(LOOP_MS)


def main():
    import bench
    play(bench.device())


if __name__ == "__main__":
    main()
