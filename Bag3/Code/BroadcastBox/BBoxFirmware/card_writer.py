"""
card_writer.py — plain NDEF text writer for Broadcast Box (PN532 via I2C).

Writes plain NDEF text records, NOT the Bag3 4-byte opcode scheme from
opcodes.py -- that scheme is untested on real hardware. This ports the
NDEF build/parse logic straight from Bag2/Utilities/writetoNFCcards.py
(write side) and Bag2/Code/lib/nfc_reader.py's _decode_ndef_text (read
side), which are proven working with real wands. MockWand/lib/nfc_reader.py
was switched to match (see that file's docstring) so the two sides agree.

No LEDAnimator/Beeper/main() — bbox_ui.py handles all Box-side feedback.
"""

from pn532 import PN532, MIFARE_AUTH_A, MIFARE_AUTH_B

COMMON_KEYS = [
    b'\xFF\xFF\xFF\xFF\xFF\xFF',
    b'\xD3\xF7\xD3\xF7\xD3\xF7',
    b'\xA0\xA1\xA2\xA3\xA4\xA5',
    b'\xB0\xB1\xB2\xB3\xB4\xB5',
    b'\x00\x00\x00\x00\x00\x00',
]


def sak_type(sak):
    if sak in (0x08, 0x18, 0x09):
        return "MIFARE Classic"
    if sak == 0x00:
        return "NTAG/Ultralight"
    return "Unknown (SAK=0x%02X)" % sak


class NfcWriter:
    def __init__(self, i2c, addr=0x24):
        self.dev = PN532(i2c, addr)

    def init(self):
        return self.dev.begin()

    def detect_tag(self, timeout=500):
        tag = self.dev.read_passive_target(timeout=timeout)
        if tag is None:
            return None
        sak = tag['sak']
        tag['tag_type'] = sak_type(sak)
        tag['is_classic'] = sak in (0x08, 0x18, 0x09)
        tag['is_ntag'] = sak == 0x00
        return tag

    def mifare_auth(self, uid, block, key=b'\xFF\xFF\xFF\xFF\xFF\xFF', kt=MIFARE_AUTH_A):
        return self.dev.mifare_auth_block(uid, block, key, kt)

    def mifare_read(self, block):
        return self.dev.mifare_read_block(block)

    def mifare_write(self, block, data):
        return self.dev.mifare_write_block(block, data)

    def ntag_write_page(self, page, data):
        return self.dev.ntag_write_page(page, data)

    def ntag_read_page(self, page):
        return self.dev.ntag_read_page(page)


# ─────────────────────────────────────────────
# BUILD NDEF TEXT RECORD (ported from Bag2/Utilities/writetoNFCcards.py)
# ─────────────────────────────────────────────
def build_ndef_text(text):
    """Build a complete NDEF message with a text record for NTAG."""
    lang = b'en'
    payload = bytes([len(lang)]) + lang + text.encode('utf-8')
    flags = 0xD1  # MB|ME|SR, TNF=0x01 (well-known)
    rec_type = b'T'
    record = bytes([flags, len(rec_type), len(payload)]) + rec_type + payload
    tlv = bytes([0x03, len(record)]) + record + bytes([0xFE])
    return tlv


def build_ndef_text_classic(text):
    """Build NDEF text padded into 16-byte MIFARE Classic blocks."""
    tlv = build_ndef_text(text)
    while len(tlv) % 16 != 0:
        tlv += b'\x00'
    return tlv


# ─────────────────────────────────────────────
# DECODE NDEF TEXT (ported from Bag2/Code/lib/nfc_reader.py's
# _decode_ndef_text -- keep the two in sync if either changes)
# ─────────────────────────────────────────────
def _decode_ndef_text(data):
    if not data or len(data) < 4:
        return None
    i = 0
    while i < len(data):
        t = data[i]
        if t == 0x00:
            i += 1
            continue
        if t == 0xFE:
            break
        if t == 0x03:
            if i + 1 >= len(data):
                break
            length = data[i + 1]
            off = i + 2
            if length == 0xFF:
                if i + 3 >= len(data):
                    break
                length = (data[i + 2] << 8) | data[i + 3]
                off = i + 4
            ndef = data[off:off + length]
            if len(ndef) > 3:
                flags = ndef[0]
                type_len = ndef[1]
                sr = flags & 0x10
                if sr:
                    pl = ndef[2]
                    ho = 3
                else:
                    if len(ndef) < 6:
                        break
                    pl = (ndef[2] << 24) | (ndef[3] << 16) | (ndef[4] << 8) | ndef[5]
                    ho = 6
                rec_type = ndef[ho:ho + type_len]
                payload = ndef[ho + type_len:ho + type_len + pl]
                if bytes(rec_type) == b'T' and len(payload) > 1:
                    lang_len = payload[0] & 0x3F
                    return bytes(payload[1 + lang_len:]).decode('utf-8', 'replace').strip().lower()
            break
        else:
            if i + 1 < len(data):
                i += 2 + data[i + 1]
            else:
                break
    return None


