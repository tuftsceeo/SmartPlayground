"""
config.py -- pin map, zone definitions, tuning thresholds for the Radar
Station.

Coordinate system: mm, sensor/station frame, +x right, +y forward.
"""

# Board: Seeed XIAO ESP32-C6. Sensor on D6/D7 = GPIO16/GPIO17.
# UART_ID=1 (not 0, GPIO16/17's IO_MUX default) to avoid UART0.
# tx=16 drives LD2450 RX; rx=17 reads LD2450 TX.
UART_ID = 1
UART_TX = 16
UART_RX = 17
UART_BAUD = 256000

# LD2450 x/y/speed are sign-magnitude, not two's complement. Flip if the
# mounting reverses left/right or forward/back.
SIGN_X = 1
SIGN_Y = 1

# Tracker association gate radius, mm. Max distance a target may move
# between frames (100ms @ 10Hz) and still match the same track.
TRACK_GATE_MM = 400

# Frames a track survives with no matching detection before it's dropped.
TRACK_MAX_MISSES = 3

# EMA smoothing factor for track position. 0 = no smoothing, 1 = frozen.
# Low by default: x/y come off the sensor already tracked/filtered
# on-board, and derived ground speed differentiates this value again --
# smoothing on top of both compounds lag. Live-tunable; raise it back up
# from the Tuning panel if raw position proves too jittery in practice.
TRACK_SMOOTH_ALPHA = 0.1

# Speed-bucket thresholds, mm/s, on tracker ground speed. Below
# SPEED_WALK_MM_S already is the still/moving dead zone -- widen it live
# from the Tuning panel if standing-still noise flickers into "walk".
# Sized against real human paces, not guessed: 5-year-olds walk
# ~800-900, run ~2000-2500; teens' walk ranges leisurely-to-power-walk
# ~1100-2012, jog/run ~3000. 1800 sits above every walking pace in that
# range (even a brisk power-walk) and below both age groups' running
# speeds. 250 is a starting hedge against sensor noise at rest, not a
# measured floor -- lower it live once a real still-person test shows
# the actual noise floor is smaller.
SPEED_WALK_MM_S = 250    # < this: still
SPEED_RUN_MM_S = 1800    # >= this: run; between: walk

# Radial speed dead zone, cm/s, for approach/recede/stationary
# classification. Below this magnitude a target counts as stationary
# rather than approaching or receding -- absorbs sensor noise around
# zero for someone standing still.
RADIAL_STATIONARY_CM_S = 5

# Named rectangles in the station frame (mm), for events.py zone counts.
ZONES = {
    "near": {"x0": -3000, "x1": 3000, "y0": 0, "y1": 2000},
    "far": {"x0": -3000, "x1": 3000, "y0": 2000, "y1": 6000},
}

# Consecutive empty frames required before `present` flips to False.
PRESENCE_DROP_FRAMES = 5
