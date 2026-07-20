"""
PlaygroundV5 (Bag3) - WS1850S NFC Tag Reader
=============================================
Board: Seeed XIAO ESP32-C6 (Bag3 wand)
NFC:   M5Stack RFID2 / WS1850S on I2C (SDA=GPIO22, SCL=GPIO23), addr 0x28

Requires ws1850s.py on the device (copied alongside this file).

Bag3 port of the original PN532 reader. The WS1850S replaces the PN532,
so the embedded PN532 wire protocol is gone; every operation now goes
through the WS1850S driver. MIFARE Classic auth+read, NTAG/Ultralight
page reads, and NDEF decoding are unchanged.

Note: the original reader began with a CD4066 reader-select preamble that
drove GPIO0/GPIO1 to switch between two PN532s. Bag3 has a single WS1850S
on the Grove I2C bus (and GPIO0 is the button), so that mux preamble has
been removed.
"""

import machine
import time
from ws1850s import WS1850S
from opcodes import decode as decode_opcode, CARD_PAGE

# ─────────────────────────────────────────────
# PIN CONFIG
# ─────────────────────────────────────────────
I2C_SDA  = 22
I2C_SCL  = 23
NFC_ADDR = 0x28      # WS1850S default (PN532 was 0x24)

# MIFARE key-type codes (match WS1850S PICC_AUTHENT1A/1B)
MIFARE_CMD_AUTH_A = WS1850S.PICC_AUTHENT1A
MIFARE_CMD_AUTH_B = WS1850S.PICC_AUTHENT1B


def sak_type(sak):
    """Best-effort tag-type name from the SAK byte (WS1850S has no ATQA)."""
    if sak in (0x08, 0x09):
        return "MIFARE Classic 1K"
    if sak == 0x18:
        return "MIFARE Classic 4K"
    if sak == 0x00:
        return "MIFARE Ultralight / NTAG2xx"
    if sak & 0x20:
        return "MIFARE Plus / DESFire / NTAG"
    return "Unknown (SAK=0x%02X)" % sak


# ─────────────────────────────────────────────
# NFC READER — WS1850S adapter
# ─────────────────────────────────────────────
# Same method names the read logic below expects, serviced by the WS1850S
# driver instead of a PN532.
class NfcReaderDev:
    def __init__(self, i2c, addr=NFC_ADDR):
        self.dev = WS1850S(i2c, addr)

    def init(self):
        self.dev.init()
        return self.dev.version()

    def read_passive_target(self, baud=0x00, timeout=1000):
        """Detect an ISO14443A tag. Returns dict or None. Leaves card ACTIVE."""
        # Clear leftover Crypto1 from a prior auth; otherwise the next
        # anticollision/SELECT is encrypted and silently fails (breaks
        # multi-sector reads and re-detecting the next card).
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
                }
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                return None
            time.sleep_ms(10)

    def mifare_auth_block(self, uid, block, key=b'\xFF\xFF\xFF\xFF\xFF\xFF',
                          key_type=MIFARE_CMD_AUTH_A):
        """Authenticate a MIFARE Classic block. Returns True on success."""
        try:
            return self.dev.auth(key_type, block, key, uid) == WS1850S.MI_OK
        except Exception:
            return False

    def mifare_read_block(self, block):
        """Read 16 bytes from an authenticated MIFARE Classic block."""
        status, data = self.dev.read_block(block)
        if status != WS1850S.MI_OK or data is None:
            raise RuntimeError("read status err")
        return bytes(data[:16])

    def ntag_read_page(self, page):
        """Read 4 bytes from an NTAG/Ultralight page."""
        status, data = self.dev.ul_read(page)
        if status != WS1850S.MI_OK or data is None:
            raise RuntimeError("read status err")
        return bytes(data[:4])


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def section(title):
    print("\n" + "=" * 55)
    print(f"  {title}")
    print("=" * 55)

