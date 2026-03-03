"""
Gesture Recognition Test — Sandboxed
======================================
Board: Seeed XIAO ESP32-C6
Accel: LIS2DW12 on I2C (SDA=22, SCL=23, addr=0x19)
LEDs:  25x SK6812 on GPIO20 (feedback)
Buzzer: GPIO19 (feedback)

Approach inspired by micro:bit CreateAI / ttseng/microbit-ml:
  - Collect a 1.5s window of accel samples at ~100Hz
  - Extract statistical features: min, max, std, peak_count, rms per axis + magnitude
  - Compare against stored gesture templates using distance metric
  - Nearest-neighbor classification with confidence threshold

Flow:
  1. RECORD mode: perform a gesture 3+ times to teach it
  2. RECOGNIZE mode: perform gestures and see them classified
  3. All via REPL menu — no NFC needed

Press Ctrl+C at any time to return to menu.
"""

import machine
import time
import math
import struct
from neopixel import NeoPixel

# ─────────────────────────────────────────────
# HARDWARE
# ─────────────────────────────────────────────
I2C_SDA = 22
I2C_SCL = 23
ACCEL_ADDR = 0x19
NEOPIXEL_PIN = 20
NUM_LEDS = 25
BUZZER_PIN = 19

i2c = machine.SoftI2C(sda=machine.Pin(I2C_SDA), scl=machine.Pin(I2C_SCL), freq=400_000)
np = NeoPixel(machine.Pin(NEOPIXEL_PIN), NUM_LEDS)

# ─────────────────────────────────────────────
# ACCEL SETUP (inline — no lib dependency)
# ─────────────────────────────────────────────
def accel_init():
    who = i2c.readfrom_mem(ACCEL_ADDR, 0x0F, 1)[0]
    if who != 0x44:
        raise RuntimeError("LIS2DW12 not found (0x%02X)" % who)
    i2c.writeto_mem(ACCEL_ADDR, 0x21, bytes([0x40]))  # soft reset
    time.sleep_ms(10)
    i2c.writeto_mem(ACCEL_ADDR, 0x20, bytes([0x54]))  # 100Hz high-perf
    i2c.writeto_mem(ACCEL_ADDR, 0x25, bytes([0x14]))  # +/-4g, low noise
    time.sleep_ms(20)
    print("  Accel OK (100Hz, +/-4g)")

def accel_read():
    """Read (x, y, z) in g."""
    d = i2c.readfrom_mem(ACCEL_ADDR, 0x28, 6)
    s = 0.000122  # 4g / 32768
    x = struct.unpack('<h', d[0:2])[0] * s
    y = struct.unpack('<h', d[2:4])[0] * s
    z = struct.unpack('<h', d[4:6])[0] * s
    return x, y, z

# ─────────────────────────────────────────────
# LED + BUZZER HELPERS
# ─────────────────────────────────────────────
def leds_off():
    for i in range(NUM_LEDS):
        np[i] = (0, 0, 0)
    np.write()

def leds_solid(r, g, b):
    for i in range(NUM_LEDS):
        np[i] = (r, g, b)
    np.write()

def leds_countdown(color, count):
    """Show countdown on LEDs: light up proportional segments."""
    for step in range(count, 0, -1):
        lit = int(step / count * NUM_LEDS)
        for i in range(NUM_LEDS):
            np[i] = color if i < lit else (0, 0, 0)
        np.write()
        beep(800 + (count - step) * 200, 80)
        time.sleep_ms(920)
    leds_off()

def leds_flash(r, g, b, times=2):
    for _ in range(times):
        leds_solid(r, g, b)
        time.sleep_ms(100)
        leds_off()
        time.sleep_ms(80)

def beep(freq=1000, ms=80):
    buz = machine.PWM(machine.Pin(BUZZER_PIN))
    buz.freq(freq)
    buz.duty_u16(32768)
    time.sleep_ms(ms)
    buz.duty_u16(0)
    buz.deinit()

# ─────────────────────────────────────────────
# DATA COLLECTION — capture a gesture window
# ─────────────────────────────────────────────
WINDOW_MS = 1500       # 1.5 second capture window
SAMPLE_INTERVAL_MS = 10  # ~100Hz

