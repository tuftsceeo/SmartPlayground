"""
PlaygroundV5 (Bag3) - NFC Opcode Card Writer with LED Animation
================================================================
Board: Seeed XIAO ESP32-C6 (Bag3 wand)
NFC:   PN532 on I2C (SDA=GPIO22, SCL=GPIO23), addr 0x24
LEDs:  25x SK6812 on GPIO20 (5×5 matrix, row-major)
Button: GPIO0 (active LOW)
Buzzer: GPIO19

Requires pn532.py and opcodes.py on the device.

Writes the compact 4-byte opcode format (see lib/opcodes.py) to page/block
5 instead of a multi-page NDEF text record, so the wand can read a card
with a single page read. You type a command NAME ("melody", "note_c",
"turnred", "stop", ...) and this writes its opcode.

Flow:
  1. Type the command name you want to write at the REPL prompt
     (type "list" to see every valid name)
  2. Press the button when a tag is on the reader
  3. LEDs animate during write
  4. Buzzer confirms success/failure
"""

import machine
import time
from neopixel import NeoPixel
from pn532 import PN532, MIFARE_AUTH_A, MIFARE_AUTH_B
from opcodes import encode, decode, CARD_PAGE, names_by_category, ALL_NAMES

# ─────────────────────────────────────────────
# PIN CONFIG
# ─────────────────────────────────────────────
I2C_SDA   = 22
I2C_SCL   = 23
NEOPIXEL  = 20
SWITCH    = 0
BUZZER    = 19
NFC_ADDR  = 0x24      # PN532 I2C address
NUM_LEDS  = 25        # 5×5 matrix on Bag3

COMMON_KEYS = [
    b'\xFF\xFF\xFF\xFF\xFF\xFF',
    b'\xD3\xF7\xD3\xF7\xD3\xF7',
    b'\xA0\xA1\xA2\xA3\xA4\xA5',
    b'\x00\x00\x00\x00\x00\x00',
]


def sak_type(sak):
    """Best-effort tag-type name from the SAK byte."""
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
# NFC WRITER — PN532 adapter
# ─────────────────────────────────────────────
# Exposes the handful of methods the write logic below expects, backed by
# the real PN532 driver (lib/pn532.py).
class NfcWriter:
    def __init__(self, i2c, addr=NFC_ADDR):
        self.dev = PN532(i2c, addr)

    def init(self):
        fw = self.dev.begin()
        print("  PN532 firmware: %d.%d (IC 0x%02X)" % (fw[1], fw[2], fw[0]))

    def detect_tag(self, timeout=500):
        """Poll for a tag up to `timeout` ms. Leaves the card ACTIVE."""
        tag = self.dev.read_passive_target(timeout=timeout)
        if tag is None:
            return None
        sak = tag['sak']
        tag['tag_type']   = sak_type(sak)
        tag['is_classic'] = sak in (0x08, 0x18, 0x09)
        tag['is_ntag']    = sak == 0x00
        return tag

    def mifare_auth(self, uid, block, key=b'\xFF\xFF\xFF\xFF\xFF\xFF', kt=MIFARE_AUTH_A):
        return self.dev.mifare_auth_block(uid, block, key, kt)

    def mifare_read(self, block):
        return self.dev.mifare_read_block(block)

    def mifare_write(self, block, data):
        """Write 16 bytes to a MIFARE Classic block (must auth first)."""
        return self.dev.mifare_write_block(block, data)

    def ntag_write_page(self, page, data):
        """Write 4 bytes to an NTAG/Ultralight page."""
        return self.dev.ntag_write_page(page, data)

    def ntag_read_page(self, page):
        """Read 4 bytes from a single NTAG/Ultralight page."""
        return self.dev.ntag_read_page(page)


# ─────────────────────────────────────────────
# WRITE FUNCTIONS — 4-byte opcode at page/block 5
# ─────────────────────────────────────────────
def write_ntag(nfc, tag, payload, led):
    """Write the 4-byte opcode to NTAG/Ultralight page 5."""
    led.writing_progress(0.5)
    try:
        nfc.ntag_write_page(CARD_PAGE, payload)
    except RuntimeError as e:
        print(f"  Page {CARD_PAGE}: WRITE FAILED — {e}")
        return False
    led.writing_progress(1.0)
    hex_str = ' '.join(f'{b:02X}' for b in payload)
    print(f"  Page {CARD_PAGE}: {hex_str}")
    return True


