"""
Cooking Recipes — Ingredient Matching Game
==========================================
Tap ingredient NFC tags to collect them, press the button to "cook".
If the collected ingredients match a recipe, the result is displayed.
Tap "stop" tag to exit back to programming mode.

Colors and shapes from leds.py — auto-scale with ambient brightness.
"""

import time
import machine

from nfc_reader import read_ndef_text
from buzzer import NOTE_FREQ
from leds import (
    OFF, RED, GREEN, BLUE, YELLOW, ORANGE, PINK, WHITE,
    RED_DIM, GREEN_DIM, BLUE_DIM, YELLOW_DIM, WHITE_DIM, ORANGE_DIM, PINK_DIM, AMBER_DIM,
)


# ─────────────────────────────────────────────
# Game-specific NFC commands
# ─────────────────────────────────────────────
COMMANDS = {
    "tomato",
    "milk",
    "cheese",
    "flour",
    "egg",
    "butter",
    "sugar",
    "cook",
    "stop",
}

INGREDIENT_ORDER = [
    "tomato",
    "milk",
    "cheese",
    "flour",
    "egg",
    "butter",
    "sugar",
]


# ─────────────────────────────────────────────
# Recipe display colors (from library palette)
# ─────────────────────────────────────────────
BLACK   = OFF
BROWN   = AMBER_DIM

IDLE_DOT   = WHITE_DIM
PROGRESS_C = GREEN_DIM


# ─────────────────────────────────────────────
# Images (5x5 LED patterns using dimmed library colors)
# ─────────────────────────────────────────────
CUPCAKE = [
    BLACK,      BLACK,      RED_DIM,    BLACK,      BLACK,
    BLACK,      PINK_DIM,   PINK_DIM,   PINK_DIM,   BLACK,
    PINK_DIM,   PINK_DIM,   PINK_DIM,   PINK_DIM,   PINK_DIM,
    ORANGE_DIM, ORANGE_DIM, ORANGE_DIM, ORANGE_DIM, ORANGE_DIM,
    BLACK,      BLUE_DIM,   BLUE_DIM,   BLUE_DIM,   BLACK,
]

EGG = [
    BLACK,     BLACK,      BLACK,      BLACK,      BLACK,
    BLACK,     WHITE_DIM,  WHITE_DIM,  WHITE_DIM,  BLACK,
    WHITE_DIM, WHITE_DIM,  YELLOW_DIM, YELLOW_DIM, WHITE_DIM,
    WHITE_DIM, WHITE_DIM,  YELLOW_DIM, YELLOW_DIM, WHITE_DIM,
    BLACK,     BLACK,      WHITE_DIM,  WHITE_DIM,  BLACK,
]

PANCAKES = [
    BLACK,      ORANGE_DIM, ORANGE_DIM, ORANGE_DIM, BLACK,
    ORANGE_DIM, ORANGE_DIM, YELLOW_DIM, ORANGE_DIM, ORANGE_DIM,
    BROWN,      ORANGE_DIM, ORANGE_DIM, ORANGE_DIM, BROWN,
    BLUE_DIM,   BROWN,      BROWN,      BROWN,      BLUE_DIM,
    BLACK,      BLUE_DIM,   BLUE_DIM,   BLUE_DIM,   BLACK,
]

PASTA = [
    BLACK,      WHITE_DIM,  RED_DIM,    BLACK,      BLACK,
    RED_DIM,    RED_DIM,    RED_DIM,    WHITE_DIM,  RED_DIM,
    YELLOW_DIM, YELLOW_DIM, YELLOW_DIM, RED_DIM,    YELLOW_DIM,
    BLUE_DIM,   YELLOW_DIM, YELLOW_DIM, YELLOW_DIM, BLUE_DIM,
    BLACK,      BLUE_DIM,   BLUE_DIM,   BLUE_DIM,   BLACK,
]

PIZZA = [
    BROWN,      BROWN,      BROWN,      BROWN,      BROWN,
    YELLOW_DIM, YELLOW_DIM, RED_DIM,    YELLOW_DIM, YELLOW_DIM,
    BLACK,      RED_DIM,    YELLOW_DIM, YELLOW_DIM, BLACK,
    BLACK,      YELLOW_DIM, YELLOW_DIM, RED_DIM,    BLACK,
    BLACK,      BLACK,      YELLOW_DIM, BLACK,      BLACK,
]

