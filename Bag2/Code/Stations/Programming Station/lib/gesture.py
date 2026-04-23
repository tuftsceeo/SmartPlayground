"""
Gesture Module — Record, extract features, and match gestures
===============================================================
Records accelerometer data, extracts a compact feature vector,
and matches live motion against stored templates.

Features extracted:
  - peak_mag:      Peak acceleration magnitude (g)
  - energy:        Total motion energy (sum of squared magnitudes)
  - dominant_axis: Which axis had highest energy (0=X, 1=Y, 2=Z)
  - axis_ratio:    Ratio of dominant axis energy to total energy
  - zero_cross:    Number of direction reversals on dominant axis
  - duration_ms:   Duration of active motion above threshold
  - spike_count:   Number of distinct acceleration peaks

Usage:
    from gesture import GestureEngine

    engine = GestureEngine(accel, leds, buzzer)
    engine.record_gesture(num_reps=3)

    # Later, in event loop:
    if engine.check_match():
        print("Gesture detected!")
"""

import time
import math


# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────
SAMPLE_RATE_MS   = 10       # 100Hz sampling
RECORD_WINDOW_MS = 1200     # Max recording window
MOTION_THRESHOLD = 0.2      # g — minimum motion to count as "active"
PEAK_THRESHOLD   = 0.35     # g — minimum to count as a peak
MATCH_TOLERANCE  = 0.55     # base tolerance factor (higher = more lenient)
MATCH_PASS_RATIO = 0.5      # need 50% of features to pass (was 60%)

# Live detection
TRIGGER_COOLDOWN = 800      # ms after a match before allowing another


# ─────────────────────────────────────────────
# FEATURE EXTRACTION
# ─────────────────────────────────────────────

def _magnitude(x, y, z):
    return math.sqrt(x * x + y * y + z * z)


def _extract_features(samples):
    """
    Extract feature vector from a list of (x, y, z) samples.
    Returns dict of features, or None if too little motion.
    """
    if len(samples) < 5:
        return None

    mags = []
    energy_x = 0.0
    energy_y = 0.0
    energy_z = 0.0
    active_samples = 0

    for x, y, z in samples:
        mag = _magnitude(x, y, z)
        motion = abs(mag - 1.0)
        mags.append(motion)
        energy_x += x * x
        energy_y += y * y
        energy_z += z * z
        if motion > MOTION_THRESHOLD:
            active_samples += 1

    if active_samples < 3:
        return None

    peak_mag = max(mags)
    energy = sum(m * m for m in mags)

    axis_energies = [energy_x, energy_y, energy_z]
    total_axis_energy = sum(axis_energies)
    if total_axis_energy < 0.01:
        return None

    dominant_axis = 0
    if axis_energies[1] > axis_energies[0]:
        dominant_axis = 1
    if axis_energies[2] > axis_energies[dominant_axis]:
        dominant_axis = 2

    axis_ratio = axis_energies[dominant_axis] / total_axis_energy

    # Zero crossings on dominant axis
    prev_val = samples[0][dominant_axis]
    zero_cross = 0
    for s in samples[1:]:
        val = s[dominant_axis]
        if (val > 0 and prev_val < 0) or (val < 0 and prev_val > 0):
            zero_cross += 1
        prev_val = val

    duration_ms = active_samples * SAMPLE_RATE_MS

    # Spike count
    spike_count = 0
    in_spike = False
    for m in mags:
        if m > PEAK_THRESHOLD and not in_spike:
            spike_count += 1
            in_spike = True
        elif m < PEAK_THRESHOLD * 0.5:
            in_spike = False

    return {
        "peak_mag": peak_mag,
        "energy": energy,
        "dominant_axis": dominant_axis,
        "axis_ratio": axis_ratio,
        "zero_cross": zero_cross,
        "duration_ms": duration_ms,
        "spike_count": spike_count,
    }


def _average_features(feature_list):
    """Average multiple feature dicts into one template."""
    if not feature_list:
        return None
    n = len(feature_list)
    avg = {}
    for key in feature_list[0]:
        if key == "dominant_axis":
            counts = [0, 0, 0]
            for f in feature_list:
                counts[f[key]] += 1
            avg[key] = counts.index(max(counts))
        else:
            avg[key] = sum(f[key] for f in feature_list) / n
    return avg