def write_mifare_classic(nfc, tag, payload, led):
    """Write the 4-byte opcode to MIFARE Classic block 5 (padded to 16)."""
    led.writing_progress(0.5)

    # Auth the sector holding block 5 — re-detect the tag first so the
    # PN532 has the card selected before the auth.
    resel = nfc.detect_tag(timeout=300)
    if resel is None:
        print("  Tag lost before auth!")
        return False

    authed = False
    for key in COMMON_KEYS:
        for kt in (MIFARE_AUTH_A, MIFARE_AUTH_B):
            if nfc.mifare_auth(tag['uid'], CARD_PAGE, key, kt):
                authed = True
                break
        if authed:
            break

    if not authed:
        print(f"  Block {CARD_PAGE}: Auth failed — cannot write")
        return False

    block16 = bytearray(16)
    block16[0:4] = payload  # bytes 4-15 stay zero
    try:
        nfc.mifare_write(CARD_PAGE, block16)
    except RuntimeError as e:
        print(f"  Block {CARD_PAGE}: WRITE FAILED — {e}")
        return False

    led.writing_progress(1.0)
    hex_str = ' '.join(f'{b:02X}' for b in payload)
    print(f"  Block {CARD_PAGE}: {hex_str} (+ 12 zero bytes)")
    return True


def print_command_list():
    """Print every valid command name, grouped by opcode category."""
    print("  ── Valid command names ──")
    for op, names in names_by_category().items():
        print("  0x%02X: %s" % (op, ', '.join(names)))


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("\n" + "*" * 55)
    print("  PlaygroundV5 (Bag3) — NFC Opcode Card Writer (PN532)")
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
    print("  PN532 ready\n")

    while True:
        # ── Step 1: Get text from user ──
        led.fill((0, 0, 5))  # dim blue = input mode
        print("  ─────────────────────────────────────")

        try:
            name = input("  Enter command name ('list' / 'quit'): ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if name.lower() in ('quit', 'exit', 'q'):
            break

        if not name:
            print("  Empty name, try again.\n")
            continue

        if name.lower() == 'list':
            print_command_list()
            print()
            continue

        payload = encode(name)
        if payload is None:
            print(f"  Unknown command name: \"{name}\" — type 'list' to see valid names.\n")
            continue

        print(f"  Command: \"{name}\"  ->  page {CARD_PAGE} = "
              + ' '.join(f'{b:02X}' for b in payload))

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
                success = write_ntag(nfc, tag, payload, led)
            elif tag['is_classic']:
                success = write_mifare_classic(nfc, tag, payload, led)
            else:
                print(f"  Unsupported tag type: {tag['tag_type']}")
        except Exception as e:
            print(f"  Write error: {e}")

        # ── Step 4: Result feedback ──
        if success:
            print(f"\n  ✓ Successfully wrote \"{name}\" to tag {tag['uid_hex']}")
            led.success()
            beep.success()
            led.rainbow_celebrate()

            # Verify by reading page 5 back and decoding it.
            print("  Verifying...")
            time.sleep_ms(300)
            verify = nfc.detect_tag(timeout=500)
            if verify:
                try:
                    if tag['is_ntag']:
                        readback = nfc.ntag_read_page(CARD_PAGE)
                    else:
                        nfc.detect_tag(timeout=300)
                        authed = False
                        for key in COMMON_KEYS:
                            for kt in (MIFARE_AUTH_A, MIFARE_AUTH_B):
                                if nfc.mifare_auth(tag['uid'], CARD_PAGE, key, kt):
                                    authed = True
                                    break
                            if authed:
                                break
                        readback = nfc.mifare_read(CARD_PAGE)[:4] if authed else None
                    decoded = decode(readback) if readback else None
                    if decoded == name:
                        print(f"  ✓ Verified: card reads back as \"{decoded}\"")
                    else:
                        print(f"  ? Verify mismatch: read back {decoded!r}")
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
