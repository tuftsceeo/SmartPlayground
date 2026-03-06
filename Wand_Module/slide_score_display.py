"""
scoreboard.py

Receives ESP-NOW score messages and displays the last 4 scores as a
bar graph on a 40-pixel NeoPixel strip wired in a serpentine 4x10 grid.

Grid layout (viewed from the front):

    row 9 (top)
    ...
    row 0 (bottom)
         col0  col1  col2  col3

Serpentine wiring: even columns run bottom-to-top (pixel 0 = row 0),
odd columns run top-to-bottom (pixel 0 = row 9). Each column is 10
pixels, so column c starts at pixel index c * 10.

Bar fill: INVERTED — fastest time = tallest bar (full height).
All other bars are scaled relative to the fastest:
    proportion = fastest_time_ms / this_time_ms
so a player who took twice as long gets half the bar height.
MIN_ROWS ensures every player has a visible bar even if they were slow.

Bars are assigned left-to-right in arrival order (FIFO — oldest drops
when a 5th score arrives).

Player colors: each score arrival gets the next color from PLAYER_COLORS
in rotation (score_count % 8).  The same wand submitting again — whether
a retry or shared between kids — just gets the next color naturally.

Game tracking: the scoreboard listens for station broadcasts
(plain JSON list: ["turnred", ...]) to detect new games.  A new game
resets the board.  Score messages whose 'colors' list differs from the
current game also trigger a reset.

Expected messages:
  Station → scoreboard (broadcast):
      ["turnred", "turnblue", ...]          <- new game sequence

  Wand → scoreboard (unicast):
      { "type": "score", "colors": [...], "time_ms": 12345, "time_s": 12.35 }
"""

import json
import machine
import network
import neopixel
import espnow
import time
import random
from collections import deque

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATA_PIN    = 0   # A0 on XIAO ESP32-C6 (GPIO0)
NUM_PIXELS  = 40
NUM_BARS    = 4
BAR_HEIGHT  = 10  # pixels per bar (rows)
MIN_ROWS    = 2   # slowest player still gets at least this many rows

# RGB values for each device color name.
COLOR_RGB = {
    "turnblue":   (0,   0,   255),
    "turngreen":  (0,   255, 0),
    "turnpurple": (160, 0,   200),
    "turnred":    (255, 0,   0),
}

BRIGHTNESS_SCALE = 0.8   # Global dimmer (0.0–1.0); tune for the driver board
DEFAULT_RGB      = (120, 120, 120)  # Fallback if color name is unrecognized

# Rainbow colors used for the arrival animation sweep
RAINBOW_ROWS = [
    (255, 0,   0),    # red
    (255, 100, 0),    # orange
    (200, 200, 0),    # yellow
    (0,   255, 0),    # green
    (0,   0,   255),  # blue
    (130, 0,   255),  # purple
]

# Vivid player identity colors — assigned to wand MACs in order of first contact.
# These are intentionally different from the game color names so bars are always
# visually distinct regardless of which game sequence was played.
PLAYER_COLORS = [
    (255,  80,   0),   # orange
    (  0, 220, 220),   # cyan
    (220,   0, 220),   # magenta
    (220, 220,   0),   # yellow
    (  0, 200,  80),   # spring green
    (200,   0,  80),   # crimson
    ( 80, 100, 255),   # periwinkle
    (255, 100, 180),   # pink
]

# ---------------------------------------------------------------------------
# Hardware init
# ---------------------------------------------------------------------------

print("[boot] Initializing NeoPixel strip: pin={}, pixels={}".format(DATA_PIN, NUM_PIXELS))
strip = neopixel.NeoPixel(machine.Pin(DATA_PIN), NUM_PIXELS)
print("[boot] NeoPixel strip ready")

print("[boot] Activating WiFi (STA mode, no connection)")
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
print("[boot] WiFi active, MAC: {}".format(":".join("{:02x}".format(b) for b in wlan.config("mac"))))

print("[boot] Activating ESP-NOW")
en = espnow.ESPNow()
en.active(True)
print("[boot] ESP-NOW ready, waiting for messages")

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

score_queue   = deque((), NUM_BARS)  # each entry: {"player_rgb": tuple, "time_ms": int}
current_game  = None                 # list of color strings for the active game
score_count   = 0                    # total scores received this game; drives color rotation

def reset_for_new_game(new_game):
    """
    Clear the score queue and show a brief wipe animation to signal a fresh game.
    Updates current_game to new_game.
    """
    global score_queue, current_game, score_count
    print("[game] New game sequence: {} (was {})".format(new_game, current_game))
    current_game = new_game
    score_queue  = deque((), NUM_BARS)
    score_count  = 0

    # Quick white pixel-wipe left-to-right then clear — like a chalkboard erase
    for i in range(NUM_PIXELS):
        strip[i] = _scale((200, 200, 200))
        strip.write()
        time.sleep_ms(8)
    time.sleep_ms(120)
    for i in range(NUM_PIXELS):
        strip[i] = (0, 0, 0)
    strip.write()
    print("[game] Score board cleared")


