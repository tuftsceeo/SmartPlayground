"""
Gesture Trainer + NFC Writer
==============================
One-time tool to train gesture templates and write them to NFC tags.

Flow:
  1. Choose a gesture name (triangle, circle, hit, etc.)
  2. Record N samples (with countdown + LED feedback)
  3. View the computed centroid
  4. Place a blank MIFARE Classic tag and write the gesture data
  5. Verify by reading back

The written tag will be recognized by gesture_engine.py in main.py.

Requires: /lib/pn532.py, /lib/gesture_engine.py
"""

import machine
import time
import math
import struct
from neopixel import NeoPixel

from pn532 import PN532, MIFARE_AUTH_A, MIFARE_AUTH_B
from gesture_engine import GestureEngine

# ─────────────────────────────────────────────
# HARDWARE
# ─────────────────────────────────────────────
I2C_SDA = 22
I2C_SCL = 23
NEOPIXEL_PIN = 20
NUM_LEDS = 25
BUZZER_PIN = 19
PN532_ADDR = 0x24

i2c = machine.SoftI2C(sda=machine.Pin(I2C_SDA), scl=machine.Pin(I2C_SCL), freq=100_000)
np = NeoPixel(machine.Pin(NEOPIXEL_PIN), NUM_LEDS)

FEATURE_NAMES = [
    "x_min", "x_max", "x_std", "x_peaks", "x_rms",
    "y_min", "y_max", "y_std", "y_peaks", "y_rms",
    "z_min", "z_max", "z_std", "z_peaks", "z_rms",
    "mag_mean", "mag_max",
]

# ─────────────────────────────────────────────
# LED/BUZZER HELPERS
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
# MANUAL CAPTURE (with countdown)
# ─────────────────────────────────────────────
def capture_with_countdown(ge):
    """3-2-1 countdown, then 1.5s capture. Returns feature vector."""
    leds_countdown((0, 0, 15), 3)
    print("  >>> GO! <<<")
    leds_solid(15, 0, 0)  # red = recording
    
    # Direct capture (timed window, not motion-gated)
    samples = []
    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < 1500:
        samples.append(ge._accel_read())
        time.sleep_ms(10)
    
    leds_off()
    fv = ge.extract_features(samples)
    leds_flash(0, 20, 0, times=2)
    beep(1200, 60)
    return fv

# ─────────────────────────────────────────────
# TRAINING
# ─────────────────────────────────────────────
trained_gestures = {}  # name -> {'templates': [...], 'centroid': [...]}

def compute_centroid(templates):
    n = len(templates)
    dim = len(templates[0])
    centroid = [0.0] * dim
    for t in templates:
        for i in range(dim):
            centroid[i] += t[i]
    for i in range(dim):
        centroid[i] /= n
    return centroid

def menu_train(ge):
    name = input("  Gesture name (e.g. triangle, circle, hit): ").strip().lower()
    if not name:
        return
    if len(name) > 12:
        print("  Name too long (max 12 chars)")
        return

    n_str = input("  How many samples? [5]: ").strip()
    n = int(n_str) if n_str else 5

    templates = []
    print()
    print("  Training '%s' with %d samples" % (name, n))
    print("  3-2-1 countdown before each. Perform the gesture when RED.")
    print()

    for i in range(n):
        input("  Press Enter for sample %d/%d..." % (i + 1, n))
        fv = capture_with_countdown(ge)
        templates.append(fv)
        print("  Sample %d: peaks(%d,%d,%d) mag_max=%.2f" % (
            i + 1, int(fv[3]), int(fv[8]), int(fv[13]), fv[16]))

    centroid = compute_centroid(templates)
    trained_gestures[name] = {'templates': templates, 'centroid': centroid}

    print()
    print("  '%s' trained with %d samples." % (name, n))
    print("  Centroid:")
    for i, fname in enumerate(FEATURE_NAMES):
        if i in (3, 8, 13):
            print("    %-10s %d" % (fname, int(centroid[i])))
        else:
            print("    %-10s %+.4f" % (fname, centroid[i]))

