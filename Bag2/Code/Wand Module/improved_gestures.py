"""
Improved Gestures - Few-Shot Gesture Recognition for Kindergartners
====================================================================
Tap the "gestures2" NFC tag to enter. Scan RED / GREEN / BLUE to pick a
training class, hold the button while performing a gesture. Scan PLAY to
test: hold the button to classify against trained gestures.

Design notes for this implementation:
- Features built from the gravity-vector trajectory in the sensor frame
  (orientation reference), not raw axis values. This is robust to small
  wrist-roll variation (~+/-15 deg) which the wand's grip affordances
  enforce, while still discriminating large arm-arc gestures.
- Angle-from-start of the gravity vector is the headline feature: it is
  invariant to wrist roll about the wand's long axis, and tracks gross-
  motor arm sweeps (e.g. point-down -> point-up = 180 deg) directly.
- Rotation axis captures the plane of motion (up-down vs left-right).
- High-frequency motion (raw accel minus low-pass-filtered gravity) gives
  intensity, tempo, and shape of sharp accelerations within the gesture.
- All DTW workspace pre-allocated in the game class to avoid heap
  fragmentation across repeated classifications.

In-game NFC tags: red, green, blue, play, stop

Entry points:
    play(nfc, leds, buz, accel, i2c, enow)  - called from main.py
    main()                                   - standalone testing
"""

import gc
import math
import machine
import time
from machine import Pin

from pn532 import PN532
from nfc_reader import NfcReader
from leds import (
    RED, GREEN, BLUE, WHITE, WHITE_DIM, ORANGE_DIM, OFF,
    SHAPE_DIAMOND, SHAPE_POWER, SHAPE_STAR,
)

# --- Hardware Config (standalone main only) ---
I2C_SDA, I2C_SCL = 22, 23
BUZZER_PIN, BUTTON_PIN, PN532_ADDR = 19, 0, 0x24

# --- Game Config ---
NUM_LEDS = 25
NFC_POLL_INTERVAL = 10
LOOP_DELAY_MS = 20
DEBOUNCE_MS = 60
MIN_HOLD_MS = 200            # pre-roll for gravity filter warm-up
POST_RELEASE_LOCKOUT_MS = 500
SAMPLE_INTERVAL_MS = 10      # 100 Hz sampling
MAX_CAPTURE_SAMPLES = 250    # up to 2.5 s; tolerates longer holds
MAX_TRAINING_SAMPLES = 6     # exemplar cap for confirmation voting

# --- Feature Config ---
TRACE_LEN = 8                # DTW trace length (angle and motion)
DTW_WINDOW = 2               # Sakoe-Chiba band radius

# Gravity IIR filter coefficient. At 100 Hz sampling, alpha=0.9 gives a
# ~1.7 Hz cutoff, which tracks slow wand rotation but rejects gesture-
# scale linear accelerations. Kindergartner gross-motor gestures peak
# at 1-3 Hz, so this is conservative.
GRAVITY_ALPHA = 0.9

# Adaptive trim: include samples whose motion magnitude exceeds a fraction
# of the per-capture peak. This handles slow gentle gestures gracefully.
TRIM_REL_THRESHOLD = 0.25
TRIM_ABS_FLOOR = 0.04        # in g; absolute lower bound for noise
TRIM_PAD_SAMPLES = 6         # padding samples on each side of active region

# Soft-similarity tolerance windows
INTENSITY_TOL_G = 0.25       # avg motion intensity tolerance (g units)
ROTATION_TOL_RAD = 1.5       # ~86 deg tolerance for total rotation

# Peak detection (for tempo / peaks-per-second feature). Peaks must be
# above a height floor and separated by a refractory period to suppress
# noise-driven double-counting. The height floor adapts to the gesture's
# own peak so gentle gestures still register tempo.
PEAK_MIN_HEIGHT = 0.06       # absolute floor (g)
PEAK_REL_FRACTION = 0.35     # fraction of gesture peak motion
PEAK_REFRACTORY_MS = 100     # minimum spacing between peaks

# Confidence floor for "?" response in play mode
CONFIDENCE_FLOOR = 0.45

COMMANDS = {"red", "green", "blue", "play", "stop"}

COLOR_BY_NAME = {
    "red": RED,
    "green": GREEN,
    "blue": BLUE,
}

SHAPE_BY_NAME = {
    "red": SHAPE_DIAMOND,
    "green": SHAPE_POWER,
    "blue": SHAPE_STAR,
}

# --- Sound Sequences ---
SOUNDS = {
    'start': [(440, 80, 40), (554, 80, 40), (659, 80, 40), (880, 120, 0)],
    'train_select': [(880, 80, 0)],
    'play_select': [(523, 60, 30), (784, 60, 0)],
    'record_start': [(1000, 50, 0)],
    'train_success': [(1400, 70, 30), (1700, 90, 0)],
    'classify_high': [(1500, 160, 0)],
    'classify_low': [(400, 180, 0)],
    'too_short': [(350, 180, 0)],
}

