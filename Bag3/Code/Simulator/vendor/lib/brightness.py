"""
brightness.py — system-wide LED brightness multiplier driven by ambient light.

On boot, main.py calls calibrate(opt3002) which reads the OPT3002 light sensor
and sets the global MULTIPLIER (0.0 to 1.0). Every NeoPixel write through
leds.py is automatically scaled by this value, so all files (freeze_dance,
color_quest, gesture engine, action runner, etc.) auto-adapt.

PRIMARY MECHANISM: leds.Leds wraps its NeoPixel in _ScaledNeoPixel. Code that
writes via `leds.np[i] = (r, g, b)` or `leds.solid(r, g, b)` is scaled
automatically. You do not need to call scale() yourself — the wrapper does it.

ESCAPE HATCH: scale(r, g, b) is provided for code that bypasses the wrapper
(e.g., a raw NeoPixel created directly without going through Leds). DO NOT
call scale() on values that are then written through leds.np — that would
double-scale.

Usage:
    import brightness
    brightness.calibrate(opt3002_instance)         # set MULTIPLIER from sensor
    brightness.set_multiplier(0.4)                  # manual override
    print(brightness.MULTIPLIER, brightness.LAST_LUX)

    # Only when bypassing the wrapper:
    r, g, b = brightness.scale(200, 200, 0)
    raw_neopixel[i] = (r, g, b)

Devices without an OPT3002 (programming station, score board, splat companion)
just leave MULTIPLIER at its default of 1.0 — no behavior change.

Lux → multiplier mapping (log scale):
    < 32 lux       (pitch dark)        → 0.15
    100 lux        (dim indoor)        → 0.32
    500 lux        (bright indoor)     → 0.55
    2000 lux       (overcast outdoor)  → 0.76
    10000+ lux     (sunlight)          → 1.00

Tuning lives in this file — see MIN_MULT / MAX_MULT / LOG_LUX_* below.
"""

import math
import time

# ── Public state ──────────────────────────────────────────
MULTIPLIER = 1.0    # default = no scaling. Devices without a light sensor stay here.
LAST_LUX   = None   # last lux reading from calibrate(); None if never calibrated.

# ── Tuning ────────────────────────────────────────────────
MIN_MULT = 0.05     # floor — any indoor light lands here (~10/255 for a source-200 color)
MAX_MULT = 0.50     # ceiling — direct sunlight (~100/255 for a source-200 color)

# Log-scale lux endpoints. Below LOG_LUX_MIN clamps to MIN_MULT,
# above LOG_LUX_MAX clamps to MAX_MULT, linear-in-log between.
LOG_LUX_MIN = 2.7   # log10(500) — typical bright indoor; any indoor stays at floor
LOG_LUX_MAX = 4.0   # log10(10000) — sunlight

# Calibration sample count + spacing
CAL_SAMPLES   = 3
CAL_DELAY_MS  = 120


def _lux_to_mult(lux):
    """Map a lux reading to a multiplier in [MIN_MULT, MAX_MULT]."""
    if lux <= 0:
        return MIN_MULT
    log_lux = math.log10(lux)
    if log_lux <= LOG_LUX_MIN:
        return MIN_MULT
    if log_lux >= LOG_LUX_MAX:
        return MAX_MULT
    t = (log_lux - LOG_LUX_MIN) / (LOG_LUX_MAX - LOG_LUX_MIN)
    return MIN_MULT + t * (MAX_MULT - MIN_MULT)


def calibrate(opt3002):
    """
    Take a few lux readings from the OPT3002 and set MULTIPLIER from the median.
    Returns (multiplier, lux) on success, or (MULTIPLIER, None) if all reads failed.

    Robust to a flaky sensor: bad reads are skipped, median rejects single outliers.
    Never raises — falls back to current MULTIPLIER if everything fails.
    """
    global MULTIPLIER, LAST_LUX

    readings = []
    for _ in range(CAL_SAMPLES):
        try:
            readings.append(opt3002.lux)
        except Exception:
            pass
        time.sleep_ms(CAL_DELAY_MS)

    if not readings:
        return MULTIPLIER, None

    readings.sort()
    lux = readings[len(readings) // 2]   # median
    MULTIPLIER = _lux_to_mult(lux)
    LAST_LUX = lux
    return MULTIPLIER, lux


def set_multiplier(value):
    """Manual override. Clamped to [0.05, 1.0]. Returns the clamped value."""
    global MULTIPLIER
    MULTIPLIER = max(0.05, min(1.0, value))
    return MULTIPLIER


def get_multiplier():
    """Convenience getter."""
    return MULTIPLIER


def get_lux():
    """Last lux reading from calibrate(), or None if uncalibrated."""
    return LAST_LUX


def scale(r, g, b):
    """
    Manually scale a color triple by MULTIPLIER. Returns (r', g', b') as ints.

    USE ONLY when writing to a NeoPixel that is NOT wrapped by leds.py
    (e.g., a raw NeoPixel you constructed directly). Code writing through
    leds.np gets automatic scaling and must NOT call this — double-scaling
    will result.
    """
    m = MULTIPLIER
    sr = int(r * m); sr = 0 if sr < 0 else (255 if sr > 255 else sr)
    sg = int(g * m); sg = 0 if sg < 0 else (255 if sg > 255 else sg)
    sb = int(b * m); sb = 0 if sb < 0 else (255 if sb > 255 else sb)
    return (sr, sg, sb)