"""
card_writer.py — NFC opcode writer for Broadcast Box (PN532 via I2C).

Lifted from Bag3/Code/utilities/writetoNFCcards.py (NfcWriter + write helpers).
No LEDAnimator/Beeper/main() — the Box UI handles feedback.
"""

from pn532 import PN532, MIFARE_AUTH_A, MIFARE_AUTH_B
from opcodes import encode, decode, CARD_PAGE

COMMON_KEYS = [
    b'\xFF\xFF\xFF\xFF\xFF\xFF',
    b'\xD3\xF7\xD3\xF7\xD3\xF7',
    b'\xA0\xA1\xA2\xA3\xA4\xA5',
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


def read_page5(nfc, tag):
    """Return the 4 bytes at page/block 5, or None."""
    try:
        if tag['is_ntag']:
            return bytes(nfc.ntag_read_page(CARD_PAGE)[:4])
        if nfc.detect_tag(timeout=300) is None:
            return None
        for key in COMMON_KEYS:
            for kt in (MIFARE_AUTH_A, MIFARE_AUTH_B):
                if nfc.mifare_auth(tag['uid'], CARD_PAGE, key, kt):
                    return bytes(nfc.mifare_read(CARD_PAGE)[:4])
        return None
    except Exception:
        return None


def write_ntag(nfc, tag, payload):
    try:
        nfc.ntag_write_page(CARD_PAGE, payload)
        return True
    except RuntimeError:
        return False


def write_mifare_classic(nfc, tag, payload):
    resel = nfc.detect_tag(timeout=300)
    if resel is None:
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
        return False
    block16 = bytearray(16)
    block16[0:4] = payload
    try:
        nfc.mifare_write(CARD_PAGE, block16)
        return True
    except RuntimeError:
        return False


def write_opcode(nfc, tag, name):
    """Write opcode for `name` to the card. Returns True on success."""
    payload = encode(name)
    if payload is None:
        return False
    if tag['is_ntag']:
        return write_ntag(nfc, tag, payload)
    if tag['is_classic']:
        return write_mifare_classic(nfc, tag, payload)
    return False


def existing_opcode_name(nfc, tag):
    data = read_page5(nfc, tag)
    if not data:
        return None
    return decode(data)