# ─────────────────────────────────────────────
# MIFARE CLASSIC READ
# ─────────────────────────────────────────────
def read_mifare_classic(nfc, tag):
    print("\n  Reading MIFARE Classic (trying keys A & B):")
    print(f"  {'Block':>5} | {'Hex Data':48} | ASCII")
    print(f"  {'─'*5}─┼─{'─'*48}─┼─{'─'*16}")

    common_keys = [
        b'\xFF\xFF\xFF\xFF\xFF\xFF',  # factory default
        b'\xA0\xA1\xA2\xA3\xA4\xA5',  # MAD key A
        b'\xB0\xB1\xB2\xB3\xB4\xB5',  # common key B
        b'\xD3\xF7\xD3\xF7\xD3\xF7',  # NFC Forum public key
        b'\x00\x00\x00\x00\x00\x00',  # blank key
    ]

    sectors_to_read = 4
    total_read = 0
    total_fail = 0

    for sector in range(sectors_to_read):
        first_block = sector * 4
        authed = False

        # Try each key until one works
        for key in common_keys:
            for key_type in [MIFARE_CMD_AUTH_A, MIFARE_CMD_AUTH_B]:
                # Must re-select tag before each auth attempt
                resel = nfc.read_passive_target(timeout=300)
                if resel is None:
                    continue

                if nfc.mifare_auth_block(tag['uid'], first_block, key, key_type):
                    kt = 'A' if key_type == MIFARE_CMD_AUTH_A else 'B'
                    key_hex = ''.join(f'{b:02X}' for b in key)

                    # Read all 4 blocks in this sector
                    for block in range(first_block, first_block + 4):
                        try:
                            data = nfc.mifare_read_block(block)
                            hex_str = ' '.join(f'{b:02X}' for b in data)
                            asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)

                            label = ""
                            if block == 0:
                                label = " <- Manufacturer"
                            elif block == CARD_PAGE:
                                label = " <- OPCODE"
                            elif block % 4 == 3:
                                label = f" <- Trailer (Key{kt}:{key_hex})"

                            print(f"  {block:>5} | {hex_str} | {asc}{label}")
                            if block == CARD_PAGE:
                                report_opcode(data)
                            total_read += 1
                        except RuntimeError as e:
                            print(f"  {block:>5} | (read error: {e})")
                            total_fail += 1

                    authed = True
                    break
            if authed:
                break

        if not authed:
            print(f"  Sector {sector} (blocks {first_block}-{first_block+3}): "
                  f"Auth failed with all keys")
            total_fail += 4

    print(f"\n  Summary: {total_read} blocks read, {total_fail} failed")

# ─────────────────────────────────────────────
# NTAG / ULTRALIGHT READ
# ─────────────────────────────────────────────
def read_ntag(nfc, tag):
    print("\n  Reading NTAG / Ultralight pages:")
    print(f"  {'Page':>5} | {'Hex Data':14} | ASCII")
    print(f"  {'─'*5}─┼─{'─'*14}─┼─{'─'*4}")

    max_pages = 45  # NTAG213=45, try up to this
    ndef_data = bytearray()
    pages_read = 0
    page5 = None

    for page in range(max_pages):
        try:
            data = nfc.ntag_read_page(page)
            hex_str = ' '.join(f'{b:02X}' for b in data)
            asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)

            labels = {0: " <- UID", 1: " <- UID", 2: " <- Lock", 3: " <- CC",
                      4: " <- NDEF start", CARD_PAGE: " <- OPCODE"}
            label = labels.get(page, "")
            print(f"  {page:>5} | {hex_str} | {asc}{label}")
            pages_read += 1

            if page == CARD_PAGE:
                page5 = data
            if page >= 4:
                ndef_data.extend(data)

        except Exception:
            print(f"  {page:>5} | (end of readable area)")
            break

    print(f"\n  Pages read: {pages_read}")

    if page5 is not None:
        report_opcode(page5)
    if ndef_data:
        decode_ndef(ndef_data)


def report_opcode(data4):
    """Decode and print the page-5 opcode (the wand's real card format)."""
    name = decode_opcode(bytes(data4[:4]))
    if name is not None:
        print("\n  >> OPCODE CARD: \"%s\"" % name)
    else:
        print("\n  >> Page %d is not a valid opcode "
              "(blank / non-opcode / bad checksum)" % CARD_PAGE)


def decode_ndef(data):
    print("\n  NDEF Decode:")
    try:
        i = 0
        while i < len(data):
            t = data[i]
            if t == 0x00:
                i += 1; continue
            elif t == 0xFE:
                break
            elif t == 0x03:
                length = data[i + 1]
                off = i + 2
                if length == 0xFF:
                    length = (data[i + 2] << 8) | data[i + 3]
                    off = i + 4
                ndef = data[off: off + length]

                if len(ndef) > 3:
                    flags = ndef[0]
                    type_len = ndef[1]
                    sr = flags & 0x10  # short record
                    pl = ndef[2] if sr else (ndef[2] << 24 | ndef[3] << 16 | ndef[4] << 8 | ndef[5])
                    ho = 3 if sr else 6
                    rec_type = bytes(ndef[ho:ho + type_len])
                    payload = bytes(ndef[ho + type_len:ho + type_len + pl])
                    ts = rec_type.decode('ascii', 'replace')
                    print(f"    Type: '{ts}' ({pl} bytes)")

                    if ts == 'T':
                        ll = payload[0] & 0x3F
                        lang = payload[1:1+ll].decode('ascii', 'replace')
                        text = payload[1+ll:].decode('utf-8', 'replace')
                        print(f"    Lang: {lang}")
                        print(f"    Text: \"{text}\"")
                    elif ts == 'U':
                        prefixes = ["", "http://www.", "https://www.", "http://", "https://",
                                    "tel:", "mailto:", "ftp://anonymous:anonymous@", "ftp://ftp."]
                        pre = prefixes[payload[0]] if payload[0] < len(prefixes) else ""
                        uri = pre + payload[1:].decode('utf-8', 'replace')
                        print(f"    URI: {uri}")
                    else:
                        print(f"    Payload: {payload[:50]}")
                break
            else:
                i += 2 + data[i + 1]; continue
            i += 1
    except Exception as e:
        print(f"    Decode error: {e}")


