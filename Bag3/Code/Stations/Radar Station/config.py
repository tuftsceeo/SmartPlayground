"""
config.py -- pin map, zone definitions, and tuning thresholds for the Radar
Station. Single source of truth for numbers the rest of the tree shouldn't
hardcode. See the top-level plan for how these were chosen; most of the
thresholds here are placeholders until Gate A/B traces are in hand -- see
each value's comment for what evidence should adjust it.

Coordinate system: mm, sensor/station frame, +x right, +y forward (away
from the sensor), matching the LD2450's own convention (to be confirmed at
Gate A step 5 -- flip SIGN_X / SIGN_Y below if the sensor disagrees).
"""

# ---- UART wiring -----------------------------------------------------
# Board: Seeed XIAO ESP32-C6 on a Seeed expansion board. Sensor wired to
# the pins silkscreened D6/D7 (GPIO16/GPIO17), the SoC's default UART0
# pins ("U0TXD"/"U0RXD" per Espressif's IO_MUX naming) -- but MicroPython
# on this chip runs its REPL over the native USB-Serial-JTAG peripheral,
# not a UART, so GPIO16/17 should be free to claim as a plain machine.UART
# instance. UART_ID=1 rather than 0 deliberately: the ESP32 GPIO matrix
# lets any UART peripheral route to any GPIO pair, and staying off UART0
# avoids any chance of colliding with a system use of it -- confirm at
# Gate A that this actually claims the pins and the REPL keeps working.
# tx=16 is the SoC's own TX (drives LD2450 RX); rx=17 is the SoC's own RX
# (reads LD2450 TX) -- i.e. wires cross between the two boards as usual.
UART_ID = 1
UART_TX = 16
UART_RX = 17
UART_BAUD = 256000

# ---- sign convention --------------------------------------------------
# LD2450 encodes x/y/speed as sign-magnitude (MSB = sign flag over a
# 15-bit magnitude), not two's complement. SIGN_X / SIGN_Y let Gate A's
# four-direction walk correct the axis directions without touching the
# decoder if the physical mounting flips left/right or forward/back.
SIGN_X = 1
SIGN_Y = 1

# ---- tracker ------------------------------------------------------
# Association gate radius in mm: how far a target can move between two
# consecutive frames (100ms apart at 10Hz) and still count as the same
# person. ~400mm covers a sprinting child; tighten if Gate B shows two
# people's tracks merging, loosen if one person's track keeps splitting.
TRACK_GATE_MM = 400

# Frames a track survives with no matching detection before it's dropped.
# At 10Hz, 3 frames = 300ms -- long enough to ride out a single dropped
# frame or a momentary occlusion without a game seeing a fresh ID.
TRACK_MAX_MISSES = 3

# EMA smoothing factor for position (0 = no smoothing/all new sample,
# 1 = frozen). Start light; increase if Gate B traces look jittery.
TRACK_SMOOTH_ALPHA = 0.35

# ---- speed thresholds (mm/s), applied to tracker ground speed --------
# Placeholders -- set these from Gate B's walking/running JSONL traces
# rather than guessing further.
SPEED_WALK_MM_S = 400   # below this: "still"
SPEED_RUN_MM_S = 1200   # at/above this: "run"; between the two: "walk"

# ---- zones -------------------------------------------------------
# Named rectangles in the station frame (mm), used by events.py for
# per-zone presence counts. Placeholder single zone spanning the
# sensor's nominal 6m range and +-60 deg azimuth at 6m (~10.4m wide);
# replace with real geometry once the station's mounting is fixed.
ZONES = {
    "near": {"x0": -3000, "x1": 3000, "y0": 0, "y1": 2000},
    "far": {"x0": -3000, "x1": 3000, "y0": 2000, "y1": 6000},
}

# ---- presence hysteresis --------------------------------------------
# Consecutive empty frames required before "present" flips to False, to
# avoid presence flapping on a single missed detection.
PRESENCE_DROP_FRAMES = 5
