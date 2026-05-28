"""
Gestures — Train and Classify Wand Motions
==========================================
Tap the "gestures" NFC tag to enter. Scan RED / GREEN / BLUE to pick a
training class, hold the button while performing a gesture (up to 8 samples
per color). Scan PLAY to test: hold the button to classify against trained
gestures. Confidence fills the matrix in the chosen color; low confidence
shows a blinking question mark.

In-game NFC tags: red, green, blue, play, stop

Entry points:
    play(nfc, leds, buz, accel, i2c, enow)  — called from main.py
    main()                                   — standalone testing

Template pattern:
    1. GesturesGame class with __init__() and run()
    2. play() for wand integration (hardware passed in)
    3. main() for standalone testing (initializes hardware)
    4. CRITICAL: ESP-NOW and NFC stop check at start of run loop
"""

import machine
import time
from machine import Pin

from pn532 import PN532
from nfc_reader import NfcReader
from game_tags import exit_tags_excluding

_EXIT_TAGS = exit_tags_excluding("gestures")
from leds import (
    RED, GREEN, BLUE, WHITE, WHITE_DIM, ORANGE_DIM, OFF,
    SHAPE_DIAMOND, SHAPE_POWER, SHAPE_STAR,
)

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
MAX_CAPTURE_SAMPLES = 320
MAX_TRAINING_SAMPLES = 8

COMMANDS = {"red", "green", "blue", "play"} | _EXIT_TAGS

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
# SAMPLE RING BUFFER
# ═══════════════════════════════════════════════
class _SampleRing:
    """Fixed-size ring buffer for accelerometer samples."""
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
    mag = (x * x + y * y + z * z) ** 0.5
    return abs(mag - 1.0)


def _trim_active_samples(samples):
    """Trim silent leading/trailing samples, keep active motion region."""
    if not samples:
        return []

    motion = [_motion_amount(s) for s in samples]
    start, end = 0, len(samples) - 1

    while start < len(samples) and motion[start] < 0.06:
        start += 1
    while end > start and motion[end] < 0.06:
        end -= 1

    if start >= len(samples):
        return []

    if start > 8:
        start -= 8
    if end < len(samples) - 9:
        end += 8

    return samples[start:end + 1]


def _resample(values, n):
    """Resample a list to exactly n points via linear interpolation."""
    if not values:
        return []
    if len(values) == 1:
        return [values[0]] * n

    out = []
    last = len(values) - 1
    for i in range(n):
        pos = (i * last) / float(n - 1)
        lo = int(pos)
        hi = min(lo + 1, last)
        frac = pos - lo
        out.append(values[lo] * (1.0 - frac) + values[hi] * frac)
    return out


def _integrate(values, dt):
    """Cumulative integration (trapezoidal approximation)."""
    out, total = [], 0.0
    for v in values:
        total += v * dt
        out.append(total)
    return out


def _max_abs(values):
    if not values:
        return 0.0
    return max(abs(v) for v in values)


def _sum_abs(values):
    return sum(abs(v) for v in values)


def _same_sign(a, b):
    return (a >= 0 and b >= 0) or (a < 0 and b < 0)


