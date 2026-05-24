"""
Improved Gestures — Memory-Efficient Few-Shot Gesture Recognition
==================================================================
Tap the "gestures2" NFC tag to enter. Scan RED / GREEN / BLUE to pick a
training class, hold the button while performing a gesture. Scan PLAY to
test: hold the button to classify against trained gestures.

Improvements over gestures.py:
- 75% smaller feature footprint (22 floats vs 88)
- DTW-based similarity (tolerant of timing variations)
- Amplitude-normalized traces (tolerant of intensity variations)
- Prototype averaging (better few-shot learning)
- Explicit garbage collection (reduced memory leaks)
- Wider tolerances tuned for kindergarteners

In-game NFC tags: red, green, blue, play, stop

Entry points:
    play(nfc, leds, buz, accel, i2c, enow)  — called from main.py
    main()                                   — standalone testing
"""

import gc
import machine
import time
from machine import Pin

from pn532 import PN532
from nfc_reader import NfcReader
from leds import RED, GREEN, BLUE, WHITE, WHITE_DIM, ORANGE_DIM, OFF

# ─── Hardware Config (standalone main only) ───
I2C_SDA, I2C_SCL = 22, 23
BUZZER_PIN, BUTTON_PIN, PN532_ADDR = 19, 0, 0x24

# ─── Game Config ───
NUM_LEDS = 25
NFC_POLL_INTERVAL = 10
LOOP_DELAY_MS = 20
DEBOUNCE_MS = 60
MIN_HOLD_MS = 150
POST_RELEASE_LOCKOUT_MS = 500
SAMPLE_INTERVAL_MS = 10
MAX_CAPTURE_SAMPLES = 150  # Reduced from 320 (1.5 sec is plenty for kids)
MAX_TRAINING_SAMPLES = 4   # Reduced: prototype approach needs fewer exemplars

# Compact trace sizes (memory-efficient)
TRACE_LEN = 12
AXIS_TRACE_LEN = 10
DTW_WINDOW = 3

COMMANDS = {"red", "green", "blue", "play", "stop"}

COLOR_BY_NAME = {
    "red": RED,
    "green": GREEN,
    "blue": BLUE,
}

# ─── Sound Sequences ───
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

# ─── LED Patterns ───
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
    for freq, dur, gap in SOUNDS.get(name, []):
        buz.beep(freq, dur)
        if gap:
            time.sleep_ms(gap)


# ═══════════════════════════════════════════════
# SAMPLE RING BUFFER (memory-efficient)
# ═══════════════════════════════════════════════
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


# ═══════════════════════════════════════════════
# LED DISPLAY HELPERS
# ═══════════════════════════════════════════════
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


# ═══════════════════════════════════════════════
# SIGNAL PROCESSING UTILITIES
# ═══════════════════════════════════════════════
def _motion_amount(sample):
    x, y, z = sample
    return abs((x * x + y * y + z * z) ** 0.5 - 1.0)


def _trim_active_samples(samples):
    """Trim silent leading/trailing samples, keep active motion region."""
    if not samples:
        return []

    n = len(samples)
    motion = [_motion_amount(s) for s in samples]
    
    start, end = 0, n - 1
    while start < n and motion[start] < 0.06:
        start += 1
    while end > start and motion[end] < 0.06:
        end -= 1

    if start >= n:
        return []

    # Add padding context
    if start > 6:
        start -= 6
    if end < n - 7:
        end += 6

    result = samples[start:end + 1]
    
    # Cleanup
    del motion
    gc.collect()
    
    return result