def menu_list():
    if not trained_gestures:
        print("  No gestures trained yet.")
        return
    print("  Trained gestures:")
    for name, data in trained_gestures.items():
        c = data['centroid']
        print("    %s  (%d samples)  mag_max=%.2f  x_std=%.3f  y_std=%.3f" % (
            name, len(data['templates']), c[16], c[2], c[7]))

# ─────────────────────────────────────────────
# NFC WRITE
# ─────────────────────────────────────────────
def menu_write(ge, nfc):
    if not trained_gestures:
        print("  No gestures trained. Train one first.")
        return

    names = list(trained_gestures.keys())
    print("  Available gestures:")
    for i, name in enumerate(names):
        print("    %d. %s" % (i + 1, name))

    choice = input("  Which gesture to write? [1]: ").strip()
    idx = int(choice) - 1 if choice else 0
    if idx < 0 or idx >= len(names):
        print("  Invalid choice.")
        return

    name = names[idx]
    centroid = trained_gestures[name]['centroid']

    print()
    print("  Will write '%s' to NFC tag." % name)
    print("  Place a MIFARE Classic tag on the reader and press Enter...")
    input()

    # Detect tag
    tag = nfc.read_passive_target(timeout=3000)
    if tag is None:
        print("  No tag detected!")
        beep(200, 300)
        return

    print("  Tag: %s (%s)" % (tag['uid_hex'], tag.get('sak', '?')))
    sak = tag.get('sak', 0)
    if sak not in (0x08, 0x18):
        print("  WARNING: This doesn't look like a MIFARE Classic tag (SAK=0x%02X)" % sak)
        cont = input("  Continue anyway? [y/N]: ").strip().lower()
        if cont != 'y':
            return

    # Pre-flight: try reading sector 1 to confirm tag is accessible
    print()
    print("  Pre-flight check...")
    resel = nfc.read_passive_target(timeout=500)
    if resel is None:
        print("  Tag disappeared! Keep it steady on the reader.")
        beep(200, 300)
        return

    from pn532 import MIFARE_AUTH_A
    test_auth = nfc.mifare_auth_block(resel['uid'], 4, b'\xFF\xFF\xFF\xFF\xFF\xFF', MIFARE_AUTH_A)
    if test_auth:
        print("  Pre-flight: sector 1 auth OK (default key A)")
    else:
        # Try re-select + key B
        resel = nfc.read_passive_target(timeout=300)
        if resel:
            from pn532 import MIFARE_AUTH_B
            test_auth = nfc.mifare_auth_block(resel['uid'], 4, b'\xFF\xFF\xFF\xFF\xFF\xFF', MIFARE_AUTH_B)
            if test_auth:
                print("  Pre-flight: sector 1 auth OK (default key B)")
        if not test_auth:
            print("  Pre-flight: sector 1 auth FAILED — tag may be locked")
            print("  Cannot write to this tag.")
            beep(200, 400)
            return

    # Show what we're about to write
    print()
    print("  Data to write:")
    print("    Name: '%s'" % name)
    print("    Features: %d floats" % len(centroid))
    print("    Blocks: 4, 5, 6, 8, 9, 10 (sectors 1-2)")
    print("    Total: 84 bytes")
    print()
    print("  Writing (keep tag steady)...")
    leds_solid(0, 0, 20)  # blue = writing

    ok = ge.write_gesture_tag(nfc, tag, name, centroid)

    if ok:
        leds_flash(0, 30, 0, times=3)
        beep(800, 60)
        time.sleep_ms(30)
        beep(1000, 60)
        time.sleep_ms(30)
        beep(1200, 100)
        print()
        print("  SUCCESS — '%s' written to tag %s" % (name, tag['uid_hex']))
    else:
        leds_flash(30, 0, 0, times=5)
        beep(200, 400)
        print()
        print("  WRITE FAILED — see block-by-block output above")
        print("  Tips:")
        print("    - Keep tag FLAT and STILL on the reader")
        print("    - Make sure it's MIFARE Classic 1K (SAK=0x08)")
        print("    - Try a different tag")

    leds_off()

