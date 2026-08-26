# Slide Score Station

A wireless scoreboard that receives ESP-NOW messages and displays the last 4 player scores as a proportional bar graph on a 40-pixel NeoPixel strip.

## What It Does

The scoreboard listens for two types of ESP-NOW messages: game sequences from the programming station (which reset the board for a new round) and score submissions from wand modules (which add a new bar to the graph). The fastest player always gets a full-height bar, and all other bars scale down proportionally — so kids can see at a glance who was quickest. When a new score arrives, a multi-phase magical animation plays before the bar graph redraws.

## How It Works

### Hardware

Minimal wiring — just a NeoPixel strip connected to one GPIO:

```
ESP32-C6
   └── GPIO0 (A0) ── 40-LED NeoPixel strip DIN
```

The 40 pixels are physically arranged as a **serpentine 4×10 grid** (4 columns, 10 rows), viewed from the front:

```
  row 9 (top)     ↑col0  ↓col1  ↑col2  ↓col3
  ...
  row 0 (bottom)
```

Even columns (0, 2) are wired bottom-to-top. Odd columns (1, 3) are wired top-to-bottom. The `pixel_index(col, row)` function handles this mapping so the rest of the code can think in terms of column/row coordinates.

### Boot Sequence

1. Initialize the 40-pixel NeoPixel strip on GPIO0.
2. Activate WiFi in STA mode (required for ESP-NOW, but no actual WiFi connection is made).
3. Activate ESP-NOW and begin listening for messages.
4. Run a startup animation: white pixel sweep across all 40 LEDs, then flash each game color (red, green, purple, blue) across the full strip.
5. Enter the receive loop.

### Message Handling

The scoreboard receives and routes two types of JSON messages:

**Station broadcast** — a plain JSON array like `["turnred", "turnblue"]`. This signals a new game is starting. The scoreboard clears all scores, resets the color rotation counter, and plays a white pixel-wipe animation. Any station broadcast always triggers a reset, even if the game sequence hasn't changed.

**Wand score message** — a JSON object with `"type": "score"`:

```json
{
  "type": "score",
  "colors": ["turnred", "turnblue"],
  "time_ms": 14230,
  "time_s": 14.23
}
```

When a score arrives, the scoreboard checks whether the game sequence matches the current game. If it doesn't (and the station broadcast was missed), the board resets automatically before recording the new score. The score is then added to a FIFO queue that holds the last 4 entries — when a 5th score arrives, the oldest one drops off.

### Bar Graph Display

Each of the 4 columns represents one score, filled left-to-right in arrival order. Bar height is proportional to speed:

- The **fastest** time in the current set always gets the full 10-row bar.
- All other bars scale as `fastest_ms / this_ms` — so a player who took twice as long gets half the bar height.
- A minimum of 2 rows (`MIN_ROWS`) ensures even the slowest player has a visible bar.
- When a new fastest time arrives, **all bars rescale live** — kids can watch the leaderboard shift.

### Bar Colors

Each score gets the next color from a rotating palette of 8 vivid colors, regardless of which wand sent it. This means the same wand submitting again (retry or shared between kids) simply gets the next color. Colors reset at the start of each new game.

| # | Color | RGB |
|---|---|---|
| 1 | Orange | (255, 80, 0) |
| 2 | Cyan | (0, 220, 220) |
| 3 | Magenta | (220, 0, 220) |
| 4 | Yellow | (220, 220, 0) |
| 5 | Spring green | (0, 200, 80) |
| 6 | Crimson | (200, 0, 80) |
| 7 | Periwinkle | (80, 100, 255) |
| 8 | Pink | (255, 100, 180) |

These colors are intentionally different from the game color names (turnred, turnblue, etc.) so bars are always visually distinct regardless of which color sequence was played.

### Score Arrival Animation

When a new score is added, a four-phase animation plays on the new column before the bar graph redraws:

1. **Anticipation sparkles (~450ms)** — random gold/white stars pop and fade across the whole strip, building excitement.
2. **Comet launch (~275ms)** — a bright white head with a purple-blue trail shoots from the bottom of the new column to the top.
3. **Burst flash (~150ms)** — the entire column flares white at the moment of impact.
4. **Rainbow bloom (~350ms)** — each row lights up in a rainbow color from bottom to top, then holds briefly before the final proportional bar graph is drawn.

### Brightness

All colors are scaled by `BRIGHTNESS_SCALE = 0.8` to keep the strip from being blinding at close range. Adjust this value (0.0–1.0) to suit your environment.

## Dependencies

None. The scoreboard is fully self-contained — it uses only built-in MicroPython modules (`json`, `machine`, `network`, `neopixel`, `espnow`, `time`, `random`, `collections`). No `/lib/` files are required.

## Deployment

1. Copy `main.py` to the root of the device.
2. Power on — the startup animation confirms the strip is wired correctly, then the board begins listening for ESP-NOW messages.
3. No configuration needed. The scoreboard listens for broadcasts from any sender.

## Design Notes

- The scoreboard is designed for obstacle course times roughly in the **30 second – 3 minute** range. Very short times (under a second) or very long times (over 10 minutes) will still work but the bar proportions may be less visually meaningful.
- The `deque` with `maxlen=4` handles the FIFO behavior automatically — no manual eviction logic needed.
- The serpentine pixel mapping means physical wiring is a simple continuous strip folded back and forth, while the code addresses pixels by logical (column, row) coordinates.
