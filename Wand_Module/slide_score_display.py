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

Bar fill: proportional to time_ms relative to the maximum among the
last 4 received scores. Longer time = taller bar. Bars are assigned
left-to-right in arrival order; the oldest score is replaced when a
5th score arrives.

Expected message JSON:
    { "type": "score", "colors": ["turnred", ...], "time_ms": 12345, "time_s": 12.35 }

colors[0] is used as the bar color. time_ms is used for bar height.
"""

import json
import machine
import network
import neopixel
import espnow
import time
from collections import deque

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATA_PIN    = 0   # A0 on XIAO ESP32-C6 (GPIO0)
NUM_PIXELS  = 40
NUM_BARS    = 4
BAR_HEIGHT  = 10  # pixels per bar (rows)

# RGB values for each device color name.
# Kept intentionally dim to avoid current draw issues on the LED driver board.
COLOR_RGB = {
    "turnblue":   (0,   0,   160),
    "turngreen":  (0,   160, 0),
    "turnpurple": (100, 0,   120),
    "turnred":    (160, 0,   0),
}

BRIGHTNESS_SCALE = 0.5   # Global dimmer (0.0–1.0); tune for the driver board
DEFAULT_RGB      = (80, 80, 80)  # Fallback if color name is unrecognized

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
# State: ring buffer of the last NUM_BARS scores
# Each entry: { "color": str, "time_ms": int }
# ---------------------------------------------------------------------------

score_queue = deque((), NUM_BARS)   # oldest on left, newest on right

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


def update_display():
    """Redraw all 4 bar columns from the current score_queue."""
    # Clear the full strip first.
    for i in range(NUM_PIXELS):
        strip[i] = (0, 0, 0)

    scores = list(score_queue)  # oldest first

    if not scores:
        strip.write()
        print("[display] No scores yet, strip cleared")
        return

    max_time = max(s["time_ms"] for s in scores)
    print("[display] Redrawing — {} bars, max_time={}ms".format(len(scores), max_time))

    for col, entry in enumerate(scores):
        color_name = entry["color"]
        time_ms    = entry["time_ms"]
        proportion = time_ms / max_time if max_time > 0 else 0
        lit_rows   = max(1, round(proportion * BAR_HEIGHT))
        rgb        = _scale(COLOR_RGB.get(color_name, DEFAULT_RGB))

        print("[display] Col {}: color={}, time={}ms, {}/{} rows, proportion={:.2f}, rgb={}".format(
            col, color_name, time_ms, lit_rows, BAR_HEIGHT, proportion, rgb))

        for row in range(lit_rows):
            strip[pixel_index(col, row)] = rgb

    strip.write()
    print("[display] Strip written")

# ---------------------------------------------------------------------------
# Message handling
# ---------------------------------------------------------------------------

def handle_message(mac, msg_bytes):
    """Parse a raw ESP-NOW payload and update the score queue if it is a score message."""
    mac_str = ":".join("{:02x}".format(b) for b in mac)
    print("[recv] Message from {}: {}".format(mac_str, msg_bytes))

    try:
        data = json.loads(msg_bytes)
    except ValueError:
        print("[recv] ERROR: Could not parse JSON, ignoring")
        return

    if not isinstance(data, dict):
        print("[recv] Ignoring non-object JSON (got {}): {}".format(type(data).__name__, data))
        return

    msg_type = data.get("type")
    if msg_type != "score":
        print("[recv] Ignoring message type: '{}'".format(msg_type))
        return

    colors  = data.get("colors")
    time_ms = data.get("time_ms")
    time_s  = data.get("time_s")

    if not colors or time_ms is None:
        print("[recv] ERROR: Missing 'colors' or 'time_ms' fields, ignoring")
        return

    device_color = colors[0]  # First entry is this device's color identifier
    entry = {"color": device_color, "time_ms": time_ms}

    # deque with maxlen drops the oldest entry automatically when full.
    score_queue.append(entry)

    print("[recv] Score queued: color='{}', time={}ms ({:.2f}s), queue depth={}".format(
        device_color, time_ms, time_s or time_ms / 1000, len(score_queue)))
    print("[recv] Current queue: {}".format(list(score_queue)))

    update_display()

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