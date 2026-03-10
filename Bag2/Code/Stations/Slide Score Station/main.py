"""
Slide Score Station — 40-LED serpentine bar graph scoreboard
=============================================================
Board: Seeed XIAO ESP32-C6
Requires hubtype.txt containing: score_board
Requires /lib/: hubtype.py, espnow_manager.py

Note: This device uses its own NeoPixel handling (serpentine grid)
rather than the shared Leds class, because the pixel addressing
is specialized for the 4x10 bar graph layout.
"""

import machine
import neopixel
import time
import random
from collections import deque

from hubtype import HUB_TYPE, HUB_CONFIG
from espnow_manager import ESPNowManager

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
DATA_PIN   = HUB_CONFIG.get("led_pin", 0)
NUM_PIXELS = HUB_CONFIG.get("num_leds", 40)
NUM_BARS   = 4
BAR_HEIGHT = 10
MIN_ROWS   = 2

COLOR_RGB = {
    "turnblue": (0, 0, 255), "turngreen": (0, 255, 0),
    "turnpurple": (160, 0, 200), "turnred": (255, 0, 0),
}

BRIGHTNESS_SCALE = 0.8
RAINBOW_ROWS = [
    (255, 0, 0), (255, 100, 0), (200, 200, 0),
    (0, 255, 0), (0, 0, 255), (130, 0, 255),
]
PLAYER_COLORS = [
    (255, 80, 0), (0, 220, 220), (220, 0, 220), (220, 220, 0),
    (0, 200, 80), (200, 0, 80), (80, 100, 255), (255, 100, 180),
]

# ─────────────────────────────────────────────
# HARDWARE
# ─────────────────────────────────────────────
strip = neopixel.NeoPixel(machine.Pin(DATA_PIN), NUM_PIXELS)

# ─────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────
score_queue = deque((), NUM_BARS)
current_game = None
score_count = 0

def _scale(rgb):
    return tuple(int(c * BRIGHTNESS_SCALE) for c in rgb)

def pixel_index(col, row):
    base = col * BAR_HEIGHT
    return base + row if col % 2 == 0 else base + (BAR_HEIGHT - 1 - row)

def _set_col(col, rgb):
    for row in range(BAR_HEIGHT):
        strip[pixel_index(col, row)] = rgb
    strip.write()

def reset_for_new_game(new_game):
    global score_queue, current_game, score_count
    print("[game] New: %s" % str(new_game))
    current_game = new_game
    score_queue = deque((), NUM_BARS)
    score_count = 0
    for i in range(NUM_PIXELS):
        strip[i] = _scale((200, 200, 200)); strip.write(); time.sleep_ms(8)
    time.sleep_ms(120)
    for i in range(NUM_PIXELS): strip[i] = (0, 0, 0)
    strip.write()

def score_arrival_animation(new_col):
    WHITE = (255, 255, 255)
    TRAIL1 = (80, 30, 220)
    TRAIL2 = (25, 10, 70)

    for _ in range(9):
        lit = []
        for _ in range(random.randint(3, 6)):
            px = random.randint(0, NUM_PIXELS - 1)
            br = random.randint(120, 255)
            strip[px] = _scale((br, int(br * 0.65), int(br * 0.1))); lit.append(px)
        strip.write(); time.sleep_ms(28)
        for px in lit: strip[px] = (0, 0, 0)
        time.sleep_ms(22)

    _set_col(new_col, (0, 0, 0))
    for row in range(BAR_HEIGHT):
        _set_col(new_col, (0, 0, 0))
        strip[pixel_index(new_col, row)] = _scale(WHITE)
        if row >= 1: strip[pixel_index(new_col, row - 1)] = _scale(TRAIL1)
        if row >= 2: strip[pixel_index(new_col, row - 2)] = _scale(TRAIL2)
        strip.write(); time.sleep_ms(27)

    _set_col(new_col, _scale(WHITE)); time.sleep_ms(150)

    for row in range(BAR_HEIGHT):
        strip[pixel_index(new_col, row)] = _scale(RAINBOW_ROWS[row % len(RAINBOW_ROWS)])
        strip.write(); time.sleep_ms(30)
    time.sleep_ms(280)
    _set_col(new_col, (0, 0, 0))

def update_display():
    for i in range(NUM_PIXELS): strip[i] = (0, 0, 0)
    scores = list(score_queue)
    if not scores:
        strip.write(); return
    min_t = min(s["time_ms"] for s in scores)
    for col, entry in enumerate(scores):
        prop = min_t / entry["time_ms"] if entry["time_ms"] > 0 else 1.0
        lit = max(MIN_ROWS, round(prop * BAR_HEIGHT))
        rgb = _scale(entry["player_rgb"])
        for row in range(lit):
            strip[pixel_index(col, row)] = rgb
    strip.write()

def startup_animation():
    sw = _scale((80, 80, 80))
    for i in range(NUM_PIXELS):
        strip[i] = sw; strip.write(); time.sleep(0.03)
    time.sleep(0.2)
    for cn, rgb in COLOR_RGB.items():
        sc = _scale(rgb)
        for i in range(NUM_PIXELS): strip[i] = sc
        strip.write(); time.sleep(0.3)
    for i in range(NUM_PIXELS): strip[i] = (0, 0, 0)
    strip.write()

# ─────────────────────────────────────────────
# MESSAGE HANDLERS
# ─────────────────────────────────────────────
def handle_colors(mac_str, color_list):
    valid = [c for c in color_list if c in COLOR_RGB]
    if valid:
        print("[station] New game from %s: %s" % (mac_str, str(valid)))
        reset_for_new_game(valid)

def handle_score(mac_str, data):
    global current_game, score_count
    colors = data.get("colors")
    time_ms = data.get("time_ms")
    if not colors or time_ms is None: return

    if current_game is not None and colors != current_game:
        reset_for_new_game(colors)
    elif current_game is None:
        current_game = colors

    rgb = PLAYER_COLORS[score_count % len(PLAYER_COLORS)]
    score_count += 1
    score_queue.append({"player_rgb": rgb, "time_ms": time_ms})
    new_col = len(score_queue) - 1
    print("[score] #%d from %s: %dms" % (score_count, mac_str, time_ms))
    score_arrival_animation(new_col)
    update_display()

def handle_stop():
    global score_queue, current_game, score_count
    print("[stop] Resetting board")
    current_game = None
    score_queue = deque((), NUM_BARS)
    score_count = 0
    for i in range(NUM_PIXELS): strip[i] = (0, 0, 0)
    strip.write()

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
print("\n" + "=" * 50)
print("  Slide Score Station")
print("  Hub type: %s" % HUB_TYPE)
print("=" * 50)

startup_animation()

mgr = ESPNowManager()
mgr.init()

update_display()
print("[main] Listening...\n")

while True:
    msg_type, data, mac_str = mgr.poll(timeout_ms=100)

    if msg_type == "colors":
        handle_colors(mac_str, data)

    elif msg_type == "score":
        handle_score(mac_str, data)

    elif msg_type == "stop":
        handle_stop()

    elif msg_type == "battery":
        # Scoreboard has no battery — ignore
        pass