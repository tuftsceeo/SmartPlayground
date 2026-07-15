"""
PlaygroundV5 (Bag3) - NFC Tag Writer with LED Animation
========================================================
Board: Seeed XIAO ESP32-C6 (Bag3 wand)
NFC:   M5Stack RFID2 / WS1850S on I2C (SDA=GPIO22, SCL=GPIO23), addr 0x28
LEDs:  60x SK6812 on GPIO20 (6×10 matrix, row-major)
Button: GPIO0 (active LOW)
Buzzer: GPIO19

Requires ws1850s.py on the device (copied alongside this file).

This is the Bag3 port of the original PN532 writer. The WS1850S replaces
the PN532, so the embedded PN532 wire protocol is gone — every tag
operation now goes through the WS1850S driver. The NDEF building, LED
animations, buzzer feedback, and REPL flow are unchanged.

Flow:
  1. Type the text you want to write at the REPL prompt
  2. Press the button when a tag is on the reader
  3. LEDs animate during write
  4. Buzzer confirms success/failure
"""

import machine
import time
from neopixel import NeoPixel
from ws1850s import WS1850S

# ─────────────────────────────────────────────
# PIN CONFIG
# ─────────────────────────────────────────────
I2C_SDA   = 22
I2C_SCL   = 23
NEOPIXEL  = 20
SWITCH    = 0
BUZZER    = 19
NFC_ADDR  = 0x28      # WS1850S default (PN532 was 0x24)
NUM_LEDS  = 60        # 6×10 matrix on Bag3

# MIFARE key-type codes (match WS1850S PICC_AUTHENT1A/1B)
MIFARE_AUTH_A = WS1850S.PICC_AUTHENT1A
MIFARE_AUTH_B = WS1850S.PICC_AUTHENT1B

COMMON_KEYS = [
    b'\xFF\xFF\xFF\xFF\xFF\xFF',
    b'\xD3\xF7\xD3\xF7\xD3\xF7',
    b'\xA0\xA1\xA2\xA3\xA4\xA5',
    b'\x00\x00\x00\x00\x00\x00',
]


def sak_type(sak):
    """Best-effort tag-type name from the SAK byte (WS1850S has no ATQA)."""
    if sak in (0x08, 0x18, 0x09):
        return "MIFARE Classic"
    if sak == 0x00:
        return "MIFARE Ultralight / NTAG2xx"
    if sak & 0x20:
        return "MIFARE Plus / DESFire / NTAG"
    return "Unknown (SAK=0x%02X)" % sak


