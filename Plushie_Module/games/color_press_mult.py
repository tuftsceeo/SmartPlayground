import time, json

from games.game import Game
from utilities.colors import *

INTENSITY = 0.1
UPRIGHT_THRESHOLD = 0.7
UPSIDEDOWN_THRESHOLD = -0.7

SCOOP_SIZE = 4
NUM_SCOOPS = 3

# NEW: show up to 7 button presses in the white counting bar (LEDs 0–6)
COUNT_BAR_LEN = 7


class Color_Press_Mult(Game):
    def __init__(self, main):
        super().__init__(main, 'color_press')

        self.button_count = 0
        self.state = 'Upright'

        self.scoop_index = 0
        self.scoop_colors = [None] * NUM_SCOOPS
        self.counting_mode = False

    def start(self):
        self._reset_cycle()

    # ---------- helpers ----------
    def _color_from_count(self, count):
        # unchanged mapping logic
        if count < 8:
            return COLORS[8 - count]
        return WHITE

    def _scoop_range(self, scoop_index):
        start = scoop_index * SCOOP_SIZE
        return start, start + SCOOP_SIZE  # end exclusive

    def _render_committed(self):
        """Show all committed scoops (and nothing else)."""
        self.main.lights.all_off()
        for s in range(NUM_SCOOPS):
            c = self.scoop_colors[s]
            if c is None:
                continue
            start, end = self._scoop_range(s)
            for i in range(start, end):
                self.main.lights.on(i, c, INTENSITY)

    def _render_count_bar(self):
        """
        Focus view while counting:
        - previous scoops disappear
        - ALWAYS show the counting bar starting at LED 0
        - Count visually up to 7 presses (LEDs 0–6)
        """
        self.main.lights.all_off()

        n = min(self.button_count, COUNT_BAR_LEN)
        for i in range(0, n):
            self.main.lights.on(i, WHITE, INTENSITY)

    def _reset_cycle(self):
        # full reset (including LEDs)
        self.button_count = 0
        self.scoop_index = 0
        self.scoop_colors = [None] * NUM_SCOOPS
        self.counting_mode = False

        # module begins with all WHITE
        self.main.lights.all_on(WHITE, INTENSITY)

    def _restart_for_new_cycle(self):
        """
        Logic reset ONLY (do not change LEDs).
        Keeps scoop 3 visible until the first press,
        then counting view takes over.
        """
        self.button_count = 0
        self.scoop_index = 0
        self.scoop_colors = [None] * NUM_SCOOPS
        self.counting_mode = False

    async def loop(self):
        try:
            x, y, z = self.main.accel.read_accel()

            # --- button press while upright ---
            if self.main.button.pressed and self.state == 'Upright':

                # After scoop 3 is showing, first press begins a new cycle for scoop 1
                if self.scoop_index >= NUM_SCOOPS:
                    self._restart_for_new_cycle()

                # debounce
                while self.main.button.pressed:
                    pass

                self.button_count += 1
                self.counting_mode = True

                # focus counting view
                self._render_count_bar()

            # --- flip detection commits scoop ---
            if self.state == 'Upright':
                if x < UPSIDEDOWN_THRESHOLD:
                    self.state = 'Upside_down'

            elif self.state == 'Upside_down':
                if x > UPRIGHT_THRESHOLD:
                    self.state = 'Upright'

                    # Commit ONLY if we are mid-cycle and the user actually counted presses
                    if self.scoop_index < NUM_SCOOPS and self.counting_mode:
                        chosen = self._color_from_count(self.button_count)
                        self.scoop_colors[self.scoop_index] = chosen

                        self.scoop_index += 1
                        self.button_count = 0
                        self.counting_mode = False

                        # after commit, all scoops reappear
                        self._render_committed()
                    else:
                        self._render_committed()

        except Exception as e:
            print(e)

    def close(self):
        self.main.lights.all_off()
