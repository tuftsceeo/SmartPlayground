"""
Cooking Recipes — Ingredient Matching Game
==========================================
Tap ingredient NFC tags to collect them, press the button to "cook".
If the collected ingredients match a recipe, the result is displayed.
Tap "stop" tag to exit back to programming mode.

Colors and shapes from leds.py — auto-scale with ambient brightness.

Entry points:
    play(nfc, leds, buz, accel, i2c, enow)  — called from main.py
    main()                             — standalone testing
"""

import time
import math
import machine
from machine import Pin

from pn532 import PN532
from nfc_reader import NfcReader
from buzzer import NOTE_FREQ
from leds import (
    OFF, RED, GREEN, BLUE, YELLOW, ORANGE, PINK, WHITE, AMBER,
    WHITE_DIM,
)


# ─────────────────────────────────────────────
# Hardware Config
# ─────────────────────────────────────────────
I2C_SDA, I2C_SCL = 22, 23
BUZZER_PIN = 19
BUTTON_PIN = 0
PN532_ADDR = 0x24
NUM_LEDS = 25


# ─────────────────────────────────────────────
# Game Config
# ─────────────────────────────────────────────
COMMANDS = {
    "tomato", "milk", "cheese", "flour",
    "egg", "butter", "sugar", "cook", "stop",
}

INGREDIENT_ORDER = [
    "tomato", "milk", "cheese", "flour",
    "egg", "butter", "sugar",
]

DEBOUNCE_MS = 50
LOOP_DELAY_MS = 20
REPEAT_SCAN_GUARD_MS = 1200


# ─────────────────────────────────────────────
# Sound Sequences
# ─────────────────────────────────────────────
SOUNDS = {
    'enter': [(392, 80, 40), (523, 80, 40), (659, 80, 40), (784, 120, 0)],  # G4-C5-E5-G5
    'exit':  [(784, 80, 40), (659, 80, 40), (523, 120, 0)],                 # G5-E5-C5
}


def _play(buz, name):
    """Play a named sound sequence."""
    seq = SOUNDS.get(name)
    if not seq:
        return
    for freq, dur, gap in seq:
        buz.beep(freq, dur)
        if gap:
            time.sleep_ms(gap)


# ─────────────────────────────────────────────
# Recipe Display Colors
# ─────────────────────────────────────────────
BLACK = OFF
BROWN = AMBER
IDLE_DOT = WHITE_DIM
PROGRESS_C = GREEN


# ─────────────────────────────────────────────
# Images (5x5 LED patterns)
# ─────────────────────────────────────────────
CUPCAKE = [
    BLACK,  BLACK,  RED,    BLACK,  BLACK,
    BLACK,  PINK,   PINK,   PINK,   BLACK,
    PINK,   PINK,   PINK,   PINK,   PINK,
    ORANGE, ORANGE, ORANGE, ORANGE, ORANGE,
    BLACK,  BLUE,   BLUE,   BLUE,   BLACK,
]

EGG = [
    BLACK, BLACK, BLACK,  BLACK,  BLACK,
    BLACK, WHITE, WHITE,  WHITE,  BLACK,
    WHITE, WHITE, YELLOW, YELLOW, WHITE,
    WHITE, WHITE, YELLOW, YELLOW, WHITE,
    BLACK, BLACK, WHITE,  WHITE,  BLACK,
]

PANCAKES = [
    BLACK,  ORANGE, ORANGE, ORANGE, BLACK,
    ORANGE, ORANGE, YELLOW, ORANGE, ORANGE,
    BROWN,  ORANGE, ORANGE, ORANGE, BROWN,
    BLUE,   BROWN,  BROWN,  BROWN,  BLUE,
    BLACK,  BLUE,   BLUE,   BLUE,   BLACK,
]

PASTA = [
    BLACK,  WHITE,  RED,    BLACK,  BLACK,
    RED,    RED,    RED,    WHITE,  RED,
    YELLOW, YELLOW, YELLOW, RED,    YELLOW,
    BLUE,   YELLOW, YELLOW, YELLOW, BLUE,
    BLACK,  BLUE,   BLUE,   BLUE,   BLACK,
]