# ═══════════════════════════════════════════════
# COMPACT FEATURE EXTRACTION
# ═══════════════════════════════════════════════
def _extract_features(samples):
    """
    Extract compact, normalized features optimized for:
    - Low memory footprint (22 floats vs 88 in original)
    - Robustness to amplitude/timing variation (few-shot friendly)
    """
    if len(samples) < 6:
        return None

    trimmed = _trim_active_samples(samples)
    n = len(trimmed)
    if n < 6:
        return None

    # ─── Single-pass statistics (avoid intermediate lists) ───
    sum_x, sum_y, sum_z = 0.0, 0.0, 0.0
    energy_x, energy_y, energy_z = 0.0, 0.0, 0.0
    sum_mag, peak_mag = 0.0, 0.0
    active = 0

    for x, y, z in trimmed:
        sum_x += x
        sum_y += y
        sum_z += z
        energy_x += x * x
        energy_y += y * y
        energy_z += z * z
        mag = (x * x + y * y + z * z) ** 0.5
        motion = abs(mag - 1.0)
        sum_mag += motion
        if motion > peak_mag:
            peak_mag = motion
        if motion > 0.07:
            active += 1

    if active < 3:
        return None

    total_energy = energy_x + energy_y + energy_z
    if total_energy <= 0.001:
        return None

    # ─── Normalized axis ratios (scale-invariant) ───
    axis_ratios = (energy_x / total_energy,
                   energy_y / total_energy,
                   energy_z / total_energy)
    
    # Find dominant axis
    if axis_ratios[1] > axis_ratios[0]:
        dominant_axis = 1 if axis_ratios[1] > axis_ratios[2] else 2
    else:
        dominant_axis = 0 if axis_ratios[0] > axis_ratios[2] else 2

    # ─── Compute compact traces via direct sampling ───
    dom_mean = [sum_x, sum_y, sum_z][dominant_axis] / n
    
    mags_trace = []
    dom_trace = []
    
    for i in range(TRACE_LEN):
        idx = int(i * (n - 1) / (TRACE_LEN - 1)) if TRACE_LEN > 1 else 0
        x, y, z = trimmed[idx]
        mags_trace.append(abs((x*x + y*y + z*z)**0.5 - 1.0))
    
    for i in range(AXIS_TRACE_LEN):
        idx = int(i * (n - 1) / (AXIS_TRACE_LEN - 1)) if AXIS_TRACE_LEN > 1 else 0
        dom_trace.append(trimmed[idx][dominant_axis] - dom_mean)

    # ─── Normalize traces to unit L2 norm (amplitude-invariant) ───
    mag_norm = sum(v * v for v in mags_trace) ** 0.5
    if mag_norm > 0.001:
        mags_trace = [v / mag_norm for v in mags_trace]
    
    dom_norm = sum(v * v for v in dom_trace) ** 0.5
    if dom_norm > 0.001:
        dom_trace = [v / dom_norm for v in dom_trace]

    # ─── Robust shape features ───
    # Zero crossings on dominant axis trace (timing-invariant shape signature)
    zero_cross = 0
    prev_positive = dom_trace[0] >= 0
    for v in dom_trace[1:]:
        curr_positive = v >= 0
        if curr_positive != prev_positive:
            zero_cross += 1
            prev_positive = curr_positive

    # Duration bucket (coarse: short/medium/long)
    duration_ms = n * SAMPLE_INTERVAL_MS
    if duration_ms < 300:
        duration_bucket = 0  # short
    elif duration_ms < 700:
        duration_bucket = 1  # medium
    else:
        duration_bucket = 2  # long

    # Intensity bucket (coarse: gentle/normal/vigorous)
    avg_mag = sum_mag / n
    if avg_mag < 0.12:
        intensity_bucket = 0  # gentle
    elif avg_mag < 0.30:
        intensity_bucket = 1  # normal
    else:
        intensity_bucket = 2  # vigorous

    # Cleanup
    del trimmed
    gc.collect()

    return {
        # Categorical features
        "dominant_axis": dominant_axis,
        "duration_bucket": duration_bucket,
        "intensity_bucket": intensity_bucket,
        "zero_cross": zero_cross,
        # Normalized continuous features
        "axis_ratios": axis_ratios,
        "peak_mag": peak_mag,
        "avg_mag": avg_mag,
        # Normalized traces (compact)
        "trace": mags_trace,
        "axis_trace": dom_trace,
    }