# ─────────────────────────────────────────────
# UID-ONLY MODE (guaranteed to work)
# ─────────────────────────────────────────────
def read_uid_only(nfc):
    """Simple mode — just reads and logs UIDs without reading blocks."""
    section("UID-Only Mode — Tap tags to log UIDs")
    print("  Press Ctrl+C to stop\n")

    seen = {}
    last_uid = None

    while True:
        try:
            tag = nfc.read_passive_target(timeout=500)
            if tag is None:
                if last_uid:
                    print("  --- removed ---\n")
                    last_uid = None
                time.sleep_ms(200)
                continue

            uid = tag['uid_hex']
            if uid != last_uid:
                last_uid = uid
                count = seen.get(uid, 0) + 1
                seen[uid] = count

                print(f"  Tag: {uid}  |  {tag['tag_type']}  |  "
                      f"seen {count}x  |  total unique: {len(seen)}")

            time.sleep_ms(300)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"  [ERR] {e}")
            time.sleep_ms(500)

    print(f"\n  Unique tags: {len(seen)}")
    for uid, cnt in seen.items():
        print(f"    {uid} — {cnt} reads")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    print("\n" + "*" * 55)
    print("  PlaygroundV5 (Bag3) — WS1850S NFC Tag Reader")
    print("  Board: XIAO ESP32-C6")
    print("*" * 55)

    i2c = machine.SoftI2C(
        sda=machine.Pin(I2C_SDA),
        scl=machine.Pin(I2C_SCL),
        freq=400_000
    )

    devices = i2c.scan()
    print(f"\n  I2C devices: {['0x{:02X}'.format(d) for d in devices]}")

    if NFC_ADDR not in devices:
        print(f"  [FAIL] WS1850S not found at 0x{NFC_ADDR:02X}")
        return

    nfc = NfcReaderDev(i2c, NFC_ADDR)

    section("WS1850S Init")
    try:
        ver = nfc.init()
        print(f"  VersionReg: 0x{ver:02X}")
        if ver in (0x00, 0xFF):
            print("  [WARN] VersionReg 0x00/0xFF — check wiring (may still work)")
    except Exception as e:
        print(f"  [FAIL] Init error: {e}")
        return

    # Main tag reading loop
    section("Scanning — Hold a tag near the reader")
    print("  Press Ctrl+C to stop\n")

    last_uid = None
    tag_count = 0

    while True:
        try:
            tag = nfc.read_passive_target(timeout=500)

            if tag is None:
                if last_uid is not None:
                    print("  --- Tag removed ---\n")
                    last_uid = None
                time.sleep_ms(200)
                continue

            if tag['uid_hex'] != last_uid:
                tag_count += 1
                last_uid = tag['uid_hex']

                print(f"  ┌─ Tag #{tag_count} ──────────────────────")
                print(f"  │ UID:  {tag['uid_hex']} ({tag['uid_len']} bytes)")
                print(f"  │ Type: {tag['tag_type']}")
                print(f"  │ SAK:  0x{tag['sak']:02X}")
                print(f"  └────────────────────────────────────")

                try:
                    if 'Classic' in tag['tag_type']:
                        read_mifare_classic(nfc, tag)
                    elif 'Ultralight' in tag['tag_type'] or 'NTAG' in tag['tag_type']:
                        read_ntag(nfc, tag)
                    else:
                        print("  (Tag type not supported for data read)")
                        print(f"  UID logged: {tag['uid_hex']}")
                except Exception as e:
                    print(f"  [WARN] Data read failed: {e}")
                    print(f"  UID was still captured: {tag['uid_hex']}")

                print()


            time.sleep_ms(300)

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"  [ERR] {e}")
            time.sleep_ms(500)

    section("Done")
    print(f"  Total tags read: {tag_count}")


if __name__ == "__main__":
    main()
    # To use UID-only mode (skip block reads), comment out main() and uncomment:
    # read_uid_only(nfc)