PIZZA = [
    BROWN,  BROWN,  BROWN,  BROWN,  BROWN,
    YELLOW, YELLOW, RED,    YELLOW, YELLOW,
    BLACK,  RED,    YELLOW, YELLOW, BLACK,
    BLACK,  YELLOW, YELLOW, RED,    BLACK,
    BLACK,  BLACK,  YELLOW, BLACK,  BLACK,
]

QUESTION_IDX = (1, 2, 3, 8, 12, 22)


# ─────────────────────────────────────────────
# Recipes
# ─────────────────────────────────────────────
RECIPES = {
    frozenset(["egg", "butter"]): EGG,
    frozenset(["flour", "milk", "egg", "butter"]): PANCAKES,
    frozenset(["tomato", "cheese", "flour"]): PIZZA,
    frozenset(["tomato", "cheese", "flour", "egg"]): PASTA,
    frozenset(["flour", "milk", "egg", "butter", "sugar"]): CUPCAKE,
}


# ─────────────────────────────────────────────
# Display Class
# ─────────────────────────────────────────────
class CookingDisplay:
    """Handles all LED display for the cooking game."""
    
    def __init__(self, leds):
        self.leds = leds
        self.np = leds.np
    
    def clear(self):
        """Turn off all LEDs."""
        self.leds.off()
    
    def show_idle(self, frame=0):
        """Display idle state with breathing white-dim effect."""
        breath = (math.sin(frame * 0.08) + 1) / 2
        level = 0.3 + 0.7 * breath
        r = int(IDLE_DOT[0] * level)
        g = int(IDLE_DOT[1] * level)
        b = int(IDLE_DOT[2] * level)
        for i in range(NUM_LEDS):
            self.np[i] = (r, g, b)
        self.np.write()
    
    def show_progress(self, scanned_set, frame=0):
        """Show collected ingredients with pulsing next-slot."""
        count = len(scanned_set)
        pulse = (math.sin(frame * 0.15) + 1) / 2
        
        for i in range(NUM_LEDS):
            if i < count:
                self.np[i] = PROGRESS_C
            elif i == count:
                scale = 0.3 + 0.7 * pulse
                self.np[i] = (
                    int(PROGRESS_C[0] * scale),
                    int(PROGRESS_C[1] * scale),
                    int(PROGRESS_C[2] * scale),
                )
            else:
                self.np[i] = IDLE_DOT
        self.np.write()
    
    def show_recipe(self, image):
        """Display a full RGB recipe image."""
        for i in range(NUM_LEDS):
            self.np[i] = image[i]
        self.np.write()
    
    def show_question(self):
        """Display yellow question-mark for unknown recipe."""
        self.leds.show_shape(QUESTION_IDX, YELLOW)


def _evaluate_recipe(scanned):
    key = frozenset(scanned)
    if key in RECIPES:
        return RECIPES[key], True
    return None, False