# ---------------------------------------------------------------------------
# Pixel addressing
# ---------------------------------------------------------------------------

def pixel_index(col, row):
    """
    Return the strip pixel index for a given column and row.

    Even columns are wired bottom-to-top (row 0 = first pixel in column).
    Odd columns are wired top-to-bottom (row 0 = last pixel in column).

    Args:
        col: Column index (0-3, left to right).
        row: Row index (0 = bottom, BAR_HEIGHT-1 = top).

    Returns:
        Absolute pixel index in the strip.
    """
    base = col * BAR_HEIGHT
    if col % 2 == 0:
        return base + row
    else:
        return base + (BAR_HEIGHT - 1 - row)

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def _scale(rgb):
    """Apply BRIGHTNESS_SCALE to an RGB tuple."""
    return tuple(int(c * BRIGHTNESS_SCALE) for c in rgb)


def _set_col(col, rgb):
    """Fill an entire column with one color."""
    for row in range(BAR_HEIGHT):
        strip[pixel_index(col, row)] = rgb
    strip.write()


def score_arrival_animation(new_col):
    """
    Four-phase magical arrival animation for a new score.

    Phase 1 — Anticipation sparkles (~450 ms):
        Random gold/white stars pop and fade across the whole strip,
        building excitement while the player's score is about to land.

    Phase 2 — Comet launch (~275 ms):
        A bright white head with a purple-blue trail shoots from the
        bottom of the new column to the top, like a spell being cast.

    Phase 3 — Burst flash (~150 ms):
        The whole column flares white — the moment of impact.

    Phase 4 — Rainbow bloom + hold (~350 ms):
        Each row blooms into a rainbow color from bottom to top,
        then holds briefly before update_display() draws the real bars.
    """
    WHITE  = (255, 255, 255)
    TRAIL1 = ( 80,  30, 220)   # purple-blue mid-trail
    TRAIL2 = ( 25,  10,  70)   # dim tail

    # ── Phase 1: anticipation sparkles ──────────────────────────────────
    for _ in range(9):
        lit = []
        for _ in range(random.randint(3, 6)):
            px = random.randint(0, NUM_PIXELS - 1)
            brightness = random.randint(120, 255)
            strip[px] = _scale((brightness, int(brightness * 0.65), int(brightness * 0.1)))
            lit.append(px)
        strip.write()
        time.sleep_ms(28)
        for px in lit:
            strip[px] = (0, 0, 0)
        time.sleep_ms(22)

    # ── Phase 2: comet shoots up the new column ──────────────────────────
    _set_col(new_col, (0, 0, 0))
    for row in range(BAR_HEIGHT):
        _set_col(new_col, (0, 0, 0))
        strip[pixel_index(new_col, row)] = _scale(WHITE)
        if row >= 1:
            strip[pixel_index(new_col, row - 1)] = _scale(TRAIL1)
        if row >= 2:
            strip[pixel_index(new_col, row - 2)] = _scale(TRAIL2)
        strip.write()
        time.sleep_ms(27)

    # ── Phase 3: full-column burst ───────────────────────────────────────
    _set_col(new_col, _scale(WHITE))
    time.sleep_ms(150)

    # ── Phase 4: rainbow blooms up, row by row, then holds ───────────────
    for row in range(BAR_HEIGHT):
        strip[pixel_index(new_col, row)] = _scale(RAINBOW_ROWS[row % len(RAINBOW_ROWS)])
        strip.write()
        time.sleep_ms(30)
    time.sleep_ms(280)

    # Clear column — update_display() will draw the final proportional bars
    _set_col(new_col, (0, 0, 0))


def update_display():
    """
    Redraw all 4 bar columns from the current score_queue.

    Scaling: fastest score = full bar (BAR_HEIGHT rows).
    All others: proportion = fastest_ms / this_ms  (slower → shorter bar).
    MIN_ROWS guarantees every player has a visible bar.
    """
    for i in range(NUM_PIXELS):
        strip[i] = (0, 0, 0)

    scores = list(score_queue)  # oldest first

    if not scores:
        strip.write()
        print("[display] No scores yet, strip cleared")
        return

    min_time = min(s["time_ms"] for s in scores)   # fastest = reference
    print("[display] Redrawing — {} bars, fastest={}ms".format(len(scores), min_time))

    for col, entry in enumerate(scores):
        time_ms    = entry["time_ms"]
        proportion = min_time / time_ms if time_ms > 0 else 1.0  # faster = bigger
        lit_rows   = max(MIN_ROWS, round(proportion * BAR_HEIGHT))
        rgb        = _scale(entry["player_rgb"])

        print("[display] Col {}: time={}ms, {}/{} rows, proportion={:.2f}, rgb={}".format(
            col, time_ms, lit_rows, BAR_HEIGHT, proportion, rgb))

        for row in range(lit_rows):
            strip[pixel_index(col, row)] = rgb

    strip.write()
    print("[display] Strip written")