# ═══════════════════════════════════════════════
# DTW-BASED SIMILARITY (timing-tolerant)
# ═══════════════════════════════════════════════
def _dtw_distance(a, b, window=DTW_WINDOW):
    """
    Simplified Dynamic Time Warping with Sakoe-Chiba band.
    Returns normalized distance (lower = more similar).
    Memory-efficient: uses two rows instead of full matrix.
    """
    n, m = len(a), len(b)
    if n == 0 or m == 0:
        return 1.0
    
    INF = 999.0
    prev_row = [INF] * m
    curr_row = [INF] * m
    
    # Initialize first row
    prev_row[0] = abs(a[0] - b[0])
    for j in range(1, min(window + 1, m)):
        prev_row[j] = prev_row[j - 1] + abs(a[0] - b[j])
    
    # Fill remaining rows
    for i in range(1, n):
        j_start = max(0, i - window)
        j_end = min(m, i + window + 1)
        
        # Reset current row
        for j in range(m):
            curr_row[j] = INF
        
        for j in range(j_start, j_end):
            cost = abs(a[i] - b[j])
            
            # Find minimum predecessor
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
    
    # Normalize by path length
    return prev_row[m - 1] / (n + m)


def _trace_similarity_dtw(a, b):
    """Convert DTW distance to similarity score (0 to 1)."""
    dist = _dtw_distance(a, b)
    # Map distance to similarity: 0 distance -> 1.0, high distance -> 0.0
    return max(0.0, 1.0 - dist * 3.0)


# ═══════════════════════════════════════════════
# SCORING (few-shot optimized)
# ═══════════════════════════════════════════════
def _score_against_sample(live, sample):
    """
    Scoring optimized for kindergarteners with few training samples.
    Uses DTW, wider tolerances, and focuses on robust features.
    """
    score = 0.0
    
    # ─── Categorical matches (high weight, clear signal) ───
    # Dominant axis match (most important - which way did they move?)
    if live["dominant_axis"] == sample["dominant_axis"]:
        score += 3.5
    
    # Duration similarity (with partial credit for adjacent buckets)
    dur_diff = abs(live["duration_bucket"] - sample["duration_bucket"])
    if dur_diff == 0:
        score += 1.5
    elif dur_diff == 1:
        score += 0.6
    
    # Intensity similarity (forgiving - kids vary a lot)
    int_diff = abs(live["intensity_bucket"] - sample["intensity_bucket"])
    if int_diff == 0:
        score += 1.0
    elif int_diff == 1:
        score += 0.4

    # Zero crossings (shape signature, ±2 tolerance for sloppy gestures)
    zc_diff = abs(live["zero_cross"] - sample["zero_cross"])
    if zc_diff == 0:
        score += 1.5
    elif zc_diff == 1:
        score += 1.0
    elif zc_diff == 2:
        score += 0.4

    # ─── DTW on normalized traces (timing-tolerant) ───
    trace_sim = _trace_similarity_dtw(live["trace"], sample["trace"])
    score += trace_sim * 4.0
    
    axis_sim = _trace_similarity_dtw(live["axis_trace"], sample["axis_trace"])
    score += axis_sim * 3.5

    # ─── Axis ratio similarity (cosine-like on energy distribution) ───
    ar_live = live["axis_ratios"]
    ar_samp = sample["axis_ratios"]
    dot = ar_live[0]*ar_samp[0] + ar_live[1]*ar_samp[1] + ar_live[2]*ar_samp[2]
    score += dot * 2.0

    # Max possible: 3.5 + 1.5 + 1.0 + 1.5 + 4.0 + 3.5 + 2.0 = 17.0
    return score / 17.0


