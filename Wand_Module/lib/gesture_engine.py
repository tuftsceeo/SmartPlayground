"""
gesture_engine.py — Gesture Recognition with NFC-stored Templates
==================================================================
Goes in /lib/

Gesture templates are stored ON the NFC tags themselves.
Each gesture tag carries:
  - A "G:" marker identifying it as a gesture tag
  - The gesture name (up to 12 chars)
  - A centroid feature vector (17 floats, 68 bytes)

NFC Data Layout (MIFARE Classic 1K):
  Sector 1, block 4:  [47 3A] + gesture_name (14 bytes, null-padded)  = "G:triangle\0\0\0\0"
  Sector 1, block 5:  features[0:4]   — 4 floats (16 bytes)
  Sector 1, block 6:  features[4:8]   — 4 floats (16 bytes)
  Sector 2, block 8:  features[8:12]  — 4 floats (16 bytes)
  Sector 2, block 9:  features[12:16] — 4 floats (16 bytes)
  Sector 2, block 10: features[16:17] — 1 float + 12 bytes padding

Total: 17 floats x 4 bytes = 68 bytes + 16 byte header = 84 bytes

Usage:
    from gesture_engine import GestureEngine
    ge = GestureEngine(i2c, np, buzzer_pin=19)
    ge.init()

    # Read a gesture template from a tapped NFC tag
    gesture = ge.read_gesture_tag(nfc, tag)

    # Load it for recognition
    ge.load_gesture(gesture['name'], gesture['centroid'])

    # Capture a gesture and classify
    fv = ge.capture_gesture()
    name, conf = ge.classify(fv)
"""

import machine
import time
import math
import struct

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────
WINDOW_MS = 1500
SAMPLE_INTERVAL_MS = 10
MOTION_THRESHOLD_G = 1.4
PRE_SAMPLES = 15
COOLDOWN_MS = 800
CONFIDENCE_THRESHOLD = 0.60   # balance: 0.55 too loose, 0.65 too strict
MAX_DISTANCE = 2.2            # absolute ceiling — reject if best match > this

GESTURE_MARKER = b'G:'

# MIFARE write command
_MIFARE_WRITE = 0xA0
_CMD_INDATAEXCHANGE = 0x40

# How many floats per block (16 bytes / 4 bytes per float)
_FLOATS_PER_BLOCK = 4


def _write_mifare_block(nfc, block, data):
    """
    Write 16 bytes to a MIFARE Classic block.
    Works with the /lib/pn532.py driver (which lacks a write method).
    Must be authenticated first.
    """
    if len(data) != 16:
        raise ValueError("Must write exactly 16 bytes, got %d" % len(data))
    params = bytes([0x01, _MIFARE_WRITE, block]) + bytes(data)
    resp = nfc._send_command(_CMD_INDATAEXCHANGE, params, timeout=1000)
    status = resp[0] & 0x3F
    if status != 0x00:
        raise RuntimeError("Write error: status 0x%02X" % status)
    return True

# Block layout for MIFARE Classic
# Sector 1: blocks 4,5,6  (block 7 = trailer)
# Sector 2: blocks 8,9,10 (block 11 = trailer)
_HEADER_BLOCK = 4
_FEATURE_BLOCKS = [5, 6, 8, 9, 10]


class _Ring:
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
        self.idx = 0
        self.count = 0