# ─────────────────────────────────────────────
# LED ANIMATIONS  (linear whole-strip effects — work on any LED count)
# ─────────────────────────────────────────────
class LEDAnimator:
    def __init__(self, pin, n):
        self.np = NeoPixel(machine.Pin(pin), n)
        self.n = n

    def clear(self):
        for i in range(self.n):
            self.np[i] = (0, 0, 0)
        self.np.write()

    def fill(self, color):
        for i in range(self.n):
            self.np[i] = color
        self.np.write()

    def idle_pulse(self, frame):
        """Slow blue breathing while waiting for input."""
        brightness = abs((frame % 60) - 30)
        for i in range(self.n):
            self.np[i] = (0, 0, brightness)
        self.np.write()

    def waiting_for_tag(self, frame):
        """Amber spinner — waiting for tag + button press."""
        self.clear()
        pos = frame % self.n
        for i in range(3):
            idx = (pos + i) % self.n
            fade = max(0, 30 - i * 10)
            self.np[idx] = (fade, fade // 2, 0)
        self.np.write()

    def writing_progress(self, progress):
        """Fill LEDs proportional to write progress (0.0 → 1.0)."""
        lit = int(progress * self.n)
        for i in range(self.n):
            if i < lit:
                self.np[i] = (0, 0, 40)  # blue = written
            elif i == lit:
                self.np[i] = (40, 40, 40)  # white = current
            else:
                self.np[i] = (5, 5, 5)  # dim = pending
        self.np.write()

    def success(self):
        """Green flash + sweep for success."""
        for _ in range(3):
            self.fill((0, 40, 0))
            time.sleep_ms(100)
            self.clear()
            time.sleep_ms(100)
        # Green sweep out
        for i in range(self.n):
            self.np[i] = (0, 30, 0)
            self.np.write()
            time.sleep_ms(30)
        time.sleep(0.5)
        # Fade out
        for b in range(30, -1, -2):
            self.fill((0, b, 0))
            time.sleep_ms(30)
        self.clear()

    def failure(self):
        """Red pulse for failure."""
        for _ in range(5):
            self.fill((40, 0, 0))
            time.sleep_ms(80)
            self.clear()
            time.sleep_ms(80)
        self.clear()

    def rainbow_celebrate(self):
        """Quick rainbow celebration."""
        for offset in range(self.n * 2):
            for i in range(self.n):
                hue = ((i + offset) * 255 // self.n) % 255
                r, g, b = self._hsv(hue, 255, 25)
                self.np[i] = (r, g, b)
            self.np.write()
            time.sleep_ms(30)
        self.clear()

    def _hsv(self, h, s, v):
        if s == 0:
            return v, v, v
        region = h // 43
        remainder = (h - region * 43) * 6
        p = (v * (255 - s)) >> 8
        q = (v * (255 - ((s * remainder) >> 8))) >> 8
        t = (v * (255 - ((s * (255 - remainder)) >> 8))) >> 8
        if region == 0: return v, t, p
        if region == 1: return q, v, p
        if region == 2: return p, v, t
        if region == 3: return p, q, v
        if region == 4: return t, p, v
        return v, p, q

# ─────────────────────────────────────────────
# BUZZER
# ─────────────────────────────────────────────
class Beeper:
    def __init__(self, pin):
        self.pin = pin

    def tone(self, freq, duration_ms):
        buz = machine.PWM(machine.Pin(self.pin))
        buz.freq(freq)
        buz.duty_u16(16384)
        time.sleep_ms(duration_ms)
        buz.duty_u16(0)
        buz.deinit()

    def success(self):
        self.tone(523, 100)  # C5
        time.sleep_ms(50)
        self.tone(659, 100)  # E5
        time.sleep_ms(50)
        self.tone(784, 200)  # G5

    def fail(self):
        self.tone(300, 200)
        time.sleep_ms(50)
        self.tone(200, 400)

    def click(self):
        self.tone(1000, 30)

# ─────────────────────────────────────────────
# NFC WRITER — WS1850S adapter
# ─────────────────────────────────────────────
# Exposes the same handful of methods the write logic below expects, but
# every call is serviced by the WS1850S driver instead of a PN532.
class NfcWriter:
    def __init__(self, i2c, addr=NFC_ADDR):
        self.dev = WS1850S(i2c, addr)

    def init(self):
        self.dev.init()
        print("  WS1850S VersionReg: 0x%02X" % self.dev.version())

    def detect_tag(self, timeout=500):
        """Poll for a tag up to `timeout` ms. Leaves the card ACTIVE."""
        # Clear leftover Crypto1 from a prior auth; otherwise the next
        # anticollision/SELECT is encrypted and silently fails (breaks
        # multi-sector writes and re-detecting the next card).
        try:
            self.dev.stop_crypto1()
        except Exception:
            pass
        deadline = time.ticks_add(time.ticks_ms(), timeout)
        while True:
            try:
                result = self.dev.read_uid_full()
            except Exception:
                result = None
            if result is not None:
                uid, sak = result
                return {
                    'uid': bytes(uid),
                    'uid_hex': ':'.join('%02X' % b for b in uid),
                    'uid_len': len(uid),
                    'sak': sak,
                    'tag_type': sak_type(sak),
                    'is_classic': sak in (0x08, 0x18, 0x09),
                    'is_ntag': sak == 0x00,
                }
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                return None
            time.sleep_ms(10)

    def mifare_auth(self, uid, block, key=b'\xFF\xFF\xFF\xFF\xFF\xFF', kt=MIFARE_AUTH_A):
        try:
            return self.dev.auth(kt, block, key, uid) == WS1850S.MI_OK
        except Exception:
            return False

    def mifare_read(self, block):
        status, data = self.dev.read_block(block)
        if status != WS1850S.MI_OK or data is None:
            raise RuntimeError("Classic read err on block %d" % block)
        return bytes(data[:16])

    def mifare_write(self, block, data):
        """Write 16 bytes to a MIFARE Classic block (must auth first)."""
        if len(data) != 16:
            raise ValueError("Must write exactly 16 bytes")
        if self.dev.write_block(block, bytes(data)) != WS1850S.MI_OK:
            raise RuntimeError("Write err on block %d" % block)
        return True

    def ntag_write_page(self, page, data):
        """Write 4 bytes to an NTAG/Ultralight page."""
        if len(data) != 4:
            raise ValueError("Must write exactly 4 bytes")
        if self.dev.ul_write(page, bytes(data)) != WS1850S.MI_OK:
            raise RuntimeError("Write err on page %d" % page)
        return True

    def ntag_read_page(self, page):
        """Read 4 bytes from a single NTAG/Ultralight page."""
        status, data = self.dev.ul_read(page)
        if status != WS1850S.MI_OK or data is None:
            raise RuntimeError("NTAG read err on page %d" % page)
        return bytes(data[:4])


# ─────────────────────────────────────────────
# BUILD NDEF TEXT RECORD
# ─────────────────────────────────────────────
def build_ndef_text(text):
    """Build a complete NDEF message with a text record for NTAG."""
    lang = b'en'
    payload = bytes([len(lang)]) + lang + text.encode('utf-8')
    # NDEF record: MB=1, ME=1, CF=0, SR=1, IL=0, TNF=01 (well-known)
    flags = 0xD1  # MB|ME|SR, TNF=0x01
    rec_type = b'T'
    record = bytes([flags, len(rec_type), len(payload)]) + rec_type + payload
    # TLV wrapper: type=0x03 (NDEF), length, data, terminator=0xFE
    tlv = bytes([0x03, len(record)]) + record + bytes([0xFE])
    return tlv


def build_ndef_text_classic(text):
    """Build NDEF text padded into 16-byte MIFARE Classic blocks."""
    lang = b'en'
    payload = bytes([len(lang)]) + lang + text.encode('utf-8')
    flags = 0xD1
    rec_type = b'T'
    record = bytes([flags, len(rec_type), len(payload)]) + rec_type + payload
    tlv = bytes([0x03, len(record)]) + record + bytes([0xFE])
    # Pad to multiple of 16 bytes
    while len(tlv) % 16 != 0:
        tlv += b'\x00'
    return tlv


# ─────────────────────────────────────────────
# WRITE FUNCTIONS
# ─────────────────────────────────────────────
def write_ntag(nfc, tag, text, led):
    """Write NDEF text record to NTAG/Ultralight starting at page 4."""
    ndef = build_ndef_text(text)
    pages_needed = (len(ndef) + 3) // 4  # 4 bytes per page
    max_pages = 36  # NTAG213 user area: pages 4-39

    if pages_needed > max_pages:
        print(f"  Text too long! Need {pages_needed} pages, max {max_pages}")
        return False

    print(f"  Writing {len(ndef)} bytes across {pages_needed} pages (4-{4+pages_needed-1})")

    # Pad to full pages
    while len(ndef) % 4 != 0:
        ndef += b'\x00'

    for i in range(pages_needed):
        page = 4 + i
        chunk = ndef[i*4: i*4 + 4]
        progress = (i + 1) / pages_needed
        led.writing_progress(progress)

        try:
            nfc.ntag_write_page(page, chunk)
            hex_str = ' '.join(f'{b:02X}' for b in chunk)
            print(f"  Page {page:>3}: {hex_str}  [{int(progress*100):>3}%]")
        except RuntimeError as e:
            print(f"  Page {page}: WRITE FAILED — {e}")
            return False

        time.sleep_ms(30)

    return True


def write_mifare_classic(nfc, tag, text, led):
    """Write NDEF text to MIFARE Classic blocks (sector 1+, skip trailers)."""
    ndef = build_ndef_text_classic(text)
    blocks_needed = len(ndef) // 16

    # Usable data blocks per sector: blocks 0,1,2 (block 3 = trailer)
    # Skip sector 0 entirely (manufacturer data)
    # Start writing at sector 1, block 4
    writable_blocks = []
    for sector in range(1, 16):  # sectors 1-15
        for blk_in_sec in range(3):  # skip trailer (block 3)
            writable_blocks.append(sector * 4 + blk_in_sec)

    if blocks_needed > len(writable_blocks):
        print(f"  Text too long! Need {blocks_needed} blocks, max {len(writable_blocks)}")
        return False

    print(f"  Writing {len(ndef)} bytes across {blocks_needed} blocks")

    written = 0
    for i in range(blocks_needed):
        block = writable_blocks[i]
        sector = block // 4
        first_block = sector * 4
        chunk = ndef[i*16: i*16 + 16]
        progress = (i + 1) / blocks_needed
        led.writing_progress(progress)

        # Auth this sector — re-detect tag first (WS1850S needs the card
        # selected before each auth; read_uid_full re-selects it).
        resel = nfc.detect_tag(timeout=300)
        if resel is None:
            print(f"  Block {block}: Tag lost!")
            return False

        authed = False
        for key in COMMON_KEYS:
            for kt in [MIFARE_AUTH_A, MIFARE_AUTH_B]:
                if nfc.mifare_auth(tag['uid'], first_block, key, kt):
                    authed = True
                    break
            if authed:
                break

        if not authed:
            print(f"  Block {block}: Auth failed — cannot write this sector")
            return False

        try:
            nfc.mifare_write(block, chunk)
            hex_str = ' '.join(f'{b:02X}' for b in chunk[:8]) + '...'
            print(f"  Block {block:>3}: {hex_str}  [{int(progress*100):>3}%]")
            written += 1
        except RuntimeError as e:
            print(f"  Block {block}: WRITE FAILED — {e}")
            return False

        time.sleep_ms(30)

    return written == blocks_needed


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("\n" + "*" * 55)
    print("  PlaygroundV5 (Bag3) — NFC Tag Writer (WS1850S)")
    print("  Type your text, place tag, press button to write")
    print("*" * 55)

    # Init hardware
    i2c = machine.SoftI2C(sda=machine.Pin(I2C_SDA), scl=machine.Pin(I2C_SCL), freq=400_000)
    btn = machine.Pin(SWITCH, machine.Pin.IN, machine.Pin.PULL_UP)
    led = LEDAnimator(NEOPIXEL, NUM_LEDS)
    beep = Beeper(BUZZER)
    led.clear()

    devices = i2c.scan()
    print(f"  I2C: {['0x{:02X}'.format(d) for d in devices]}")

    nfc = NfcWriter(i2c, NFC_ADDR)
    nfc.init()
    print("  WS1850S ready\n")

    while True:
        # ── Step 1: Get text from user ──
        led.fill((0, 0, 5))  # dim blue = input mode
        print("  ─────────────────────────────────────")

        try:
            text = input("  Enter text to write (or 'quit'): ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if text.lower() in ('quit', 'exit', 'q'):
            break

        if not text:
            print("  Empty text, try again.\n")
            continue

        byte_len = len(text.encode('utf-8'))
        print(f"  Text: \"{text}\" ({byte_len} bytes)")
        if byte_len > 130:
            print("  [WARN] Text may be too long for small tags (NTAG213=137 bytes max)")

        # ── Step 2: Wait for tag + button press ──
        print("\n  Place tag on reader and press the BUTTON to write...")

        frame = 0
        tag = None
        tag_on_reader = False

        while True:
            # Animate while waiting
            led.waiting_for_tag(frame)
            frame += 1

            # Check for tag
            detected = nfc.detect_tag(timeout=100)
            if detected and not tag_on_reader:
                tag = detected
                tag_on_reader = True
                print(f"\n  Tag detected: {tag['uid_hex']} ({tag['tag_type']})")
                print("  >>> Press BUTTON to write! <<<")
                beep.click()
                # Show green ring = tag ready
                led.fill((0, 20, 0))
            elif not detected and tag_on_reader:
                tag_on_reader = False
                tag = None
                print("  Tag removed — place it back...")

            # Check button
            if btn.value() == 0 and tag_on_reader and tag:
                time.sleep_ms(50)  # debounce
                if btn.value() == 0:
                    beep.click()
                    break

            time.sleep_ms(50)

        # ── Step 3: Write to tag ──
        print(f"\n  Writing to {tag['tag_type']}...")
        led.fill((0, 0, 20))  # blue = writing
        time.sleep_ms(200)

        success = False
        try:
            if tag['is_ntag']:
                success = write_ntag(nfc, tag, text, led)
            elif tag['is_classic']:
                success = write_mifare_classic(nfc, tag, text, led)
            else:
                print(f"  Unsupported tag type: {tag['tag_type']}")
        except Exception as e:
            print(f"  Write error: {e}")

        # ── Step 4: Result feedback ──
        if success:
            print(f"\n  ✓ Successfully wrote \"{text}\" to tag {tag['uid_hex']}")
            led.success()
            beep.success()
            led.rainbow_celebrate()

            # Verify by reading back
            print("  Verifying...")
            time.sleep_ms(300)
            verify = nfc.detect_tag(timeout=500)
            if verify:
                try:
                    if tag['is_ntag']:
                        page4 = nfc.ntag_read_page(4)
                        if page4[0] == 0x03:
                            print("  ✓ NDEF header verified on tag")
                        else:
                            print("  ? Could not verify NDEF header")
                except Exception:
                    print("  ? Verify read failed (tag may have moved)")
        else:
            print(f"\n  ✗ Write failed!")
            led.failure()
            beep.fail()

        print()


    # Cleanup
    led.clear()
    print("\n  Done. Goodbye!")


if __name__ == "__main__":
    main()