def _compute_tolerance(feature_list):
    """Compute per-feature tolerance from variation across recordings."""
    if len(feature_list) < 2:
        # Only one sample — use generous defaults
        tol = {}
        f = feature_list[0]
        for key in f:
            if key == "dominant_axis":
                continue
            tol[key] = max(f[key] * MATCH_TOLERANCE, 0.3)
        return tol

    tol = {}
    for key in feature_list[0]:
        if key == "dominant_axis":
            continue
        vals = [f[key] for f in feature_list]
        mean = sum(vals) / len(vals)
        spread = max(vals) - min(vals)
        # Tolerance = max of (spread * 2.0) or (base tolerance * mean) or min floor
        base = max(mean * MATCH_TOLERANCE, 0.3)
        tol[key] = max(spread * 2.0, base)
    return tol


# ─────────────────────────────────────────────
# MATCHING
# ─────────────────────────────────────────────

def _match_features(live, template, tolerance):
    """
    Compare live features to template.
    Returns True if within tolerance on enough features.
    Dominant axis is a soft check (counts as one feature, not a gate).
    """
    if live is None or template is None:
        return False

    checks = 0
    passes = 0

    # Dominant axis — soft check (not a hard gate)
    checks += 1
    if live["dominant_axis"] == template["dominant_axis"]:
        passes += 1

    # Continuous features
    for key in ("peak_mag", "energy", "axis_ratio", "duration_ms", "spike_count"):
        if key not in tolerance:
            continue
        diff = abs(live[key] - template[key])
        checks += 1
        if diff <= tolerance[key]:
            passes += 1

    return checks > 0 and passes >= checks * MATCH_PASS_RATIO


# ─────────────────────────────────────────────
# RECORDING HELPERS
# ─────────────────────────────────────────────

def _record_one_window(accel, duration_ms=RECORD_WINDOW_MS):
    samples = []
    num_samples = duration_ms // SAMPLE_RATE_MS
    for _ in range(num_samples):
        try:
            x, y, z = accel.read()
            samples.append((x, y, z))
        except Exception:
            pass
        time.sleep_ms(SAMPLE_RATE_MS)
    return samples


def _trim_to_motion(samples):
    """Trim leading/trailing idle samples to just the active gesture."""
    if not samples:
        return samples

    first = 0
    last = len(samples) - 1

    for i in range(len(samples)):
        x, y, z = samples[i]
        if abs(_magnitude(x, y, z) - 1.0) > MOTION_THRESHOLD:
            first = max(0, i - 3)
            break

    for i in range(len(samples) - 1, -1, -1):
        x, y, z = samples[i]
        if abs(_magnitude(x, y, z) - 1.0) > MOTION_THRESHOLD:
            last = min(len(samples) - 1, i + 3)
            break

    return samples[first:last + 1]


# ─────────────────────────────────────────────
# GESTURE ENGINE
# ─────────────────────────────────────────────