# ─────────────────────────────────────────────
# NFC READ (test a tag)
# ─────────────────────────────────────────────
def menu_read(ge, nfc):
    print("  Place a gesture tag on the reader and press Enter...")
    input()

    tag = nfc.read_passive_target(timeout=3000)
    if tag is None:
        print("  No tag detected!")
        return

    print("  Tag: %s" % tag['uid_hex'])
    gesture = ge.read_gesture_tag(nfc, tag)

    if gesture is None:
        print("  Not a gesture tag (or read failed).")
        return

    print("  Gesture: '%s'" % gesture['name'])
    print("  Centroid:")
    for i, fname in enumerate(FEATURE_NAMES):
        v = gesture['centroid'][i]
        if i in (3, 8, 13):
            print("    %-10s %d" % (fname, int(v)))
        else:
            print("    %-10s %+.4f" % (fname, v))

# ─────────────────────────────────────────────
# LIVE TEST (load from tags + recognize)
# ─────────────────────────────────────────────
def menu_live_test(ge, nfc):
    print("  Load gesture tags first. Tap each gesture tag, Enter when done.")
    print()

    while True:
        cmd = input("  Tap a gesture tag + Enter (or 'done'): ").strip().lower()
        if cmd == 'done':
            break

        tag = nfc.read_passive_target(timeout=3000)
        if tag is None:
            print("  No tag detected.")
            continue

        name = ge.load_from_tag(nfc, tag)
        if name:
            print("  Loaded '%s'" % name)
            beep(1000, 60)
        else:
            print("  Not a gesture tag or read failed.")

    ge.status()
    n_loaded = len(ge.loaded_gestures)
    if n_loaded == 0:
        print("  No gestures loaded.")
        return

    print()
    print("  %d gesture(s) loaded. Starting live recognition..." % n_loaded)
    print("  Perform gestures. Press Ctrl+C to stop.")
    print()

    count = 0
    while True:
        try:
            result = ge.wait_for_gesture(timeout_ms=10000)
            if result == "fired":
                count += 1
                print("  [%d] Detected: %s" % (count, ge.last_gesture_name))
            elif result is None:
                pass  # timeout, keep looping
        except KeyboardInterrupt:
            break

    ge._leds_off()
    print("\n  %d gestures detected." % count)
    ge.clear_loaded()

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("\n" + "*" * 50)
    print("  Gesture Trainer + NFC Writer")
    print("  Train gestures, write to tags, test live")
    print("*" * 50)

    # Init NFC
    nfc = PN532(i2c, PN532_ADDR)
    try:
        ic, ver, rev = nfc.begin()
        print("  PN5%02X fw %d.%d — NFC ready" % (ic, ver, rev))
    except Exception as e:
        print("  NFC init failed: %s" % str(e))
        print("  (Training still works, writing won't)")
        nfc = None

    # Init gesture engine
    ge = GestureEngine(i2c, np, buzzer_pin=BUZZER_PIN)
    ge.init()
    print("  Accel ready.")

    beep(600, 50)
    time.sleep_ms(30)
    beep(900, 50)
    leds_off()

    while True:
        print()
        print("  ┌──────────────────────────────────┐")
        print("  │  t = Train a gesture              │")
        print("  │  l = List trained gestures         │")
        print("  │  w = Write to NFC tag              │")
        print("  │  r = Read a gesture tag            │")
        print("  │  g = Go live (load tags + test)    │")
        print("  │  x = Clear all trained             │")
        print("  │  q = Quit                          │")
        print("  └──────────────────────────────────┘")
        menu_list()

        try:
            choice = input("\n  > ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            break

        if choice == 't':
            menu_train(ge)
        elif choice == 'l':
            menu_list()
        elif choice == 'w':
            if nfc is None:
                print("  NFC not available!")
            else:
                menu_write(ge, nfc)
        elif choice == 'r':
            if nfc is None:
                print("  NFC not available!")
            else:
                menu_read(ge, nfc)
        elif choice == 'g':
            if nfc is None:
                print("  NFC not available!")
            else:
                menu_live_test(ge, nfc)
        elif choice == 'x':
            trained_gestures.clear()
            print("  Cleared.")
        elif choice == 'q':
            break

    leds_off()
    print("\n  Done.")

if __name__ == "__main__":
    main()