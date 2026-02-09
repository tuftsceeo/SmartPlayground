import time, json
import asyncio

from games.game import Game
from utilities.colors import *

INTENSITY = 0.1
UPRIGHT_THRESHOLD = 0.7
UPSIDEDOWN_THRESHOLD = -0.7

SCOOP_SIZE = 4
NUM_SCOOPS = 3

# NEW: show up to 7 button presses in the white counting bar (LEDs 0–6)
COUNT_BAR_LEN = 7

TARGET_COMBOS = [
    [YELLOW, YELLOW, YELLOW],
    [YELLOW, RED, PURPLE ],
]
# Edit color combos for each animal

class Color_Press_Mult(Game):
    def __init__(self, main):
        super().__init__(main, 'color_press')

        self.button_count = 0
        self.state = 'Upright'

        self.scoop_index = 0
        self.scoop_colors = [None] * NUM_SCOOPS
        self.counting_mode = False

    def _log(self, message):
        try:
            self.main.log_message(f"[COLOR_PRESS_MULT] {message}")
        except:
            print(message)

    def start(self):
        self._log("Game started")
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
                    self._log("New cycle started (all scoops filled)")
                    self._restart_for_new_cycle()

                # debounce
                while self.main.button.pressed:
                    pass

                self.button_count += 1
                self.counting_mode = True
                self._log(f"Button pressed | scoop={self.scoop_index+1}/{NUM_SCOOPS} | count={self.button_count}")

                # focus counting view
                self._render_count_bar()

            # --- flip detection commits scoop ---
            if self.state == 'Upright':
                if x < UPSIDEDOWN_THRESHOLD:
                    self.state = 'Upside_down'
                    self._log(f"Flip → Upside_down | x={x:+.3f}")

            elif self.state == 'Upside_down':
                if x > UPRIGHT_THRESHOLD:
                    self.state = 'Upright'
                    self._log(f"Flip → Upright | x={x:+.3f}")

                    # Commit ONLY if we are mid-cycle and the user actually counted presses
                    if self.scoop_index < NUM_SCOOPS and self.counting_mode:
                        chosen = self._color_from_count(self.button_count)
                        self.scoop_colors[self.scoop_index] = chosen

                        self._log(f"Scoop committed | scoop={self.scoop_index+1}/{NUM_SCOOPS} | count={self.button_count} → color_index={8-self.button_count if self.button_count < 8 else 'WHITE'}")

                        self.scoop_index += 1
                        self.button_count = 0
                        self.counting_mode = False

                        if self.scoop_index >= NUM_SCOOPS:
                            self._log(f"All {NUM_SCOOPS} scoops complete | colors={self.scoop_colors}")
                            if self.scoop_colors in TARGET_COMBOS:
                                self._log("TARGET_COMBO matched → blink + rainbow")
                                self._render_committed()
                                await asyncio.sleep(0.5)
                                last_scoop_color = self.scoop_colors[-1]
                                for _ in range(5):
                                    self.main.lights.all_off()
                                    await asyncio.sleep(0.2)
                                    self._render_committed()
                                    await asyncio.sleep(0.2)
                                for i in range(12):
                                    self.main.lights.on(i, COLORS[i % 7], INTENSITY)
                                self._log("Rainbow displayed")
                                return

                        # after commit, all scoops reappear
                        self._render_committed()
                    else:
                        self._render_committed()

        except Exception as e:
            print(e)

    def close(self):
        self._log(f"Game closed | scoop_index={self.scoop_index} | scoop_colors={self.scoop_colors}")
        self.main.lights.all_off()