# ═══════════════════════════════════════════════
# PROTOTYPE LEARNING
# ═══════════════════════════════════════════════
def _update_prototype(prototype, new_features, sample_count):
    """
    Update prototype with exponential moving average.
    More weight to newer samples, but preserves stability.
    """
    if prototype is None or sample_count <= 1:
        # First sample: just copy
        return {
            "dominant_axis": new_features["dominant_axis"],
            "duration_bucket": new_features["duration_bucket"],
            "intensity_bucket": new_features["intensity_bucket"],
            "zero_cross": new_features["zero_cross"],
            "axis_ratios": new_features["axis_ratios"],
            "peak_mag": new_features["peak_mag"],
            "avg_mag": new_features["avg_mag"],
            "trace": list(new_features["trace"]),
            "axis_trace": list(new_features["axis_trace"]),
        }
    
    # Blend factor: newer samples get more weight initially, stabilizes over time
    alpha = max(0.2, 1.0 / sample_count)
    
    updated = {}
    
    # Categorical: use mode (most common) - for simplicity, use latest
    updated["dominant_axis"] = new_features["dominant_axis"]
    updated["duration_bucket"] = new_features["duration_bucket"]
    updated["intensity_bucket"] = new_features["intensity_bucket"]
    updated["zero_cross"] = int(prototype["zero_cross"] * (1 - alpha) + 
                                 new_features["zero_cross"] * alpha + 0.5)
    
    # Blend ratios
    old_ar = prototype["axis_ratios"]
    new_ar = new_features["axis_ratios"]
    updated["axis_ratios"] = (
        old_ar[0] * (1 - alpha) + new_ar[0] * alpha,
        old_ar[1] * (1 - alpha) + new_ar[1] * alpha,
        old_ar[2] * (1 - alpha) + new_ar[2] * alpha,
    )
    
    # Blend scalars
    updated["peak_mag"] = prototype["peak_mag"] * (1 - alpha) + new_features["peak_mag"] * alpha
    updated["avg_mag"] = prototype["avg_mag"] * (1 - alpha) + new_features["avg_mag"] * alpha
    
    # Blend traces element-wise
    updated["trace"] = [
        prototype["trace"][i] * (1 - alpha) + new_features["trace"][i] * alpha
        for i in range(len(prototype["trace"]))
    ]
    updated["axis_trace"] = [
        prototype["axis_trace"][i] * (1 - alpha) + new_features["axis_trace"][i] * alpha
        for i in range(len(prototype["axis_trace"]))
    ]
    
    return updated