QUESTION = [
    BLACK, YELLOW_DIM, YELLOW_DIM, YELLOW_DIM, BLACK,
    BLACK, BLACK,      BLACK,      YELLOW_DIM, BLACK,
    BLACK, BLACK,      YELLOW_DIM, BLACK,      BLACK,
    BLACK, BLACK,      BLACK,      BLACK,      BLACK,
    BLACK, BLACK,      YELLOW_DIM, BLACK,      BLACK,
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
# Display helpers
# ─────────────────────────────────────────────
def _show_pixels(np, pixel_list):
    for i in range(25):
        np[i] = pixel_list[i]
    np.write()


def _show_idle(np):
    for i in range(25):
        np[i] = IDLE_DOT
    np.write()


def _show_progress(np, scanned):
    count = len(scanned)
    for i in range(25):
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
# Entry point
# ─────────────────────────────────────────────
def play(nfc, leds, buz, accel, i2c):
    """
    Cooking Recipes game entry point.
    Tap ingredient tags to collect them, press button to cook.
    Tap "stop" tag to exit.
    """
    from nfc_reader import NfcReader
    
    np = leds.np
    button = machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP)
    
    # Create game-specific NFC reader
    reader = NfcReader(nfc, COMMANDS)
    
    # Button debounce state
    DEBOUNCE_MS = 50
    stable_state = button.value()
    last_reading = stable_state
    last_change_ms = time.ticks_ms()
    
    def button_was_pressed():
        nonlocal stable_state, last_reading, last_change_ms
        reading = button.value()
        now = time.ticks_ms()
        if reading != last_reading:
            last_change_ms = now
            last_reading = reading
        if time.ticks_diff(now, last_change_ms) > DEBOUNCE_MS:
            if stable_state != reading:
                stable_state = reading
                if stable_state == 0:
                    return True
        return False
    
    # Game state
    scanned_ingredients = set()
    last_uid = None
    poll_count = 0
    
    # Entry feedback
    buz.beep(523, 100)
    _show_idle(np)
    print("\n  === COOKING GAME ===")
    print("  Tap ingredient tags, press button to cook!")
    print("  Tap STOP tag to exit\n")
    
    try:
        while True:
            # ── Check for stop tag periodically ──
            poll_count += 1
            if poll_count >= 15:
                poll_count = 0
                text, uid = read_ndef_text(nfc, timeout=100)
                if text == "stop":
                    print("  STOP tag detected")
                    return
            
            # ── NFC command read ──
            try:
                command, uid_hex = reader.read_command(timeout=120)
            except Exception as e:
                print("  NFC read error: %s" % str(e))
                command = None
                uid_hex = None
            
            if uid_hex is None:
                last_uid = None
            elif uid_hex != last_uid:
                last_uid = uid_hex
                
                if command == "stop":
                    print("  STOP tag detected")
                    return
                
                if command == "cook":
                    scanned_ingredients = set()
                    _show_idle(np)
                    buz.play_note(NOTE_FREQ["notec"], 200)
                    print("  Reset - ready to collect ingredients")
                
                elif command in INGREDIENT_ORDER:
                    scanned_ingredients.add(command)
                    _show_progress(np, scanned_ingredients)
                    buz.play_note(NOTE_FREQ["notee"], 150)
                    print("  Added: %s (%d ingredients)" % (command, len(scanned_ingredients)))
            
            # ── Button press to cook ──
            if button_was_pressed():
                image, matched = _evaluate_recipe(scanned_ingredients)
                _show_pixels(np, image)
                
                if matched:
                    buz.play_note(NOTE_FREQ["noteb"], 300)
                    print("  Recipe matched!")
                else:
                    buz.play_note(NOTE_FREQ["notef"], 300)
                    print("  No matching recipe")
                
                # Wait for button release
                while button.value() == 0:
                    time.sleep_ms(10)
            
            time.sleep_ms(20)
    
    finally:
        # Clean up LEDs on exit
        for i in range(25):
            np[i] = (0, 0, 0)
        np.write()
        print("\n  === RETURNING TO PROGRAMMING MODE ===\n")