def capture_window():
    """
    Capture accelerometer data for WINDOW_MS milliseconds.
    Returns list of (x, y, z) tuples.
    """
    samples = []
    # Show recording: red
    leds_solid(15, 0, 0)
    
    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < WINDOW_MS:
        samples.append(accel_read())
        time.sleep_ms(SAMPLE_INTERVAL_MS)
    
    leds_off()
    return samples

# ─────────────────────────────────────────────
# FEATURE EXTRACTION
# Inspired by micro:bit ML approach:
#   per axis: min, max, std, peak_count, rms
#   plus: magnitude_mean, magnitude_max
# Total: 5*3 + 2 = 17 features
# ─────────────────────────────────────────────

def _mean(vals):
    if not vals:
        return 0.0
    return sum(vals) / len(vals)

def _std(vals, mu):
    if len(vals) < 2:
        return 0.0
    variance = sum((v - mu) ** 2 for v in vals) / len(vals)
    return math.sqrt(variance)

def _rms(vals):
    if not vals:
        return 0.0
    return math.sqrt(sum(v * v for v in vals) / len(vals))

def _count_peaks(vals, threshold=0.05):
    """Count positive peaks (local maxima above threshold)."""
    if len(vals) < 3:
        return 0
    peaks = 0
    for i in range(1, len(vals) - 1):
        if vals[i] > vals[i-1] and vals[i] > vals[i+1] and vals[i] > threshold:
            peaks += 1
    return peaks

def extract_features(samples):
    """
    Extract feature vector from a list of (x, y, z) samples.
    Returns a list of 17 floats.
    """
    if not samples:
        return [0.0] * 17
    
    xs = [s[0] for s in samples]
    ys = [s[1] for s in samples]
    zs = [s[2] for s in samples]
    mags = [math.sqrt(s[0]**2 + s[1]**2 + s[2]**2) for s in samples]
    
    features = []
    for axis_vals in (xs, ys, zs):
        mu = _mean(axis_vals)
        features.append(min(axis_vals))            # min
        features.append(max(axis_vals))            # max
        features.append(_std(axis_vals, mu))       # std
        features.append(_count_peaks(axis_vals))   # peak count
        features.append(_rms(axis_vals))           # rms
    
    # Magnitude features
    features.append(_mean(mags))   # magnitude mean
    features.append(max(mags))     # magnitude max
    
    return features

FEATURE_NAMES = [
    "x_min", "x_max", "x_std", "x_peaks", "x_rms",
    "y_min", "y_max", "y_std", "y_peaks", "y_rms",
    "z_min", "z_max", "z_std", "z_peaks", "z_rms",
    "mag_mean", "mag_max",
]

# ─────────────────────────────────────────────
# GESTURE DATABASE
# Each gesture: { name: str, templates: [feature_vector, ...] }
# ─────────────────────────────────────────────
gestures = []  # list of dicts

def add_gesture(name):
    """Create a new gesture category."""
    for g in gestures:
        if g['name'] == name:
            print("  Gesture '%s' already exists" % name)
            return g
    g = {'name': name, 'templates': [], 'centroid': None}
    gestures.append(g)
    return g

def record_template(gesture_dict):
    """Record one sample for a gesture. Returns the feature vector."""
    samples = capture_window()
    fv = extract_features(samples)
    gesture_dict['templates'].append(fv)
    _update_centroid(gesture_dict)
    return fv

def _update_centroid(gesture_dict):
    """Recompute centroid (mean feature vector) for a gesture."""
    templates = gesture_dict['templates']
    if not templates:
        gesture_dict['centroid'] = None
        return
    n = len(templates)
    dim = len(templates[0])
    centroid = [0.0] * dim
    for t in templates:
        for i in range(dim):
            centroid[i] += t[i]
    for i in range(dim):
        centroid[i] /= n
    gesture_dict['centroid'] = centroid

# ─────────────────────────────────────────────
# CLASSIFICATION
# ─────────────────────────────────────────────

def _distance(a, b):
    """Euclidean distance between two feature vectors, with normalization."""
    if len(a) != len(b):
        return 999999.0
    total = 0.0
    for i in range(len(a)):
        # Normalize peak counts (indices 3, 8, 13) differently
        if i in (3, 8, 13):
            # Peak counts: scale by 0.1 so they don't dominate
            diff = (a[i] - b[i]) * 0.1
        else:
            diff = a[i] - b[i]
        total += diff * diff
    return math.sqrt(total)