# ═══════════════════════════════════════════════
# FEATURE EXTRACTION
# ═══════════════════════════════════════════════
def _extract_features(samples):
    """Extract feature dict from accelerometer samples, or None if invalid."""
    if len(samples) < 6:
        return None

    trimmed = _trim_active_samples(samples)
    if len(trimmed) < 6:
        return None

    mags, xs, ys, zs = [], [], [], []
    energy_x, energy_y, energy_z = 0.0, 0.0, 0.0
    active = 0

    for x, y, z in trimmed:
        mag = (x * x + y * y + z * z) ** 0.5
        motion = abs(mag - 1.0)
        mags.append(motion)
        xs.append(x)
        ys.append(y)
        zs.append(z)
        energy_x += x * x
        energy_y += y * y
        energy_z += z * z
        if motion > 0.07:
            active += 1

    if active < 3:
        return None

    axis_energies = [energy_x, energy_y, energy_z]
    total_energy = sum(axis_energies)
    if total_energy <= 0.001:
        return None

    dominant_axis = axis_energies.index(max(axis_energies))
    axis_ratio = axis_energies[dominant_axis] / total_energy

    base_n = min(4, len(trimmed))
    base_x = sum(xs[:base_n]) / base_n
    base_y = sum(ys[:base_n]) / base_n
    base_z = sum(zs[:base_n]) / base_n

    dxs = [x - base_x for x in xs]
    dys = [y - base_y for y in ys]
    dzs = [z - base_z for z in zs]
    dominant_detrended = [dxs, dys, dzs][dominant_axis]

    zero_cross = 0
    prev = dominant_detrended[0]
    for val in dominant_detrended[1:]:
        if (val > 0 and prev < 0) or (val < 0 and prev > 0):
            zero_cross += 1
        prev = val

    spike_count, in_spike = 0, False
    for m in mags:
        if m > 0.18 and not in_spike:
            spike_count += 1
            in_spike = True
        elif m < 0.08:
            in_spike = False

    dt = 0.01
    vel_dom = _integrate(dominant_detrended, dt)
    vel_x = _integrate(dxs, dt)
    vel_y = _integrate(dys, dt)
    vel_z = _integrate(dzs, dt)

    peak_speed_proxy = _max_abs(vel_dom)
    travel_proxy = _sum_abs(vel_dom) * dt
    net_displacement_proxy = abs(vel_dom[-1]) if vel_dom else 0.0

    speed3 = [(vel_x[i]**2 + vel_y[i]**2 + vel_z[i]**2)**0.5 for i in range(len(vel_x))]
    travel3_proxy = _sum_abs(speed3) * dt

    first_window = max(2, min(len(dominant_detrended) // 4, len(dominant_detrended)))
    first_push = sum(dominant_detrended[:first_window]) / first_window

    return {
        "peak_mag": max(mags),
        "avg_mag": sum(mags) / len(mags),
        "energy": sum(m * m for m in mags),
        "dominant_axis": dominant_axis,
        "axis_ratio": axis_ratio,
        "zero_cross": zero_cross,
        "duration_ms": len(trimmed) * 10,
        "spike_count": spike_count,
        "trace": _resample(mags, 36),
        "axis_trace": _resample(dominant_detrended, 28),
        "velocity_trace": _resample(vel_dom, 24),
        "peak_speed_proxy": peak_speed_proxy,
        "travel_proxy": travel_proxy,
        "travel3_proxy": travel3_proxy,
        "net_displacement_proxy": net_displacement_proxy,
        "first_push": first_push,
    }


# ═══════════════════════════════════════════════
# CLASSIFICATION
# ═══════════════════════════════════════════════
def _trace_similarity(a, b):
    """Pearson correlation between two traces."""
    if not a or not b or len(a) != len(b):
        return 0.0

    mean_a = sum(a) / len(a)
    mean_b = sum(b) / len(b)

    num, den_a, den_b = 0.0, 0.0, 0.0
    for i in range(len(a)):
        da = a[i] - mean_a
        db = b[i] - mean_b
        num += da * db
        den_a += da * da
        den_b += db * db

    den = (den_a * den_b) ** 0.5
    return num / den if den > 0 else 0.0


def _feature_part(live_val, sample_val, base_tol):
    """Score a single feature comparison (0.0 to 1.0)."""
    diff = abs(live_val - sample_val)
    return max(0.0, min(1.0, 1.0 - diff / float(base_tol)))


def _score_against_sample(live, sample):
    """Weighted similarity score between live features and a training sample."""
    score, weight = 0.0, 0.0

    trace_sim = max(0.0, _trace_similarity(live["trace"], sample["trace"]))
    score += trace_sim * 1.8
    weight += 1.8

    axis_sim = max(0.0, _trace_similarity(live["axis_trace"], sample["axis_trace"]))
    score += axis_sim * 2.8
    weight += 2.8

    velocity_sim = max(0.0, _trace_similarity(live["velocity_trace"], sample["velocity_trace"]))
    score += velocity_sim * 2.5
    weight += 2.5

    score += _feature_part(live["peak_speed_proxy"], sample["peak_speed_proxy"], 0.11) * 1.8
    weight += 1.8
    score += _feature_part(live["travel_proxy"], sample["travel_proxy"], 0.15) * 2.0
    weight += 2.0
    score += _feature_part(live["travel3_proxy"], sample["travel3_proxy"], 0.22) * 1.4
    weight += 1.4
    score += _feature_part(live["net_displacement_proxy"], sample["net_displacement_proxy"], 0.12) * 1.7
    weight += 1.7
    score += _feature_part(live["peak_mag"], sample["peak_mag"], 0.55) * 1.0
    weight += 1.0
    score += _feature_part(live["avg_mag"], sample["avg_mag"], 0.26) * 0.8
    weight += 0.8
    score += _feature_part(live["energy"], sample["energy"], 2.60) * 0.9
    weight += 0.9
    score += _feature_part(live["axis_ratio"], sample["axis_ratio"], 0.24) * 0.8
    weight += 0.8
    score += _feature_part(live["duration_ms"], sample["duration_ms"], 850) * 0.5
    weight += 0.5
    score += _feature_part(live["zero_cross"], sample["zero_cross"], 4.0) * 0.6
    weight += 0.6
    score += _feature_part(live["spike_count"], sample["spike_count"], 3.0) * 0.5
    weight += 0.5

    if live["dominant_axis"] == sample["dominant_axis"]:
        score += 1.2
    weight += 1.2

    if _same_sign(live["first_push"], sample["first_push"]):
        score += 1.5
    weight += 1.5

    return score / weight


def _classify(samples, training_data):
    """Classify samples against training data. Returns (class_name, score)."""
    live = _extract_features(samples)
    if live is None:
        return None, 0.0

    best_name, best_score = None, 0.0

    for name in ("red", "green", "blue"):
        exemplars = training_data[name]["samples"]
        if not exemplars:
            continue

        scores = sorted([_score_against_sample(live, s) for s in exemplars], reverse=True)

        if len(scores) >= 3:
            color_score = scores[0] * 0.60 + scores[1] * 0.28 + scores[2] * 0.12
        elif len(scores) == 2:
            color_score = scores[0] * 0.68 + scores[1] * 0.32
        else:
            color_score = scores[0]

        if color_score > best_score:
            best_score = color_score
            best_name = name

    return best_name, best_score


# ═══════════════════════════════════════════════
# GAME CLASS
# ═══════════════════════════════════════════════
class GesturesGame:
    """Train-and-classify gesture recognition game."""

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
            "red": {"samples": []},
            "green": {"samples": []},
            "blue": {"samples": []},
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
            return cmd in _EXIT_TAGS
        except Exception:
            return False

    def _poll_tag(self):
        """Read in-game NFC command (not stop). Returns cmd or None."""
        if self._frame % NFC_POLL_INTERVAL != 0:
            return None
        try:
            cmd, _ = self.reader.read_command(timeout=100)
            return None if cmd in _EXIT_TAGS else cmd
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
                _off(self.np)
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

        lockout_start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), lockout_start) < POST_RELEASE_LOCKOUT_MS:
            if self.btn.value() == 0:
                while self.btn.value() == 0:
                    time.sleep_ms(10)
                time.sleep_ms(DEBOUNCE_MS)
                lockout_start = time.ticks_ms()
            time.sleep_ms(10)

        return ring.get_all(), overflowed, False

    # ─── Result Display ───
    def _show_question_mark(self, ms=3000):
        """Show blinking question mark for low confidence. Returns True if stopped."""
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
        """Show confidence with shape animation. Returns True if stopped."""
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

            scaled_color = (int(color[0] * scale), int(color[1] * scale), int(color[2] * scale))

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
        return False

    # ─── Training Data Helpers ───
    def _count_trained(self):
        return sum(1 for name in ("red", "green", "blue") if self._training_data[name]["samples"])

    def _add_training_sample(self, color_name, features):
        """Add features to training data, discarding oldest if at capacity."""
        samples = self._training_data[color_name]["samples"]
        samples.append(features)
        if len(samples) > MAX_TRAINING_SAMPLES:
            samples.pop(0)
            print("  %s oldest training sample discarded" % color_name.upper())
        return len(samples)

    # ─── Mode Handlers ───
    def _handle_tag_command(self, cmd):
        """Process NFC tag commands. Returns True if mode changed."""
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
        """Active training for selected color. Returns False if should exit."""
        active_color = COLOR_BY_NAME.get(self._selected_color, BLUE)

        if self.btn.value() == 0:
            time.sleep_ms(DEBOUNCE_MS)
            if self.btn.value() == 0:
                print("  Recording %s gesture..." % self._selected_color.upper())
                _play_sound(self.buz, 'record_start')

                samples, overflowed, aborted = self._capture_while_button(active_color)
                if aborted:
                    print("  Stop during capture")
                    return False

                if overflowed:
                    print("  Capture got long — newest part was kept")

                features = _extract_features(samples)
                if features is not None:
                    count = self._add_training_sample(self._selected_color, features)
                    print("  %s saved (%d sample set%s kept)" % (
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
        """Classification mode. Returns False if should exit."""
        if self._count_trained() == 0:
            _pulse_border(self.np, ORANGE_DIM, self._frame)
        else:
            _pulse_border(self.np, WHITE_DIM, self._frame)

        if self.btn.value() == 0:
            time.sleep_ms(DEBOUNCE_MS)
            if self.btn.value() == 0:
                print("  Recording live gesture...")
                _play_sound(self.buz, 'record_start')

                samples, overflowed, aborted = self._capture_while_button(WHITE_DIM)
                if aborted:
                    print("  Stop during capture")
                    return False

                if overflowed:
                    print("  Live capture got long — newest part was kept")

                trimmed = _trim_active_samples(samples)
                if len(trimmed) >= 6:
                    name, score = _classify(trimmed, self._training_data)

                    if name is None:
                        print("  No trained class available")
                        _play_sound(self.buz, 'classify_low')
                    else:
                        pct = max(0, min(100, int(score * 100 + 0.5)))
                        print("  Chosen class: %s  Confidence: %d%%" % (name.upper(), pct))

                        if score < 0.10:
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
                else:
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


# ═══════════════════════════════════════════════
# ENTRY POINTS
# ═══════════════════════════════════════════════
def play(nfc, leds, buz, accel, i2c, enow):
    """Called from main.py when the 'gestures' tag is tapped."""
    if accel is None:
        print("  Gestures requires accelerometer — not available")
        buz.reject()
        return

    _play_sound(buz, 'start')
    print("\n  === GESTURES ===")

    try:
        GesturesGame(nfc, leds, buz, accel, enow).run()
    finally:
        leds.off()

    print("\n  === RETURNING TO PROGRAMMING MODE ===\n")


def main():
    """Standalone entry point for testing without main.py."""
    print("\n" + "=" * 45)
    print("  Gestures — Train and Classify")
    print("=" * 45)

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

    print()
    play(nfc, leds, buz, accel, i2c, enow)


if __name__ == "__main__":
    main()