class GestureEngine:
    def __init__(self, accel, leds, buzzer):
        self.accel = accel
        self.leds = leds
        self.buzzer = buzzer
        self.template = None
        self.tolerance = None
        self.last_match_time = 0
        self.has_gesture = False

    def record_gesture(self, num_reps=3):
        """
        Guide the user through recording a gesture multiple times.
        Returns True if successful.
        """
        self.template = None
        self.tolerance = None
        self.has_gesture = False

        feature_list = []

        for rep in range(num_reps):
            # Countdown
            self._countdown(rep + 1, num_reps)

            # Recording — LEDs fill up as time passes
            self.buzzer.beep(800, 60)
            samples = self._record_with_leds()

            # Trim and extract
            trimmed = _trim_to_motion(samples)
            features = _extract_features(trimmed)

            if features is None:
                # Not enough motion — red flash, retry from scratch
                self._show_fail()
                print("  Rep %d/%d: not enough motion — restarting" % (rep + 1, num_reps))
                return self.record_gesture(num_reps)

            feature_list.append(features)

            # Success for this rep — green flash
            self._show_rep_ok()

            print("  Rep %d/%d: peak=%.2fg energy=%.1f axis=%d spikes=%d" % (
                rep + 1, num_reps,
                features["peak_mag"], features["energy"],
                features["dominant_axis"], features["spike_count"],
            ))

            if rep < num_reps - 1:
                time.sleep_ms(500)

        # Build template
        self.template = _average_features(feature_list)
        self.tolerance = _compute_tolerance(feature_list)

        if self.template is None:
            print("  [FAIL] Could not build gesture template")
            self.buzzer.reject()
            return False

        self.has_gesture = True

        # Success celebration
        self._show_complete()

        print("  Gesture saved: peak=%.2fg energy=%.1f axis=%d ratio=%.2f spikes=%d" % (
            self.template["peak_mag"], self.template["energy"],
            self.template["dominant_axis"], self.template["axis_ratio"],
            self.template["spike_count"],
        ))

        return True

    def check_match(self):
        """
        Check if current motion matches the stored gesture.
        Call when INT1 fires (motion detected).
        Returns True if gesture detected.
        """
        if not self.has_gesture:
            return False

        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_match_time) < TRIGGER_COOLDOWN:
            return False

        samples = _record_one_window(self.accel, duration_ms=RECORD_WINDOW_MS)
        trimmed = _trim_to_motion(samples)
        features = _extract_features(trimmed)

        if features is None:
            return False

        matched = _match_features(features, self.template, self.tolerance)

        if matched:
            self.last_match_time = time.ticks_ms()

        return matched

    # ── LED feedback during recording ──

    def _countdown(self, rep, total):
        """3-2-1 countdown with clear LED groupings."""
        n = self.leds.num

        print("  Get ready... (%d/%d)" % (rep, total))

        # 3 — all LEDs dim yellow
        for i in range(n):
            self.leds.np[i] = (8, 8, 0)
        self.leds.np.write()
        self.buzzer.beep(500, 60)
        time.sleep_ms(700)

        # 2 — two thirds lit
        two_thirds = (n * 2) // 3
        for i in range(n):
            self.leds.np[i] = (12, 10, 0) if i < two_thirds else (0, 0, 0)
        self.leds.np.write()
        self.buzzer.beep(600, 60)
        time.sleep_ms(700)

        # 1 — one third lit, brighter
        one_third = n // 3
        for i in range(n):
            self.leds.np[i] = (20, 15, 0) if i < one_third else (0, 0, 0)
        self.leds.np.write()
        self.buzzer.beep(700, 60)
        time.sleep_ms(700)

        # GO — full bright cyan flash
        for i in range(n):
            self.leds.np[i] = (15, 10, 25)
        self.leds.np.write()
        self.buzzer.beep(1000, 80)
        time.sleep_ms(200)

    def _record_with_leds(self):
        """Record while filling LEDs to show progress."""
        samples = []
        n = self.leds.num
        num_samples = RECORD_WINDOW_MS // SAMPLE_RATE_MS

        for idx in range(num_samples):
            try:
                x, y, z = self.accel.read()
                samples.append((x, y, z))
            except Exception:
                pass

            # Fill LEDs proportionally
            lit = ((idx + 1) * n) // num_samples
            for i in range(n):
                if i < lit:
                    self.leds.np[i] = (5, 0, 15)  # cyan/blue recording
                else:
                    self.leds.np[i] = (1, 1, 1)   # dim pending
            self.leds.np.write()

            time.sleep_ms(SAMPLE_RATE_MS)

        return samples

    def _show_rep_ok(self):
        """Green flash — one rep captured."""
        for i in range(self.leds.num):
            self.leds.np[i] = (20, 0, 0)  # green (GRB)
        self.leds.np.write()
        self.buzzer.beep(1000, 50)
        time.sleep_ms(300)
        self.leds.off()

    def _show_fail(self):
        """Red flash — not enough motion."""
        for _ in range(3):
            for i in range(self.leds.num):
                self.leds.np[i] = (0, 25, 0)  # red (GRB)
            self.leds.np.write()
            time.sleep_ms(100)
            self.leds.off()
            time.sleep_ms(100)
        self.buzzer.beep(300, 200)
        time.sleep_ms(400)

    def _show_complete(self):
        """Celebration — gesture saved successfully."""
        # Quick green sweep
        for i in range(self.leds.num):
            self.leds.np[i] = (25, 0, 0)  # green
            self.leds.np.write()
            time.sleep_ms(20)
        time.sleep_ms(200)

        # Flash
        self.leds.flash(20, 0, 0, times=3, on_ms=80, off_ms=60)

        # Rising tones
        self.buzzer.beep(880, 50)
        time.sleep_ms(30)
        self.buzzer.beep(1100, 50)
        time.sleep_ms(30)
        self.buzzer.beep(1320, 80)

        self.leds.off()