# --- LED Patterns ---
QUESTION_MARK = [0, 1, 2, 3, 4, 9, 12, 17, 22]
BORDER_INDICES = (0, 1, 2, 3, 4, 5, 9, 10, 14, 15, 19, 20, 21, 22, 23, 24)
PERIMETER = [0, 1, 2, 3, 4, 9, 14, 19, 24, 23, 22, 21, 20, 15, 10, 5]
LED_FILL_ORDER = [
    12,
    7, 11, 13, 17,
    6, 8, 16, 18,
    2, 10, 14, 22,
    1, 3, 5, 9, 15, 19, 21, 23,
    0, 4, 20, 24,
]


def _play_sound(buz, name):
    """Play a named sound sequence on the buzzer."""
    for freq, dur, gap in SOUNDS.get(name, []):
        buz.beep(freq, dur)
        if gap:
            time.sleep_ms(gap)


# ============================================================
# SAMPLE RING BUFFER
# ============================================================
class _SampleRing:
    """Fixed-size ring buffer for accelerometer samples."""
    __slots__ = ('size', 'buf', 'idx', 'count')

    def __init__(self, size):
        self.size = size
        self.buf = [None] * size
        self.idx = 0
        self.count = 0

    def push(self, item):
        self.buf[self.idx] = item
        self.idx = (self.idx + 1) % self.size
        if self.count < self.size:
            self.count += 1

    def get_all(self):
        if self.count < self.size:
            return self.buf[:self.count]
        return self.buf[self.idx:] + self.buf[:self.idx]

    def clear(self):
        for i in range(self.size):
            self.buf[i] = None
        self.idx = 0
        self.count = 0


# ============================================================
# LED DISPLAY HELPERS
# ============================================================
def _off(np):
    for i in range(NUM_LEDS):
        np[i] = OFF
    np.write()


def _set_all(np, color):
    for i in range(NUM_LEDS):
        np[i] = color
    np.write()


def _set_border(np, color):
    for i in range(NUM_LEDS):
        np[i] = color if i in BORDER_INDICES else OFF
    np.write()


def _pulse_border(np, color, frame):
    wave = frame % 20
    if wave > 10:
        wave = 20 - wave
    scale = 0.20 + (wave / 10.0) * 0.80
    scaled = (int(color[0] * scale), int(color[1] * scale), int(color[2] * scale))
    _set_border(np, scaled)