def _classify(samples, training_data):
    """
    Classification using prototypes with exemplar confirmation.
    Optimized for few-shot learning scenarios.
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
        
        # Score against prototype (primary)
        if prototype is not None:
            proto_score = _score_against_sample(live, prototype)
            
            # If we have exemplars, use best one for confirmation boost
            if exemplars:
                exemplar_scores = [_score_against_sample(live, ex) for ex in exemplars]
                best_exemplar = max(exemplar_scores)
                # Weighted combination: prototype is anchor, exemplar confirms
                score = proto_score * 0.65 + best_exemplar * 0.35
            else:
                score = proto_score
        else:
            # No prototype yet, use best exemplar
            exemplar_scores = [_score_against_sample(live, ex) for ex in exemplars]
            score = max(exemplar_scores)

        if score > best_score:
            best_score = score
            best_name = name

    # Cleanup
    del live
    gc.collect()

    return best_name, best_score


# ═══════════════════════════════════════════════
# GAME CLASS
# ═══════════════════════════════════════════════
class ImprovedGesturesGame:
    """Memory-efficient, few-shot optimized gesture recognition game."""

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

    # ─── Stop / Tag Polling ───
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

    # ─── Button Capture ───
    def _capture_while_button(self, color):
        """
        Record accelerometer samples while button held.
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

        # Post-release lockout
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

    # ─── Result Display ───
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

    def _show_confidence(self, color, score, ms=3000):
        """Show confidence fill animation."""
        score = max(0.0, min(1.0, score))
        lit = max(1, min(NUM_LEDS, int(score * NUM_LEDS + 0.5))) if score > 0 else 0

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

            for i in range(NUM_LEDS):
                self.np[i] = OFF
            for i in range(lit):
                idx = LED_FILL_ORDER[i]
                self.np[idx] = (int(color[0] * scale), int(color[1] * scale), int(color[2] * scale))
            self.np.write()
            time.sleep_ms(100)
            frame += 1
        return False

    # ─── Training Data Helpers ───
    def _count_trained(self):
        return sum(1 for name in ("red", "green", "blue") 
                   if self._training_data[name]["count"] > 0)

    def _add_training_sample(self, color_name, features):
        """Add features and update prototype."""
        data = self._training_data[color_name]
        data["count"] += 1
        
        # Update prototype with EMA
        data["prototype"] = _update_prototype(
            data["prototype"], features, data["count"]
        )
        
        # Keep a few exemplars for confirmation voting
        samples = data["samples"]
        samples.append(features)
        if len(samples) > MAX_TRAINING_SAMPLES:
            # Remove oldest
            old = samples.pop(0)
            del old
            gc.collect()
        
        return data["count"]

    # ─── Mode Handlers ───
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
        """Idle training mode — pulse gray border."""
        _pulse_border(self.np, WHITE_DIM, self._frame)

    def _update_train_mode(self):
        """Active training for selected color."""
        active_color = COLOR_BY_NAME.get(self._selected_color, BLUE)

        if self.btn.value() == 0:
            time.sleep_ms(DEBOUNCE_MS)
            if self.btn.value() == 0:
                print("  Recording %s gesture..." % self._selected_color.upper())
                _play_sound(self.buz, 'record_start')

                gc.collect()  # Pre-capture cleanup
                samples, overflowed, aborted = self._capture_while_button(active_color)
                
                if aborted:
                    print("  Stop during capture")
                    return False

                if overflowed:
                    print("  Capture got long — newest part was kept")

                gc.collect()  # Post-capture cleanup
                features = _extract_features(samples)
                del samples
                gc.collect()
                
                if features is not None:
                    count = self._add_training_sample(self._selected_color, features)
                    print("  %s saved (%d sample%s total)" % (
                        self._selected_color.upper(), count, "" if count == 1 else "s"))
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
                    print("  Live capture got long — newest part was kept")

                gc.collect()
                trimmed = _trim_active_samples(samples)
                del samples
                gc.collect()
                
                if len(trimmed) >= 6:
                    name, score = _classify(trimmed, self._training_data)
                    del trimmed
                    gc.collect()

                    if name is None:
                        print("  No trained class available")
                        _play_sound(self.buz, 'classify_low')
                    else:
                        pct = max(0, min(100, int(score * 100 + 0.5)))
                        print("  Chosen class: %s  Confidence: %d%%" % (name.upper(), pct))

                        if score < 0.15:  # Slightly higher threshold for "unknown"
                            _play_sound(self.buz, 'classify_low')
                            if self._show_question_mark(3000):
                                return False
                        else:
                            result_color = COLOR_BY_NAME.get(name, BLUE)
                            _play_sound(self.buz, 'classify_high')
                            if self._show_confidence(result_color, score, 3000):
                                return False

                        self._result_until = time.ticks_add(time.ticks_ms(), 10)
                else:
                    del trimmed
                    gc.collect()
                    print("  Gesture too short or too still")
                    _play_sound(self.buz, 'too_short')

                _set_border(self.np, WHITE_DIM)

        return True

    # ─── Main Loop ───
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


# ═══════════════════════════════════════════════
# ENTRY POINTS
# ═══════════════════════════════════════════════
def play(nfc, leds, buz, accel, i2c, enow):
    """Called from main.py when the 'gestures2' tag is tapped."""
    if accel is None:
        print("  Improved Gestures requires accelerometer — not available")
        buz.reject()
        return

    gc.collect()
    _play_sound(buz, 'start')
    print("\n  === IMPROVED GESTURES ===")

    try:
        ImprovedGesturesGame(nfc, leds, buz, accel, enow).run()
    finally:
        leds.off()
        gc.collect()

    print("\n  === RETURNING TO PROGRAMMING MODE ===\n")


def main():
    """Standalone entry point for testing without main.py."""
    print("\n" + "=" * 50)
    print("  Improved Gestures — Few-Shot Learning")
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
        print("  [WARN] OPT3002: %s — brightness x1.00" % e)

    from leds import Leds
    from buzzer import Buzzer
    leds = Leds()
    buz = Buzzer(BUZZER_PIN)

    nfc = PN532(i2c, PN532_ADDR)
    try:
        ic, ver, rev = nfc.begin()
        print("  PN5%02X fw %d.%d — NFC ready" % (ic, ver, rev))
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