# ─────────────────────────────────────────────
# Game Class
# ─────────────────────────────────────────────
class CookingGame:
    """Ingredient matching and recipe cooking game."""
    
    def __init__(self, nfc, leds, buz, enow):
        self.nfc = nfc
        self.leds = leds
        self.buz = buz
        self.enow = enow
        self.display = CookingDisplay(leds)
        self.btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
        self.reader = NfcReader(nfc, COMMANDS)
        
        # Game state
        self.scanned_ingredients = set()
        self.last_uid = None
        self.last_scan_ms = 0
        self._frame = 0
        
        # Button state: read at init to avoid false trigger from held button
        self._btn_was_down = (self.btn.value() == 0)
    
    def _button_was_pressed(self):
        """Check for debounced button press edge. Returns True on press."""
        down = (self.btn.value() == 0)
        if down and not self._btn_was_down:
            time.sleep_ms(DEBOUNCE_MS)
            if self.btn.value() == 0:
                self._btn_was_down = True
                return True
        elif not down and self._btn_was_down:
            self._btn_was_down = False
        return False
    
    def _cook(self):
        """Evaluate recipe and display result."""
        image, matched = _evaluate_recipe(self.scanned_ingredients)
        
        if matched:
            self.display.show_recipe(image)
            self.buz.play_note(NOTE_FREQ["noteb"], 300)
            print("  Recipe matched!")
        else:
            self.display.show_question()
            self.buz.play_note(NOTE_FREQ["notef"], 300)
            print("  No matching recipe")
        
        # Wait for button release
        while self.btn.value() == 0:
            time.sleep_ms(10)
    
    def _reset(self):
        """Reset ingredients for new recipe."""
        self.scanned_ingredients = set()
        self.display.show_idle(self._frame)
        self.buz.play_note(NOTE_FREQ["notec"], 200)
        print("  Reset - ready to collect ingredients")
    
    def run(self):
        """Main game loop. Returns when stop tag is tapped."""
        print("  Tap ingredient tags, press button to cook!")
        print("  Tap STOP tag or station stop to exit\n")
        
        while True:
            # ── ESP-NOW ──
            if self.enow:
                msg_type, _, _ = self.enow.poll()
                if msg_type == "stop":
                    print("  ESP-NOW stop")
                    return

            # ── DISPLAY UPDATE ──
            if len(self.scanned_ingredients) > 0:
                self.display.show_progress(self.scanned_ingredients, self._frame)
            else:
                self.display.show_idle(self._frame)
            
            # ── STOP CHECK via NfcReader (at top of loop) ──
            try:
                command, uid_hex = self.reader.read_command(timeout=120)
            except Exception as e:
                print("  NFC read error: %s" % str(e))
                command = None
                uid_hex = None
            
            if command == "stop":
                print("  STOP tag detected")
                return
            
            # ── GAME LOGIC ──
            if uid_hex is None:
                self.last_uid = None
            else:
                now = time.ticks_ms()
                # Skip if same tag and within repeat guard window
                if uid_hex == self.last_uid and time.ticks_diff(now, self.last_scan_ms) < REPEAT_SCAN_GUARD_MS:
                    pass
                else:
                    self.last_uid = uid_hex
                    self.last_scan_ms = now
                    
                    if command == "cook":
                        self._reset()
                    
                    elif command in INGREDIENT_ORDER:
                        self.scanned_ingredients.add(command)
                        self.buz.play_note(NOTE_FREQ["notee"], 150)
                        print("  Added: %s (%d ingredients)" % (command, len(self.scanned_ingredients)))
            
            # ── BUTTON: Cook recipe ──
            if self._button_was_pressed():
                self._cook()
            
            self._frame += 1
            time.sleep_ms(LOOP_DELAY_MS)


# ─────────────────────────────────────────────
# Entry Point: Wand Integration
# ─────────────────────────────────────────────
def play(nfc, leds, buz, accel, i2c, enow):
    """
    Called from main.py when the "cooking" tag is tapped.
    Hardware is already initialized by the caller.
    """
    _play(buz, 'enter')
    
    print("\n  === COOKING GAME ===")
    
    try:
        CookingGame(nfc, leds, buz, enow).run()
    finally:
        _play(buz, 'exit')
        leds.off()
        print("\n  === RETURNING TO PROGRAMMING MODE ===\n")


# ─────────────────────────────────────────────
# Entry Point: Standalone Testing
# ─────────────────────────────────────────────
def main():
    """
    Standalone entry point for testing without main.py.
    Run directly: import cooking; cooking.main()
    """
    print("\n" + "=" * 45)
    print("  Cooking Recipes — Ingredient Matching Game")
    print("=" * 45)
    
    i2c = machine.SoftI2C(sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=100_000)
    
    # Calibrate brightness from ambient light
    import brightness
    try:
        from opt3002 import OPT3002
        light = OPT3002(i2c)
        light.init()
        mult, lux = brightness.calibrate(light)
        if lux is not None:
            print("  Light: %.0f lux -> brightness x%.2f" % (lux, mult))
    except Exception as e:
        print("  [WARN] OPT3002: %s — brightness x1.00" % e)
    
    # Initialize LEDs
    from leds import Leds
    leds = Leds()
    
    # Initialize buzzer
    from buzzer import Buzzer
    buz = Buzzer(BUZZER_PIN)
    
    # Initialize NFC
    nfc = PN532(i2c, PN532_ADDR)
    try:
        ic, ver, rev = nfc.begin()
        print("  PN5%02X fw %d.%d — NFC ready" % (ic, ver, rev))
    except Exception as e:
        print("  NFC init failed: %s" % e)
        return
    
    from espnow_manager import ESPNowManager
    enow = ESPNowManager()
    enow.init()

    print()
    
    # Run the game
    play(nfc, leds, buz, None, i2c, enow)


if __name__ == "__main__":
    main()
