"""
Cooking Recipes — Ingredient Matching Game
==========================================
Tap ingredient NFC tags to collect them, press the button to "cook".
If the collected ingredients match a recipe, the result is displayed.
Tap "stop" tag to exit back to programming mode.

Colors and shapes from leds.py — auto-scale with ambient brightness.

Entry points:
    play(nfc, leds, buz, accel, i2c)  — called from main.py
    main()                             — standalone testing

Template Pattern:
    1. CookingGame class with __init__() and run()
    2. play() for wand integration (hardware passed in)
    3. main() for standalone testing (initializes hardware)
    4. CRITICAL: Stop tag checked via NfcReader at START of every loop
"""

import time
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

QUESTION = [
    BLACK, YELLOW, YELLOW, YELLOW, BLACK,
    BLACK, BLACK,  BLACK,  YELLOW, BLACK,
    BLACK, BLACK,  YELLOW, BLACK,  BLACK,
    BLACK, BLACK,  BLACK,  BLACK,  BLACK,
    BLACK, BLACK,  YELLOW, BLACK,  BLACK,
]


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
# Display Helpers
# ─────────────────────────────────────────────
def _show_pixels(np, pixel_list):
    for i in range(NUM_LEDS):
        np[i] = pixel_list[i]
    np.write()


def _show_idle(np):
    for i in range(NUM_LEDS):
        np[i] = IDLE_DOT
    np.write()


def _show_progress(np, scanned):
    count = len(scanned)
    for i in range(NUM_LEDS):
        np[i] = IDLE_DOT
    for i in range(count):
        np[i] = PROGRESS_C
    np.write()


def _evaluate_recipe(scanned):
    key = frozenset(scanned)
    if key in RECIPES:
        return RECIPES[key], True
    return QUESTION, False


# ─────────────────────────────────────────────
# Game Class
# ─────────────────────────────────────────────
class CookingGame:
    """Ingredient matching and recipe cooking game."""
    
    def __init__(self, nfc, leds, buz):
        self.nfc = nfc
        self.leds = leds
        self.buz = buz
        self.np = leds.np
        self.btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
        self.reader = NfcReader(nfc, COMMANDS)
        
        # Game state
        self.scanned_ingredients = set()
        self.last_uid = None
        
        # Button debounce state
        self._stable_state = self.btn.value()
        self._last_reading = self._stable_state
        self._last_change_ms = time.ticks_ms()
    
    def _button_was_pressed(self):
        """Check for debounced button press. Returns True on press edge."""
        reading = self.btn.value()
        now = time.ticks_ms()
        
        if reading != self._last_reading:
            self._last_change_ms = now
            self._last_reading = reading
        
        if time.ticks_diff(now, self._last_change_ms) > DEBOUNCE_MS:
            if self._stable_state != reading:
                self._stable_state = reading
                if self._stable_state == 0:
                    return True
        return False
    
    def _cook(self):
        """Evaluate recipe and display result."""
        image, matched = _evaluate_recipe(self.scanned_ingredients)
        _show_pixels(self.np, image)
        
        if matched:
            self.buz.play_note(NOTE_FREQ["noteb"], 300)
            print("  Recipe matched!")
        else:
            self.buz.play_note(NOTE_FREQ["notef"], 300)
            print("  No matching recipe")
        
        # Wait for button release
        while self.btn.value() == 0:
            time.sleep_ms(10)
    
    def _reset(self):
        """Reset ingredients for new recipe."""
        self.scanned_ingredients = set()
        _show_idle(self.np)
        self.buz.play_note(NOTE_FREQ["notec"], 200)
        print("  Reset - ready to collect ingredients")
    
    def run(self):
        """Main game loop. Returns when stop tag is tapped."""
        print("  Tap ingredient tags, press button to cook!")
        print("  Tap STOP tag to exit\n")
        
        _show_idle(self.np)
        
        while True:
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
            elif uid_hex != self.last_uid:
                self.last_uid = uid_hex
                
                if command == "cook":
                    self._reset()
                
                elif command in INGREDIENT_ORDER:
                    self.scanned_ingredients.add(command)
                    _show_progress(self.np, self.scanned_ingredients)
                    self.buz.play_note(NOTE_FREQ["notee"], 150)
                    print("  Added: %s (%d ingredients)" % (command, len(self.scanned_ingredients)))
            
            # ── BUTTON: Cook recipe ──
            if self._button_was_pressed():
                self._cook()
            
            time.sleep_ms(LOOP_DELAY_MS)


# ─────────────────────────────────────────────
# Entry Point: Wand Integration
# ─────────────────────────────────────────────
def play(nfc, leds, buz, accel, i2c):
    """
    Called from main.py when the "cooking" tag is tapped.
    Hardware is already initialized by the caller.
    """
    buz.beep(523, 100)
    
    print("\n  === COOKING GAME ===")
    
    try:
        CookingGame(nfc, leds, buz).run()
    finally:
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
    
    print()
    
    # Run the game
    play(nfc, leds, buz, None, i2c)


if __name__ == "__main__":
    main()