def classify(feature_vector):
    """
    Classify a feature vector against all gesture centroids.
    Returns (gesture_name, confidence, distances_dict) or (None, 0, {}).
    
    Confidence = 1 - (best_dist / (best_dist + second_best_dist))
    If only one gesture, confidence based on absolute distance.
    """
    if not gestures:
        return None, 0.0, {}
    
    dists = {}
    for g in gestures:
        if g['centroid'] is None:
            continue
        d = _distance(feature_vector, g['centroid'])
        dists[g['name']] = d
    
    if not dists:
        return None, 0.0, {}
    
    sorted_names = sorted(dists, key=lambda n: dists[n])
    best_name = sorted_names[0]
    best_dist = dists[best_name]
    
    if len(sorted_names) >= 2:
        second_dist = dists[sorted_names[1]]
        # Confidence: how much closer is best vs second
        total = best_dist + second_dist
        if total < 0.001:
            confidence = 1.0  # both zero — perfect match
        else:
            confidence = 1.0 - (best_dist / total)
    else:
        # Single gesture — use absolute threshold
        # Lower distance = higher confidence
        confidence = max(0.0, 1.0 - best_dist / 2.0)
    
    return best_name, confidence, dists

# ─────────────────────────────────────────────
# INTERACTIVE MENU
# ─────────────────────────────────────────────