# ─────────────────────────────────────────────
# WRITE FUNCTIONS
# ─────────────────────────────────────────────
def _write_ntag_text(nfc, text):
    """Write NDEF text record to NTAG/Ultralight starting at page 4."""
    ndef = build_ndef_text(text)
    pages_needed = (len(ndef) + 3) // 4
    max_pages = 36  # NTAG213 user area: pages 4-39
    if pages_needed > max_pages:
        return False
    while len(ndef) % 4 != 0:
        ndef += b'\x00'
    for i in range(pages_needed):
        page = 4 + i
        chunk = ndef[i * 4: i * 4 + 4]
        try:
            nfc.ntag_write_page(page, chunk)
        except RuntimeError:
            return False
    return True


def _write_classic_text(nfc, tag, text):
    """Write NDEF text to MIFARE Classic blocks (sector 1+, skip trailers)."""
    ndef = build_ndef_text_classic(text)
    blocks_needed = len(ndef) // 16

    writable_blocks = []
    for sector in range(1, 16):  # sectors 1-15
        for blk_in_sec in range(3):  # skip trailer (block 3)
            writable_blocks.append(sector * 4 + blk_in_sec)
    if blocks_needed > len(writable_blocks):
        return False

    written = 0
    for i in range(blocks_needed):
        block = writable_blocks[i]
        sector = block // 4
        first_block = sector * 4
        chunk = ndef[i * 16: i * 16 + 16]

        resel = nfc.detect_tag(timeout=300)
        if resel is None:
            return False
        authed = False
        for key in COMMON_KEYS:
            for kt in (MIFARE_AUTH_A, MIFARE_AUTH_B):
                if nfc.mifare_auth(tag['uid'], first_block, key, kt):
                    authed = True
                    break
            if authed:
                break
        if not authed:
            return False
        try:
            nfc.mifare_write(block, chunk)
            written += 1
        except RuntimeError:
            return False
    return written == blocks_needed


def write_text(nfc, tag, text):
    """Write plain NDEF text `text` to the card. Returns True on success.

    Wrapped in a broad except (not just the RuntimeError the low-level
    write calls raise) because a flaky I2C read/re-select during the
    write (detect_tag/mifare_auth) can also throw OSError -- letting that
    escape here took down the whole server loop on a transient timeout.
    """
    try:
        if tag['is_ntag']:
            return _write_ntag_text(nfc, text)
        if tag['is_classic']:
            return _write_classic_text(nfc, tag, text)
        return False
    except Exception as e:
        print("# write_text err: %s" % str(e))
        return False


def existing_text(nfc, tag):
    """Read back NDEF text already on the card, or None."""
    try:
        if tag['is_ntag']:
            data = bytearray()
            for page in range(4, 20):
                try:
                    data.extend(nfc.ntag_read_page(page))
                except Exception:
                    break
            return _decode_ndef_text(data)
        if tag['is_classic']:
            data = bytearray()
            for sector in (1, 2):
                fb = sector * 4
                authed = False
                for key in COMMON_KEYS:
                    for kt in (MIFARE_AUTH_A, MIFARE_AUTH_B):
                        resel = nfc.detect_tag(timeout=150)
                        if resel is None:
                            continue
                        if nfc.mifare_auth(resel['uid'], fb, key, kt):
                            for blk in range(fb, fb + 3):
                                try:
                                    data.extend(nfc.mifare_read(blk))
                                except Exception:
                                    data.extend(b'\x00' * 16)
                            authed = True
                            break
                    if authed:
                        break
                if not authed:
                    data.extend(b'\x00' * 48)
            return _decode_ndef_text(data)
        return None
    except Exception:
        return None