def _spin_border(np, color, frame):
    for i in range(NUM_LEDS):
        np[i] = OFF
    pos = frame % len(PERIMETER)
    for i, idx in enumerate(PERIMETER):
        dist = abs(i - pos)
        wrap = len(PERIMETER) - dist
        if dist == 0:
            np[idx] = color
        elif dist == 1 or wrap == 1:
            np[idx] = (color[0] // 3, color[1] // 3, color[2] // 3)
    np.write()


def _flash(np, color, times=2, on_ms=120, off_ms=80):
    for _ in range(times):
        _set_all(np, color)
        time.sleep_ms(on_ms)
        _off(np)
        time.sleep_ms(off_ms)


# ============================================================
# SIGNAL PROCESSING UTILITIES
# ============================================================
def _resample_linear(values, out_len):
    """Resample a 1-D sequence to out_len points by linear interpolation."""
    n = len(values)
    if n == 0:
        return [0.0] * out_len
    if n == 1:
        return [values[0]] * out_len
    result = [0.0] * out_len
    for i in range(out_len):
        # Map output index i to input position
        pos = i * (n - 1) / (out_len - 1)
        lo = int(pos)
        hi = lo + 1
        if hi >= n:
            result[i] = values[n - 1]
        else:
            frac = pos - lo
            result[i] = values[lo] * (1.0 - frac) + values[hi] * frac
    return result


# ============================================================
# FEATURE EXTRACTION
# ============================================================
def _extract_features(samples):
    """
    Extract gravity-trajectory-based features from a raw accelerometer
    sample sequence.

    Pipeline:
      1. Run a one-pole IIR low-pass filter, seeded from the first few
         samples, to estimate the gravity vector at each timestep.
      2. Subtract filtered gravity from raw to get high-frequency motion.
      3. Trim leading/trailing silent regions using an adaptive motion
         threshold (handles slow-gentle gestures).
      4. Compute the angle of each filtered gravity vector from the start
         gravity vector. This is the orientation-invariant trace.
      5. Compute the mean rotation axis (start cross current, time-averaged).
      6. Compute high-frequency motion magnitude trace and tempo features.

    Returns a feature dict, or None if the gesture was too short/still.
    """
    if len(samples) < 8:
        return None

    n_raw = len(samples)

    # --- 1. Seed gravity from first ~5 samples (the MIN_HOLD pre-roll
    # gives time for grip to settle before recording begins). ---
    seed_n = min(5, n_raw)
    seed_sum = [0.0, 0.0, 0.0]
    for i in range(seed_n):
        s = samples[i]
        seed_sum[0] += s[0]
        seed_sum[1] += s[1]
        seed_sum[2] += s[2]
    g_x = seed_sum[0] / seed_n
    g_y = seed_sum[1] / seed_n
    g_z = seed_sum[2] / seed_n

    # --- 2. Single pass: IIR filter, motion magnitude, store filtered
    # gravity unit vectors. Avoid keeping full filtered/motion lists where
    # possible to limit allocation. ---
    alpha = GRAVITY_ALPHA
    one_minus_alpha = 1.0 - alpha

    # Filtered gravity unit vectors per sample (we need these later for
    # angle trace and rotation axis). Keep as flat list of floats to
    # reduce tuple-allocation overhead: [gx0,gy0,gz0, gx1,gy1,gz1, ...].
    g_flat = [0.0] * (n_raw * 3)
    motion_mag = [0.0] * n_raw

    for i in range(n_raw):
        s = samples[i]
        g_x = alpha * g_x + one_minus_alpha * s[0]
        g_y = alpha * g_y + one_minus_alpha * s[1]
        g_z = alpha * g_z + one_minus_alpha * s[2]
        # Normalize gravity for this sample
        gn = (g_x * g_x + g_y * g_y + g_z * g_z) ** 0.5
        if gn > 1e-6:
            base = i * 3
            g_flat[base] = g_x / gn
            g_flat[base + 1] = g_y / gn
            g_flat[base + 2] = g_z / gn
        # Motion = raw minus filtered gravity (use raw, not normalized)
        mx = s[0] - g_x
        my = s[1] - g_y
        mz = s[2] - g_z
        motion_mag[i] = (mx * mx + my * my + mz * mz) ** 0.5

    # --- 3. Adaptive trim: find peak motion, use relative threshold ---
    peak_motion = 0.0
    for m in motion_mag:
        if m > peak_motion:
            peak_motion = m

    threshold = max(TRIM_ABS_FLOOR, TRIM_REL_THRESHOLD * peak_motion)

    start, end = 0, n_raw - 1
    while start < n_raw and motion_mag[start] < threshold:
        start += 1
    while end > start and motion_mag[end] < threshold:
        end -= 1

    if start >= n_raw or (end - start) < 6:
        # No real motion found
        return None

    # Pad context
    if start > TRIM_PAD_SAMPLES:
        start -= TRIM_PAD_SAMPLES
    else:
        start = 0
    if end < n_raw - 1 - TRIM_PAD_SAMPLES:
        end += TRIM_PAD_SAMPLES
    else:
        end = n_raw - 1

    n = end - start + 1
    if n < 6:
        return None

    # --- 4. Angle-from-start trace ---
    # Start gravity = filtered gravity at trim start (unit vector)
    s_base = start * 3
    g0x = g_flat[s_base]
    g0y = g_flat[s_base + 1]
    g0z = g_flat[s_base + 2]

    # Compute angle (radians) for every sample in the trim region.
    # acos(dot) with clamping. Result is in [0, pi].
    angle_full = [0.0] * n
    for i in range(n):
        base = (start + i) * 3
        dot = g0x * g_flat[base] + g0y * g_flat[base + 1] + g0z * g_flat[base + 2]
        if dot > 1.0:
            dot = 1.0
        elif dot < -1.0:
            dot = -1.0
        angle_full[i] = math.acos(dot)

    # Total rotation (max angle seen from start)
    total_rotation = 0.0
    for a in angle_full:
        if a > total_rotation:
            total_rotation = a

    # Resample to fixed length
    angle_trace = _resample_linear(angle_full, TRACE_LEN)
    del angle_full

    # --- 5. Rotation axis: time-averaged (g_start cross g_t), normalized ---
    ax_sum, ay_sum, az_sum = 0.0, 0.0, 0.0
    for i in range(n):
        base = (start + i) * 3
        gx, gy, gz = g_flat[base], g_flat[base + 1], g_flat[base + 2]
        # cross product g0 x g
        ax_sum += g0y * gz - g0z * gy
        ay_sum += g0z * gx - g0x * gz
        az_sum += g0x * gy - g0y * gx

    axis_raw_mag = (ax_sum * ax_sum + ay_sum * ay_sum + az_sum * az_sum) ** 0.5
    # axis_raw_mag is large for big planar rotations, near-zero for still
    # gestures or fully out-and-back motions. Store both the normalized
    # axis and a "confidence" scalar so scoring can downweight when ill-
    # defined.
    if axis_raw_mag > 1e-3:
        rot_axis = (ax_sum / axis_raw_mag, ay_sum / axis_raw_mag, az_sum / axis_raw_mag)
    else:
        rot_axis = (0.0, 0.0, 0.0)
    # Normalized "axis strength": how planar/coherent was the rotation.
    # Divide by n so it doesn't grow with sample count.
    axis_strength = axis_raw_mag / n

    # --- 6. Motion magnitude trace (resampled) ---
    motion_slice = motion_mag[start:end + 1]
    motion_trace = _resample_linear(motion_slice, TRACE_LEN)

    # Average motion intensity
    sum_motion = 0.0
    for m in motion_slice:
        sum_motion += m
    avg_motion = sum_motion / n

    # Peaks per second: count local maxima with refractory spacing and
    # an adaptive height floor. Kindergartner gross-motor gestures peak
    # at biomechanically realistic rates of 1-5 Hz, so we enforce a
    # minimum spacing of ~100 ms between accepted peaks. The height
    # floor is the larger of an absolute noise floor and a fraction of
    # the gesture's own peak (so a gentle gesture doesn't require the
    # same absolute amplitude as a vigorous one to register peaks).
    height_floor = max(PEAK_MIN_HEIGHT, PEAK_REL_FRACTION * peak_motion)
    refractory_samples = PEAK_REFRACTORY_MS // SAMPLE_INTERVAL_MS

    peaks = 0
    last_peak_i = -refractory_samples  # allow a peak at i=0+
    slice_len = len(motion_slice)
    for i in range(1, slice_len - 1):
        m = motion_slice[i]
        if (m > height_floor
                and m > motion_slice[i - 1]
                and m >= motion_slice[i + 1]
                and (i - last_peak_i) >= refractory_samples):
            peaks += 1
            last_peak_i = i

    duration_s = n * SAMPLE_INTERVAL_MS / 1000.0
    peaks_per_sec = peaks / duration_s if duration_s > 0 else 0.0

    # Cleanup intermediates
    del g_flat
    del motion_mag
    del motion_slice
    gc.collect()

    return {
        "angle_trace": angle_trace,
        "motion_trace": motion_trace,
        "rot_axis": rot_axis,
        "axis_strength": axis_strength,
        "total_rotation": total_rotation,
        "avg_motion": avg_motion,
        "peaks_per_sec": peaks_per_sec,
    }


# ============================================================
# DTW (timing-tolerant trace similarity)
# ============================================================
def _dtw_distance(a, b, prev_row, curr_row, window=DTW_WINDOW):
    """
    Dynamic Time Warping with Sakoe-Chiba band.
    Returns normalized distance (lower = more similar).

    prev_row and curr_row are caller-provided workspace lists of length
    >= TRACE_LEN to avoid per-call allocation.
    """
    n, m = len(a), len(b)
    if n == 0 or m == 0:
        return 1.0

    INF = 1e9

    # Initialize first row
    for j in range(m):
        prev_row[j] = INF
    prev_row[0] = abs(a[0] - b[0])
    for j in range(1, min(window + 1, m)):
        prev_row[j] = prev_row[j - 1] + abs(a[0] - b[j])

    for i in range(1, n):
        j_start = max(0, i - window)
        j_end = min(m, i + window + 1)

        for j in range(m):
            curr_row[j] = INF

        for j in range(j_start, j_end):
            cost = abs(a[i] - b[j])
            min_prev = INF
            if j > 0 and curr_row[j - 1] < min_prev:
                min_prev = curr_row[j - 1]
            if prev_row[j] < min_prev:
                min_prev = prev_row[j]
            if j > 0 and prev_row[j - 1] < min_prev:
                min_prev = prev_row[j - 1]
            curr_row[j] = cost + min_prev

        # Swap rows
        prev_row, curr_row = curr_row, prev_row

    # After final swap, prev_row holds the last computed row
    return prev_row[m - 1] / (n + m)


def _trace_sim_dtw(a, b, prev_row, curr_row, scale=3.0):
    """Convert DTW distance to similarity in [0, 1] via linear mapping."""
    dist = _dtw_distance(a, b, prev_row, curr_row)
    s = 1.0 - dist * scale
    if s < 0.0:
        return 0.0
    if s > 1.0:
        return 1.0
    return s


# ============================================================
# SCORING
# ============================================================
# Weight constants (defined once for clarity; sum = max raw score).
W_ANGLE_TRACE = 4.0     # primary: shape of arm-arc swept
W_ROT_AXIS = 2.0        # plane of motion (up-down vs left-right)
W_TOTAL_ROT = 1.5       # how big the arm-arc was
W_MOTION_TRACE = 3.0    # shape of sharp accelerations within gesture
W_AVG_MOTION = 1.5      # big-vs-small / wild-vs-gentle
W_PEAKS_PER_SEC = 1.0   # gesture tempo (rate, not count)
W_MAX_TOTAL = (W_ANGLE_TRACE + W_ROT_AXIS + W_TOTAL_ROT +
               W_MOTION_TRACE + W_AVG_MOTION + W_PEAKS_PER_SEC)

# Axis strength below this means the rotation axis is ill-defined;
# downweight the axis term proportionally.
AXIS_STRENGTH_FULL = 0.3


def _score_against_sample(live, sample, dtw_prev, dtw_curr):
    """
    Compare a live feature dict against a stored prototype/exemplar.
    Returns similarity in [0, 1].

    The rotation-axis term is gated by both gestures having a coherent
    plane of motion. When one gesture has a defined axis and the other
    does not, that itself is evidence of dissimilarity and the term
    receives zero credit. When neither has a defined axis (e.g. both
    are stationary-wiggle shakes), the term is dropped from both the
    numerator and the effective max, so the comparison falls back to
    the motion-trace, intensity, and tempo features which carry the
    discriminating information for those gestures.
    """
    score = 0.0
    max_total = W_MAX_TOTAL

    # Angle-from-start trace (DTW)
    angle_sim = _trace_sim_dtw(live["angle_trace"], sample["angle_trace"],
                               dtw_prev, dtw_curr)
    score += angle_sim * W_ANGLE_TRACE

    # Rotation axis (cosine similarity), gated by axis strength on both
    # sides. If both gestures have ill-defined axes, drop the term from
    # the comparison entirely (reduces max_total). If only one has a
    # defined axis, that's evidence of dissimilarity -> contribute zero
    # but keep the term in max_total.
    la = live["rot_axis"]
    sa = sample["rot_axis"]
    live_strength = min(1.0, live["axis_strength"] / AXIS_STRENGTH_FULL)
    samp_strength = min(1.0, sample["axis_strength"] / AXIS_STRENGTH_FULL)
    if live_strength < 0.15 and samp_strength < 0.15:
        # Both axes undefined: drop the term
        max_total -= W_ROT_AXIS
    else:
        axis_weight = live_strength * samp_strength
        if axis_weight > 0.0:
            dot = la[0] * sa[0] + la[1] * sa[1] + la[2] * sa[2]
            axis_sim = max(0.0, dot)
            # Scale by how well-defined both axes were
            score += axis_sim * W_ROT_AXIS * axis_weight
        # If only one is defined, axis_weight = 0 and term contributes 0,
        # which is the correct "dissimilar" signal.

    # Total rotation magnitude (soft similarity in radians)
    rot_diff = abs(live["total_rotation"] - sample["total_rotation"])
    rot_sim = 1.0 - min(1.0, rot_diff / ROTATION_TOL_RAD)
    score += rot_sim * W_TOTAL_ROT

    # High-frequency motion magnitude trace (DTW)
    mot_sim = _trace_sim_dtw(live["motion_trace"], sample["motion_trace"],
                             dtw_prev, dtw_curr)
    score += mot_sim * W_MOTION_TRACE

    # Average motion intensity (big vs small / wild vs gentle)
    int_diff = abs(live["avg_motion"] - sample["avg_motion"])
    int_sim = 1.0 - min(1.0, int_diff / INTENSITY_TOL_G)
    score += int_sim * W_AVG_MOTION

    # Peaks per second (gesture tempo, not count)
    p_live = live["peaks_per_sec"]
    p_samp = sample["peaks_per_sec"]
    p_max = max(p_live, p_samp, 1.0)
    peak_diff = abs(p_live - p_samp)
    peak_sim = 1.0 - min(1.0, peak_diff / p_max)
    score += peak_sim * W_PEAKS_PER_SEC

    return score / max_total


# ============================================================
# PROTOTYPE LEARNING
# ============================================================
def _update_prototype(exemplars):
    """
    Build the class prototype from the current exemplar list. Uses
    component-wise mean for continuous features and unit-normalization
    for the rotation axis.

    Called whenever an exemplar is added or removed.
    """
    n = len(exemplars)
    if n == 0:
        return None
    if n == 1:
        # Single exemplar: copy directly
        e = exemplars[0]
        return {
            "angle_trace": list(e["angle_trace"]),
            "motion_trace": list(e["motion_trace"]),
            "rot_axis": e["rot_axis"],
            "axis_strength": e["axis_strength"],
            "total_rotation": e["total_rotation"],
            "avg_motion": e["avg_motion"],
            "peaks_per_sec": e["peaks_per_sec"],
        }

    inv_n = 1.0 / n

    # Trace means
    angle_trace = [0.0] * TRACE_LEN
    motion_trace = [0.0] * TRACE_LEN
    for e in exemplars:
        at = e["angle_trace"]
        mt = e["motion_trace"]
        for i in range(TRACE_LEN):
            angle_trace[i] += at[i]
            motion_trace[i] += mt[i]
    for i in range(TRACE_LEN):
        angle_trace[i] *= inv_n
        motion_trace[i] *= inv_n

    # Rotation axis: sum then re-normalize. This naturally weights
    # exemplars with stronger axis strength because their (already-
    # normalized) axes point coherently while weak/noisy axes cancel.
    ax, ay, az = 0.0, 0.0, 0.0
    sum_strength = 0.0
    sum_rotation = 0.0
    sum_motion = 0.0
    sum_peaks = 0.0
    for e in exemplars:
        ra = e["rot_axis"]
        ax += ra[0]
        ay += ra[1]
        az += ra[2]
        sum_strength += e["axis_strength"]
        sum_rotation += e["total_rotation"]
        sum_motion += e["avg_motion"]
        sum_peaks += e["peaks_per_sec"]

    axis_mag = (ax * ax + ay * ay + az * az) ** 0.5
    if axis_mag > 1e-6:
        rot_axis = (ax / axis_mag, ay / axis_mag, az / axis_mag)
    else:
        rot_axis = (0.0, 0.0, 0.0)

    return {
        "angle_trace": angle_trace,
        "motion_trace": motion_trace,
        "rot_axis": rot_axis,
        "axis_strength": sum_strength * inv_n,
        "total_rotation": sum_rotation * inv_n,
        "avg_motion": sum_motion * inv_n,
        "peaks_per_sec": sum_peaks * inv_n,
    }


def _classify(samples, training_data, dtw_prev, dtw_curr):
    """
    Classify a live gesture against trained prototypes.
    Returns (name, score) or (None, 0.0) if no classes trained.
    """
    live = _extract_features(samples)
    if live is None:
        return None, 0.0

    best_name, best_score = None, 0.0

    for name in ("red", "green", "blue"):
        data = training_data[name]
        prototype = data.get("prototype")
        exemplars = data.get("samples", [])

        if prototype is None and not exemplars:
            continue

        # Primary score against prototype (centroid)
        if prototype is not None:
            proto_score = _score_against_sample(live, prototype,
                                                dtw_prev, dtw_curr)
            # Best-exemplar confirmation: helps when the prototype has
            # averaged across variants and the live gesture matches one
            # exemplar tightly.
            if exemplars:
                best_ex = 0.0
                for ex in exemplars:
                    s = _score_against_sample(live, ex, dtw_prev, dtw_curr)
                    if s > best_ex:
                        best_ex = s
                score = proto_score * 0.65 + best_ex * 0.35
            else:
                score = proto_score
        else:
            best_ex = 0.0
            for ex in exemplars:
                s = _score_against_sample(live, ex, dtw_prev, dtw_curr)
                if s > best_ex:
                    best_ex = s
            score = best_ex

        if score > best_score:
            best_score = score
            best_name = name

    del live
    gc.collect()

    return best_name, best_score


# ============================================================
# GAME CLASS
# ============================================================
class ImprovedGesturesGame:
    """Few-shot gesture recognition game for kindergartners."""

    def __init__(self, nfc, leds, buz, accel, enow):
        self.nfc = nfc
        self.leds = leds
        self.np = leds.np
        self.buz = buz
        self.accel = accel
        self.enow = enow
        self.reader = NfcReader(nfc, COMMANDS)
        self.btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)

        self._frame = 0
        self._mode = "training"
        self._selected_color = None
        self._result_until = 0

        self._training_data = {
            "red": {"samples": [], "prototype": None, "count": 0},
            "green": {"samples": [], "prototype": None, "count": 0},
            "blue": {"samples": [], "prototype": None, "count": 0},
        }

        # Pre-allocated DTW workspace. Reused across all classifications
        # and training extractions to prevent heap fragmentation, which
        # has been the dominant memory issue in past iterations.
        self._dtw_prev = [0.0] * TRACE_LEN
        self._dtw_curr = [0.0] * TRACE_LEN

    # --- Stop / Tag Polling ---
    def _check_stop(self):
        """Check ESP-NOW and NFC for stop signal."""
        if self.enow:
            msg_type, _, _ = self.enow.poll()
            if msg_type == "stop":
                return True
        if self._frame % NFC_POLL_INTERVAL != 0:
            return False
        try:
            cmd, _ = self.reader.read_command(timeout=100)
            return cmd == "stop"
        except Exception:
            return False

    def _poll_tag(self):
        """Read in-game NFC command (not stop). Returns cmd or None."""
        if self._frame % NFC_POLL_INTERVAL != 0:
            return None
        try:
            cmd, _ = self.reader.read_command(timeout=100)
            return None if cmd == "stop" else cmd
        except Exception:
            return None

    # --- Button Capture ---
    def _capture_while_button(self, color):
        """
        Record accelerometer samples while button is held.
        Returns (samples, overflowed, aborted).
        """
        press_start = time.ticks_ms()
        last_sample_ms = press_start
        ring = _SampleRing(MAX_CAPTURE_SAMPLES)
        frame = 0
        overflowed = False

        while self.btn.value() == 0:
            if frame % 20 == 0 and self._check_stop():
                ring.clear()
                _off(self.np)
                gc.collect()
                return None, False, True

            now = time.ticks_ms()
            held_ms = time.ticks_diff(now, press_start)

            if held_ms >= MIN_HOLD_MS:
                if time.ticks_diff(now, last_sample_ms) >= SAMPLE_INTERVAL_MS:
                    last_sample_ms = now
                    try:
                        if ring.count >= ring.size:
                            overflowed = True
                        ring.push(self.accel.read())
                    except Exception:
                        pass
                _spin_border(self.np, color, frame)
            else:
                _pulse_border(self.np, color, frame)

            frame += 1
            time.sleep_ms(5)

        time.sleep_ms(DEBOUNCE_MS)

        # Post-release lockout (ignores rebounce)
        lockout_start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), lockout_start) < POST_RELEASE_LOCKOUT_MS:
            if self.btn.value() == 0:
                while self.btn.value() == 0:
                    time.sleep_ms(10)
                time.sleep_ms(DEBOUNCE_MS)
                lockout_start = time.ticks_ms()
            time.sleep_ms(10)

        samples = ring.get_all()
        ring.clear()
        gc.collect()

        return samples, overflowed, False

    # --- Result Display ---
    def _show_question_mark(self, ms=3000):
        """Show blinking question mark for low confidence."""
        end_at = time.ticks_add(time.ticks_ms(), ms)
        frame = 0
        while time.ticks_diff(end_at, time.ticks_ms()) > 0:
            if frame % 8 == 0 and self._check_stop():
                _off(self.np)
                return True
            bright = WHITE if (frame // 6) % 2 == 0 else WHITE_DIM
            for i in range(NUM_LEDS):
                self.np[i] = bright if i in QUESTION_MARK else OFF
            self.np.write()
            time.sleep_ms(120)
            frame += 1
        return False

    def _show_confidence(self, color, score, shape=None, ms=3000):
        """Show confidence with shape animation."""
        score = max(0.0, min(1.0, score))

        end_at = time.ticks_add(time.ticks_ms(), ms)
        frame = 0
        while time.ticks_diff(end_at, time.ticks_ms()) > 0:
            if frame % 8 == 0 and self._check_stop():
                _off(self.np)
                return True

            wave = frame % 20
            if wave > 10:
                wave = 20 - wave
            scale = 0.35 + (wave / 10.0) * 0.65

            scaled_color = (int(color[0] * scale),
                            int(color[1] * scale),
                            int(color[2] * scale))

            if shape:
                # Show the class shape pulsing in its color (colorblind-friendly)
                self.leds.show_shape(shape, scaled_color)
            else:
                # Fallback to fill pattern based on confidence
                lit = max(1, min(NUM_LEDS, int(score * NUM_LEDS + 0.5))) if score > 0 else 0
                for i in range(NUM_LEDS):
                    self.np[i] = OFF
                for i in range(lit):
                    idx = LED_FILL_ORDER[i]
                    self.np[idx] = scaled_color
                self.np.write()

            time.sleep_ms(100)
            frame += 1
        gc.collect()
        return False

    # --- Training Data Helpers ---
    def _count_trained(self):
        return sum(1 for name in ("red", "green", "blue")
                   if self._training_data[name]["count"] > 0)

    def _add_training_sample(self, color_name, features):
        """Add an exemplar and rebuild the prototype from all exemplars."""
        data = self._training_data[color_name]
        data["count"] += 1

        samples = data["samples"]
        samples.append(features)
        if len(samples) > MAX_TRAINING_SAMPLES:
            old = samples.pop(0)
            del old
            gc.collect()

        # Rebuild prototype from current exemplars. Mean-of-exemplars is
        # more stable than EMA for small N and re-derives correctly when
        # the oldest is evicted.
        data["prototype"] = _update_prototype(samples)

        return data["count"]

    # --- Mode Handlers ---
    def _handle_tag_command(self, cmd):
        """Process NFC tag commands."""
        if cmd in ("red", "green", "blue"):
            self._selected_color = cmd
            self._mode = "train"
            print("  %s training selected" % cmd.upper())
            _play_sound(self.buz, 'train_select')
            _set_border(self.np, WHITE_DIM)
            return True
        elif cmd == "play":
            self._mode = "play"
            self._selected_color = None
            print("  PLAY mode selected")
            _play_sound(self.buz, 'play_select')
            _set_border(self.np, WHITE_DIM)
            return True
        return False

    def _update_training_mode(self):
        """Idle training mode - pulse gray border."""
        _pulse_border(self.np, WHITE_DIM, self._frame)

    def _update_train_mode(self):
        """Active training for selected color."""
        active_color = COLOR_BY_NAME.get(self._selected_color, BLUE)

        if self.btn.value() == 0:
            time.sleep_ms(DEBOUNCE_MS)
            if self.btn.value() == 0:
                print("  Recording %s gesture..." % self._selected_color.upper())
                _play_sound(self.buz, 'record_start')

                gc.collect()
                samples, overflowed, aborted = self._capture_while_button(active_color)

                if aborted:
                    print("  Stop during capture")
                    return False

                if overflowed:
                    print("  Capture got long - newest part was kept")

                gc.collect()
                features = _extract_features(samples)
                del samples
                gc.collect()

                if features is not None:
                    count = self._add_training_sample(self._selected_color, features)
                    print("  %s saved (%d sample%s total)" % (
                        self._selected_color.upper(), count,
                        "" if count == 1 else "s"))
                    _play_sound(self.buz, 'train_success')
                    _flash(self.np, active_color, times=1, on_ms=160, off_ms=40)
                else:
                    print("  Gesture too short or too still")
                    _play_sound(self.buz, 'too_short')

                _set_border(self.np, WHITE_DIM)
        else:
            _pulse_border(self.np, active_color, self._frame)

        return True

    def _update_play_mode(self):
        """Classification mode."""
        if self._count_trained() == 0:
            _pulse_border(self.np, ORANGE_DIM, self._frame)
        else:
            _pulse_border(self.np, WHITE_DIM, self._frame)

        if self.btn.value() == 0:
            time.sleep_ms(DEBOUNCE_MS)
            if self.btn.value() == 0:
                print("  Recording live gesture...")
                _play_sound(self.buz, 'record_start')

                gc.collect()
                samples, overflowed, aborted = self._capture_while_button(WHITE_DIM)

                if aborted:
                    print("  Stop during capture")
                    return False

                if overflowed:
                    print("  Live capture got long - newest part was kept")

                gc.collect()
                if samples is None or len(samples) < 8:
                    print("  Gesture too short")
                    _play_sound(self.buz, 'too_short')
                    _set_border(self.np, WHITE_DIM)
                    return True

                name, score = _classify(samples, self._training_data,
                                        self._dtw_prev, self._dtw_curr)
                del samples
                gc.collect()

                if name is None:
                    print("  No trained class available")
                    _play_sound(self.buz, 'classify_low')
                else:
                    pct = max(0, min(100, int(score * 100 + 0.5)))
                    print("  Chosen class: %s  Confidence: %d%%" % (
                        name.upper(), pct))

                    if score < CONFIDENCE_FLOOR:
                        _play_sound(self.buz, 'classify_low')
                        if self._show_question_mark(3000):
                            return False
                    else:
                        result_color = COLOR_BY_NAME.get(name, BLUE)
                        result_shape = SHAPE_BY_NAME.get(name)
                        _play_sound(self.buz, 'classify_high')
                        if self._show_confidence(result_color, score, result_shape, 3000):
                            return False

                    self._result_until = time.ticks_add(time.ticks_ms(), 10)

                _set_border(self.np, WHITE_DIM)

        return True

    # --- Main Loop ---
    def run(self):
        """Main game loop."""
        print("  Scan RED / GREEN / BLUE to train")
        print("  Scan PLAY to test gestures")
        print("  Hold button while performing a gesture")
        print("  Tap STOP tag or station stop to exit\n")

        while True:
            if self._check_stop():
                print("  Stop detected")
                return

            now = time.ticks_ms()
            if time.ticks_diff(now, self._result_until) < 0:
                time.sleep_ms(LOOP_DELAY_MS)
                self._frame += 1
                continue

            cmd = self._poll_tag()
            if cmd:
                self._handle_tag_command(cmd)

            if self._mode == "training":
                self._update_training_mode()
            elif self._mode == "train":
                if not self._update_train_mode():
                    return
            elif self._mode == "play":
                if not self._update_play_mode():
                    return

            time.sleep_ms(LOOP_DELAY_MS)
            self._frame += 1

            # Periodic GC every ~5 seconds of idle
            if self._frame % 250 == 0:
                gc.collect()


# ============================================================
# ENTRY POINTS
# ============================================================
def play(nfc, leds, buz, accel, i2c, enow):
    """Called from main.py when the 'gestures2' tag is tapped."""
    if accel is None:
        print("  Improved Gestures requires accelerometer - not available")
        buz.reject()
        return

    gc.collect()
    _play_sound(buz, 'start')
    print("\n  === IMPROVED GESTURES ===")
    print("  Free memory at entry: %d bytes" % gc.mem_free())

    try:
        ImprovedGesturesGame(nfc, leds, buz, accel, enow).run()
    finally:
        leds.off()
        gc.collect()
        print("  Free memory at exit:  %d bytes" % gc.mem_free())

    print("\n  === RETURNING TO PROGRAMMING MODE ===\n")


def main():
    """Standalone entry point for testing without main.py."""
    print("\n" + "=" * 50)
    print("  Improved Gestures - Few-Shot Learning")
    print("=" * 50)

    gc.collect()
    print("  Free memory: %d bytes" % gc.mem_free())

    i2c = machine.SoftI2C(sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=100_000)

    import brightness
    try:
        from opt3002 import OPT3002
        light = OPT3002(i2c)
        light.init()
        mult, lux = brightness.calibrate(light)
        if lux is not None:
            print("  Light: %.0f lux -> brightness x%.2f" % (lux, mult))
    except Exception as e:
        print("  [WARN] OPT3002: %s - brightness x1.00" % e)

    from leds import Leds
    from buzzer import Buzzer
    leds = Leds()
    buz = Buzzer(BUZZER_PIN)

    nfc = PN532(i2c, PN532_ADDR)
    try:
        ic, ver, rev = nfc.begin()
        print("  PN5%02X fw %d.%d - NFC ready" % (ic, ver, rev))
    except Exception as e:
        print("  NFC init failed: %s" % e)
        return

    accel = None
    try:
        from lis2dw12 import LIS2DW12, RANGE_4G
        accel = LIS2DW12(i2c)
        accel.init(fs_range=RANGE_4G)
        print("  Accelerometer OK")
    except Exception as e:
        print("  [WARN] Accel: %s" % e)

    from espnow_manager import ESPNowManager
    enow = ESPNowManager()
    enow.init()

    gc.collect()
    print("  Free memory after init: %d bytes" % gc.mem_free())
    print()

    play(nfc, leds, buz, accel, i2c, enow)


if __name__ == "__main__":
    main()