def print_header():
    print()
    print("=" * 50)
    print("  Gesture Recognition Test")
    print("  Window: %dms | ~%d samples" % (WINDOW_MS, WINDOW_MS // SAMPLE_INTERVAL_MS))
    print("=" * 50)

def print_gestures():
    if not gestures:
        print("  No gestures recorded yet.")
        return
    print("  Gestures:")
    for i, g in enumerate(gestures):
        n = len(g['templates'])
        print("    %d. %s  (%d samples)" % (i + 1, g['name'], n))

def print_features(fv):
    """Print a feature vector nicely."""
    print("  Features:")
    for i, name in enumerate(FEATURE_NAMES):
        if i in (3, 8, 13):
            print("    %-10s %d" % (name, int(fv[i])))
        else:
            print("    %-10s %+.4f" % (name, fv[i]))

def menu_record():
    """Record gesture samples interactively."""
    name = input("  Gesture name (e.g. flick, circle, stab): ").strip().lower()
    if not name:
        return
    
    g = add_gesture(name)
    
    n_str = input("  How many samples? [5]: ").strip()
    n = int(n_str) if n_str else 5
    
    print()
    print("  Recording %d samples of '%s'" % (n, name))
    print("  Hold the wand ready. 3-2-1 countdown before each capture.")
    print("  Perform the gesture when LEDs turn RED.")
    print()
    
    for i in range(n):
        input("  Press Enter for sample %d/%d..." % (i + 1, n))
        
        # Countdown
        leds_countdown((0, 0, 15), 3)
        
        # Capture
        print("  >>> GO! <<<")
        fv = record_template(g)
        
        # Confirm
        leds_flash(0, 20, 0, times=2)
        beep(1200, 60)
        
        print("  Sample %d recorded (%d peaks x, %d peaks y, %d peaks z, mag_max=%.2f)" % (
            i + 1, int(fv[3]), int(fv[8]), int(fv[13]), fv[16]))
    
    print()
    print("  '%s' now has %d total samples." % (name, len(g['templates'])))

def menu_recognize():
    """Live recognition loop."""
    if not gestures:
        print("  No gestures recorded! Record some first.")
        return
    
    ready = sum(1 for g in gestures if g['centroid'] is not None)
    if ready < 1:
        print("  Need at least 1 gesture with samples.")
        return
    
    print()
    print("  === RECOGNITION MODE ===")
    print("  Perform a gesture when LEDs turn RED.")
    print("  Press Ctrl+C to stop.")
    print()
    
    CONFIDENCE_THRESHOLD = 0.55
    
    while True:
        try:
            input("  Press Enter to capture (Ctrl+C to stop)...")
            
            # Short countdown
            leds_countdown((0, 0, 15), 2)
            
            print("  >>> GO! <<<")
            samples = capture_window()
            fv = extract_features(samples)
            
            name, confidence, dists = classify(fv)
            
            pct = int(confidence * 100)
            
            print()
            if name and confidence >= CONFIDENCE_THRESHOLD:
                print("  >> DETECTED: %s  (%d%% confidence)" % (name, pct))
                # Color feedback per gesture
                idx = 0
                for i, g in enumerate(gestures):
                    if g['name'] == name:
                        idx = i
                        break
                colors = [
                    (0, 30, 0),    # green
                    (30, 0, 0),    # red
                    (0, 0, 30),    # blue
                    (20, 10, 0),   # yellow
                    (15, 0, 15),   # purple
                    (0, 15, 15),   # cyan
                ]
                c = colors[idx % len(colors)]
                leds_flash(c[0], c[1], c[2], times=3)
                beep(800 + idx * 200, 100)
            else:
                print("  >> UNKNOWN (best guess: %s at %d%%)" % (name or "?", pct))
                leds_flash(10, 5, 0, times=1)
                beep(300, 200)
            
            # Show distances
            if dists:
                print("  Distances: %s" % ", ".join(
                    "%s=%.3f" % (n, d) for n, d in sorted(dists.items(), key=lambda x: x[1])
                ))
            print()
            
        except KeyboardInterrupt:
            leds_off()
            print("\n  Stopped recognition.")
            break

def menu_details():
    """Show detailed feature vectors for all gestures."""
    if not gestures:
        print("  No gestures.")
        return
    for g in gestures:
        print("\n  --- %s (%d samples) ---" % (g['name'], len(g['templates'])))
        if g['centroid']:
            print("  Centroid:")
            print_features(g['centroid'])
        for i, t in enumerate(g['templates']):
            print("  Sample %d:" % (i + 1))
            print_features(t)

def menu_compare():
    """Side-by-side centroid comparison."""
    if len(gestures) < 2:
        print("  Need 2+ gestures to compare.")
        return
    
    print()
    print("  %-12s" % "Feature", end="")
    for g in gestures:
        print("  %-12s" % g['name'], end="")
    print()
    print("  " + "-" * (12 + 14 * len(gestures)))
    
    for i, fname in enumerate(FEATURE_NAMES):
        print("  %-12s" % fname, end="")
        for g in gestures:
            if g['centroid']:
                v = g['centroid'][i]
                if i in (3, 8, 13):
                    print("  %-12d" % int(v), end="")
                else:
                    print("  %-12.4f" % v, end="")
            else:
                print("  %-12s" % "---", end="")
        print()

def menu_clear():
    """Clear all gestures."""
    gestures.clear()
    print("  All gestures cleared.")

def menu_raw():
    """Show live accelerometer values for 5 seconds."""
    print("  Raw accel for 5 seconds:")
    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < 5000:
        x, y, z = accel_read()
        mag = math.sqrt(x*x + y*y + z*z)
        print("  X:%+.3f  Y:%+.3f  Z:%+.3f  mag:%.3f" % (x, y, z, mag))
        time.sleep_ms(100)

def main():
    print("\n  Initializing...")
    accel_init()
    leds_off()
    beep(600, 50)
    time.sleep_ms(30)
    beep(900, 50)
    
    print_header()
    
    while True:
        print()
        print("  ┌─────────────────────────────┐")
        print("  │  r = Record gestures        │")
        print("  │  g = Recognize (live test)   │")
        print("  │  d = Detail (show features)  │")
        print("  │  c = Compare centroids       │")
        print("  │  w = Raw accel (5 sec)       │")
        print("  │  x = Clear all               │")
        print("  │  q = Quit                    │")
        print("  └─────────────────────────────┘")
        print_gestures()
        
        try:
            choice = input("\n  > ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            break
        
        if choice == 'r':
            menu_record()
        elif choice == 'g':
            menu_recognize()
        elif choice == 'd':
            menu_details()
        elif choice == 'c':
            menu_compare()
        elif choice == 'w':
            menu_raw()
        elif choice == 'x':
            menu_clear()
        elif choice == 'q':
            break
        else:
            print("  Unknown option.")
    
    leds_off()
    print("\n  Done.")

if __name__ == "__main__":
    main()