# ---------------------------------------------------------------------------
# Message handling
# ---------------------------------------------------------------------------

def _handle_station_broadcast(mac, color_list):
    """
    Called when the station broadcasts a new game sequence.
    Any station broadcast means a new game is starting — always reset.
    """
    valid = [c for c in color_list if c in COLOR_RGB]
    if not valid:
        print("[station] Broadcast contains no recognised color names, ignoring")
        return
    mac_str = ":".join("{:02x}".format(b) for b in mac)
    print("[station] New game from {}: {}".format(mac_str, valid))
    reset_for_new_game(valid)


def _handle_score(mac, data):
    """
    Called when a wand sends a completed-game score message.
    Each score gets the next color in PLAYER_COLORS regardless of sender —
    same wand submitting again (retry or shared between kids) just gets the
    next color in the rotation naturally.
    """
    global current_game, score_count

    colors  = data.get("colors")
    time_ms = data.get("time_ms")
    time_s  = data.get("time_s")

    if not colors or time_ms is None:
        print("[score] ERROR: Missing 'colors' or 'time_ms', ignoring")
        return

    # Detect a game change (station broadcast may have been missed)
    if current_game is not None and colors != current_game:
        print("[score] Game sequence changed, resetting board")
        reset_for_new_game(colors)
    elif current_game is None:
        current_game = colors
        print("[score] First score — game sequence set: {}".format(current_game))

    player_rgb  = PLAYER_COLORS[score_count % len(PLAYER_COLORS)]
    score_count += 1
    entry = {"player_rgb": player_rgb, "time_ms": time_ms}

    # deque drops oldest automatically when full (FIFO)
    score_queue.append(entry)
    new_col = len(score_queue) - 1

    mac_str = ":".join("{:02x}".format(b) for b in mac)
    print("[score] #{} from {}: time={}ms ({:.2f}s), color={}, depth={}".format(
        score_count, mac_str, time_ms, time_s or time_ms / 1000, player_rgb, len(score_queue)))

    score_arrival_animation(new_col)
    update_display()


def handle_message(mac, msg_bytes):
    """Route an incoming ESP-NOW message to the appropriate handler."""
    mac_str = ":".join("{:02x}".format(b) for b in mac)
    print("[recv] From {}: {}".format(mac_str, msg_bytes))

    try:
        data = json.loads(msg_bytes)
    except ValueError:
        print("[recv] ERROR: Could not parse JSON, ignoring")
        return

    if isinstance(data, list):
        # Plain list → station broadcast of a new game sequence
        _handle_station_broadcast(mac, data)
        return

    if not isinstance(data, dict):
        print("[recv] Unexpected JSON type ({}), ignoring".format(type(data).__name__))
        return

    msg_type = data.get("type")
    if msg_type == "score":
        _handle_score(mac, data)
    else:
        print("[recv] Unknown message type '{}', ignoring".format(msg_type))

# ---------------------------------------------------------------------------
# Startup animation
# ---------------------------------------------------------------------------

def startup_animation():
    """
    Test animation run once at boot to verify strip wiring and color mapping.

    Sequence:
      1. Sweep each pixel on one at a time (white) from pixel 0 to 39.
      2. Flash each device color across the full strip once.
      3. Clear the strip.
    """
    print("[anim] Starting startup animation")
    SWEEP_DELAY  = 0.03   # seconds per pixel during sweep
    FLASH_DELAY  = 0.3    # seconds per color flash
    SWEEP_RGB    = _scale((80, 80, 80))

    # Phase 1: pixel sweep
    print("[anim] Phase 1: pixel sweep")
    for i in range(NUM_PIXELS):
        strip[i] = SWEEP_RGB
        strip.write()
        time.sleep(SWEEP_DELAY)

    # Brief pause at full strip
    time.sleep(0.2)

    # Phase 2: full-strip color flash for each device color
    print("[anim] Phase 2: color flash")
    for color_name, rgb in COLOR_RGB.items():
        scaled = _scale(rgb)
        print("[anim] Flashing: {}  rgb={}".format(color_name, scaled))
        for i in range(NUM_PIXELS):
            strip[i] = scaled
        strip.write()
        time.sleep(FLASH_DELAY)

    # Phase 3: clear
    for i in range(NUM_PIXELS):
        strip[i] = (0, 0, 0)
    strip.write()
    print("[anim] Startup animation complete")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

startup_animation()
update_display()  # Clear strip and confirm clean state before receiving
print("[main] Entering receive loop")

while True:
    mac, msg = en.recv()
    if msg:
        handle_message(mac, msg)