class GestureEngine:
    def __init__(self, i2c, neopixel, buzzer_pin=19, accel_addr=0x19, num_leds=25):
        self.i2c = i2c
        self.np = neopixel
        self.num_leds = num_leds
        self.buz_pin = buzzer_pin
        self.accel_addr = accel_addr
        self.loaded_gestures = []
        self.last_gesture_name = None

    # ─── HARDWARE ─────────────────────────────

    def init(self):
        who = self.i2c.readfrom_mem(self.accel_addr, 0x0F, 1)[0]
        if who != 0x44:
            raise RuntimeError("LIS2DW12 not found (0x%02X)" % who)
        self.i2c.writeto_mem(self.accel_addr, 0x21, bytes([0x40]))
        time.sleep_ms(10)
        self.i2c.writeto_mem(self.accel_addr, 0x20, bytes([0x54]))
        self.i2c.writeto_mem(self.accel_addr, 0x25, bytes([0x14]))
        time.sleep_ms(20)

    def _accel_read(self):
        d = self.i2c.readfrom_mem(self.accel_addr, 0x28, 6)
        s = 0.000122
        return (
            struct.unpack('<h', d[0:2])[0] * s,
            struct.unpack('<h', d[2:4])[0] * s,
            struct.unpack('<h', d[4:6])[0] * s,
        )

    def _beep(self, freq=1000, ms=80):
        buz = machine.PWM(machine.Pin(self.buz_pin))
        buz.freq(freq)
        buz.duty_u16(32768)
        time.sleep_ms(ms)
        buz.duty_u16(0)
        buz.deinit()

    def _leds_off(self):
        for i in range(self.num_leds):
            self.np[i] = (0, 0, 0)
        self.np.write()

    def _leds_solid(self, color):
        for i in range(self.num_leds):
            self.np[i] = color
        self.np.write()

    def _leds_dim(self, color, count=3):
        for i in range(self.num_leds):
            self.np[i] = color if i < count else (0, 0, 0)
        self.np.write()

    def _leds_breathe(self, base_color, frame):
        brightness = abs(math.sin(frame * 0.05))
        r = int(base_color[0] * brightness)
        g = int(base_color[1] * brightness)
        b = int(base_color[2] * brightness)
        for i in range(self.num_leds):
            self.np[i] = (r, g, b)
        self.np.write()

    def _leds_celebration(self, color):
        for _ in range(3):
            self._leds_solid(color)
            time.sleep_ms(80)
            self._leds_off()
            time.sleep_ms(60)
        for i in range(self.num_leds):
            self.np[i] = color
            self.np.write()
            time.sleep_ms(20)
        time.sleep_ms(300)
        r, g, b = color
        for step in range(10, -1, -1):
            sc = step / 10
            self._leds_solid((int(r * sc), int(g * sc), int(b * sc)))
            time.sleep_ms(30)
        self._leds_off()

    # ─── FEATURE EXTRACTION ──────────────────

    @staticmethod
    def _mean(vals):
        return sum(vals) / len(vals) if vals else 0.0

    @staticmethod
    def _std(vals, mu):
        if len(vals) < 2:
            return 0.0
        return math.sqrt(sum((v - mu) ** 2 for v in vals) / len(vals))

    @staticmethod
    def _rms(vals):
        return math.sqrt(sum(v * v for v in vals) / len(vals)) if vals else 0.0

    @staticmethod
    def _count_peaks(vals, threshold=0.05):
        if len(vals) < 3:
            return 0
        peaks = 0
        for i in range(1, len(vals) - 1):
            if vals[i] > vals[i-1] and vals[i] > vals[i+1] and vals[i] > threshold:
                peaks += 1
        return peaks

    def extract_features(self, samples):
        """Extract 17-float feature vector from [(x,y,z), ...] samples."""
        if not samples:
            return [0.0] * 17
        xs = [s[0] for s in samples]
        ys = [s[1] for s in samples]
        zs = [s[2] for s in samples]
        mags = [math.sqrt(s[0]**2 + s[1]**2 + s[2]**2) for s in samples]
        features = []
        for axis in (xs, ys, zs):
            mu = self._mean(axis)
            features.append(min(axis))
            features.append(max(axis))
            features.append(self._std(axis, mu))
            features.append(self._count_peaks(axis))
            features.append(self._rms(axis))
        features.append(self._mean(mags))
        features.append(max(mags))
        return features

    # ─── CLASSIFICATION ───────────────────────

    @staticmethod
    def _distance(a, b):
        total = 0.0
        for i in range(len(a)):
            if i in (3, 8, 13):
                diff = (a[i] - b[i]) * 0.1
            else:
                diff = a[i] - b[i]
            total += diff * diff
        return math.sqrt(total)

    def classify(self, fv):
        """
        Classify against loaded gestures.
        Returns (gesture_name, confidence, distance) or (None, 0.0, 999).

        Applies both relative confidence threshold and absolute
        distance ceiling to reduce false positives from random motion.
        """
        if not self.loaded_gestures:
            return None, 0.0, 999.0

        dists = {}
        for g in self.loaded_gestures:
            dists[g['name']] = self._distance(fv, g['centroid'])

        sorted_names = sorted(dists, key=lambda n: dists[n])
        best = sorted_names[0]
        best_dist = dists[best]

        # Absolute distance gate — reject if too far from any template
        if best_dist > MAX_DISTANCE:
            return None, 0.0, best_dist

        if len(sorted_names) >= 2:
            second_dist = dists[sorted_names[1]]
            total = best_dist + second_dist
            conf = 1.0 - (best_dist / total) if total > 0.001 else 1.0
        else:
            conf = max(0.0, 1.0 - best_dist / 2.0)

        return best, conf, best_dist

    # ─── NFC TAG READ/WRITE ───────────────────

    @staticmethod
    def _floats_to_bytes(floats):
        return b''.join(struct.pack('<f', f) for f in floats)

    @staticmethod
    def _bytes_to_floats(data, count):
        floats = []
        for i in range(count):
            offset = i * 4
            if offset + 4 <= len(data):
                floats.append(struct.unpack('<f', data[offset:offset+4])[0])
            else:
                floats.append(0.0)
        return floats

    def build_gesture_tag_data(self, name, centroid):
        name_bytes = name.encode('utf-8')[:12]
        header = GESTURE_MARKER + name_bytes + b'\x00' * (14 - len(name_bytes))
        assert len(header) == 16
        blocks = {_HEADER_BLOCK: header}
        feat_bytes = self._floats_to_bytes(centroid)
        for i, blk in enumerate(_FEATURE_BLOCKS):
            start = i * 16
            end = start + 16
            chunk = feat_bytes[start:end]
            if len(chunk) < 16:
                chunk = chunk + b'\x00' * (16 - len(chunk))
            blocks[blk] = chunk
        return blocks

    def is_gesture_tag(self, header_data):
        return header_data[:2] == GESTURE_MARKER

    def parse_gesture_header(self, header_data):
        if not self.is_gesture_tag(header_data):
            return None
        name_bytes = header_data[2:]
        null_pos = name_bytes.find(b'\x00')
        if null_pos >= 0:
            name_bytes = name_bytes[:null_pos]
        return name_bytes.decode('utf-8', 'replace').strip()

    def read_gesture_tag(self, nfc, tag):
        from pn532 import MIFARE_AUTH_A, MIFARE_AUTH_B
        common_keys = [
            b'\xFF\xFF\xFF\xFF\xFF\xFF',
            b'\xD3\xF7\xD3\xF7\xD3\xF7',
            b'\xA0\xA1\xA2\xA3\xA4\xA5',
            b'\x00\x00\x00\x00\x00\x00',
        ]
        all_blocks = [_HEADER_BLOCK] + _FEATURE_BLOCKS
        block_data = {}
        for blk in all_blocks:
            sector = blk // 4
            first_block = sector * 4
            resel = nfc.read_passive_target(timeout=200)
            if resel is None:
                return None
            authed = False
            for key in common_keys:
                for kt in [MIFARE_AUTH_A, MIFARE_AUTH_B]:
                    if nfc.mifare_auth_block(resel['uid'], first_block, key, kt):
                        authed = True
                        break
                if authed:
                    break
            if not authed:
                return None
            try:
                block_data[blk] = nfc.mifare_read_block(blk)
            except Exception:
                return None
        header = bytes(block_data[_HEADER_BLOCK])
        if not self.is_gesture_tag(header):
            return None
        name = self.parse_gesture_header(header)
        feat_bytes = b''
        for blk in _FEATURE_BLOCKS:
            feat_bytes += bytes(block_data[blk])
        centroid = self._bytes_to_floats(feat_bytes, 17)
        return {'name': name, 'centroid': centroid}

    def write_gesture_tag(self, nfc, tag, name, centroid):
        from pn532 import MIFARE_AUTH_A, MIFARE_AUTH_B
        common_keys = [
            b'\xFF\xFF\xFF\xFF\xFF\xFF',
            b'\xD3\xF7\xD3\xF7\xD3\xF7',
            b'\xA0\xA1\xA2\xA3\xA4\xA5',
            b'\x00\x00\x00\x00\x00\x00',
        ]
        if not name or len(name) > 12:
            print("  [ERR] Name must be 1-12 chars, got '%s'" % name)
            return False
        if len(centroid) != 17:
            print("  [ERR] Centroid must be 17 floats, got %d" % len(centroid))
            return False
        blocks = self.build_gesture_tag_data(name, centroid)
        print("  Writing %d blocks: %s" % (len(blocks), list(blocks.keys())))
        sorted_blocks = sorted(blocks.items())
        for blk, data in sorted_blocks:
            sector = blk // 4
            first_block = sector * 4
            if blk == 0:
                print("  [SKIP] Block 0 (manufacturer)")
                continue
            if blk % 4 == 3:
                print("  [SKIP] Block %d (sector trailer)" % blk)
                continue
            print("  Block %d (sector %d)..." % (blk, sector), end="")
            resel = nfc.read_passive_target(timeout=300)
            if resel is None:
                print(" FAIL -- tag not found")
                return False
            authed = False
            for key in common_keys:
                for kt in [MIFARE_AUTH_A, MIFARE_AUTH_B]:
                    resel = nfc.read_passive_target(timeout=200)
                    if resel is None:
                        continue
                    if nfc.mifare_auth_block(resel['uid'], first_block, key, kt):
                        authed = True
                        break
                if authed:
                    break
            if not authed:
                print(" FAIL -- auth failed")
                return False
            try:
                _write_mifare_block(nfc, blk, data)
            except Exception as e:
                print(" FAIL -- write error: %s" % str(e))
                return False
            time.sleep_ms(50)
            resel = nfc.read_passive_target(timeout=300)
            if resel is None:
                print(" wrote, verify SKIP (tag gone)")
                continue
            authed2 = False
            for key in common_keys:
                for kt in [MIFARE_AUTH_A, MIFARE_AUTH_B]:
                    resel = nfc.read_passive_target(timeout=200)
                    if resel is None:
                        break
                    if nfc.mifare_auth_block(resel['uid'], first_block, key, kt):
                        authed2 = True
                        break
                if authed2:
                    break
            if authed2:
                try:
                    readback = nfc.mifare_read_block(blk)
                    if bytes(readback) == bytes(data):
                        print(" OK (verified)")
                    else:
                        print(" MISMATCH!")
                        return False
                except Exception as e:
                    print(" wrote, verify read failed: %s" % str(e))
            else:
                print(" wrote, verify auth failed")
        print("  All blocks written successfully.")
        return True

    # ─── GESTURE LOADING ──────────────────────

    def load_gesture(self, name, centroid):
        for g in self.loaded_gestures:
            if g['name'] == name:
                g['centroid'] = centroid
                return
        self.loaded_gestures.append({'name': name, 'centroid': list(centroid)})

    def load_from_tag(self, nfc, tag):
        gesture = self.read_gesture_tag(nfc, tag)
        if gesture is None:
            return None
        self.load_gesture(gesture['name'], gesture['centroid'])
        return gesture['name']

    def clear_loaded(self):
        self.loaded_gestures.clear()

    # ─── MOTION-GATED CAPTURE ─────────────────

    def capture_gesture(self, timeout_ms=15000, breathe_color=None):
        ring = _Ring(PRE_SAMPLES)
        start = time.ticks_ms()
        frame = 0
        while True:
            x, y, z = self._accel_read()
            mag = math.sqrt(x*x + y*y + z*z)
            ring.push((x, y, z))
            if breathe_color and frame % 3 == 0:
                self._leds_breathe(breathe_color, frame)
            frame += 1
            if mag > MOTION_THRESHOLD_G:
                pre = ring.get_all()
                ring.clear()
                if breathe_color:
                    self._leds_solid(breathe_color)
                samples = list(pre)
                remaining_ms = WINDOW_MS - (len(pre) * SAMPLE_INTERVAL_MS)
                cap_start = time.ticks_ms()
                while time.ticks_diff(time.ticks_ms(), cap_start) < remaining_ms:
                    samples.append(self._accel_read())
                    time.sleep_ms(SAMPLE_INTERVAL_MS)
                return self.extract_features(samples)
            if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
                return None
            time.sleep_ms(SAMPLE_INTERVAL_MS)

    # ─── NON-BLOCKING GESTURE CHECK ──────────
    # For use in the event loop: poll once per cycle

    def poll_motion(self):
        """
        Check if motion exceeds threshold RIGHT NOW.
        Returns True if a gesture capture should begin.
        Non-blocking — single accel read.
        """
        x, y, z = self._accel_read()
        mag = math.sqrt(x*x + y*y + z*z)
        return mag > MOTION_THRESHOLD_G

    def capture_and_classify(self):
        """
        Capture a full gesture window (blocking ~1.5s) and classify.
        Call this AFTER poll_motion() returns True.
        Returns (gesture_name, confidence, best_dist, all_dists_dict).
        all_dists_dict maps gesture_name -> distance for all loaded gestures.
        """
        ring = _Ring(PRE_SAMPLES)
        # Quick pre-fill
        for _ in range(PRE_SAMPLES):
            ring.push(self._accel_read())
            time.sleep_ms(SAMPLE_INTERVAL_MS)

        pre = ring.get_all()
        samples = list(pre)
        remaining_ms = WINDOW_MS - (len(pre) * SAMPLE_INTERVAL_MS)
        cap_start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), cap_start) < remaining_ms:
            samples.append(self._accel_read())
            time.sleep_ms(SAMPLE_INTERVAL_MS)

        fv = self.extract_features(samples)

        # Compute all distances
        all_dists = {}
        for g in self.loaded_gestures:
            all_dists[g['name']] = self._distance(fv, g['centroid'])

        name, conf, best_dist = self.classify(fv)
        return name, conf, best_dist, all_dists

    # ─── BLOCKING WAIT (legacy, for standalone use) ──

    def wait_for_gesture(self, nfc=None, read_tag_fn=None, timeout_ms=15000):
        if not self.loaded_gestures:
            return None
        ring = _Ring(PRE_SAMPLES)
        last_capture = 0
        poll_count = 0
        self.last_gesture_name = None
        self._leds_dim((8, 0, 8), 3)
        while True:
            x, y, z = self._accel_read()
            mag = math.sqrt(x*x + y*y + z*z)
            ring.push((x, y, z))
            now = time.ticks_ms()
            if nfc and read_tag_fn and poll_count >= 30:
                poll_count = 0
                cmd, _ = read_tag_fn(nfc)
                if cmd == "stop":
                    self._leds_off()
                    return "stop"
            poll_count += 1
            if time.ticks_diff(now, last_capture) < COOLDOWN_MS:
                time.sleep_ms(SAMPLE_INTERVAL_MS)
                continue
            if mag > MOTION_THRESHOLD_G:
                pre = ring.get_all()
                ring.clear()
                samples = list(pre)
                remaining_ms = WINDOW_MS - (len(pre) * SAMPLE_INTERVAL_MS)
                cap_start = time.ticks_ms()
                while time.ticks_diff(time.ticks_ms(), cap_start) < remaining_ms:
                    samples.append(self._accel_read())
                    time.sleep_ms(SAMPLE_INTERVAL_MS)
                fv = self.extract_features(samples)
                name, conf, dist = self.classify(fv)
                if name is not None and conf >= CONFIDENCE_THRESHOLD:
                    self.last_gesture_name = name
                    self._beep(1000, 60)
                    self._leds_celebration((15, 0, 15))
                    return "fired"
                last_capture = time.ticks_ms()
                self._leds_dim((8, 0, 8), 3)
            time.sleep_ms(SAMPLE_INTERVAL_MS)

    def status(self):
        if not self.loaded_gestures:
            print("  No gestures loaded.")
            return
        for g in self.loaded_gestures:
            c = g['centroid']
            print("  %s: mag_max=%.2f x_std=%.3f y_std=%.3f" % (
                g['name'], c[16], c[2], c[7]))