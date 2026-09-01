"""
card_writer.py — plain NDEF text writer for Broadcast Box (WS1850S via I2C).

Writes plain NDEF text records, NOT the Bag3 4-byte opcode scheme from
opcodes.py -- that scheme is untested on real hardware. This ports the
NDEF build/parse logic straight from Bag2/Utilities/writetoNFCcards.py
(write side) and Bag2/Code/lib/nfc_reader.py's _decode_ndef_text (read
side), which are proven working with real wands. MockWand/lib/nfc_reader.py
was switched to match (see that file's docstring) so the two sides agree.

Reader chip: WS1850S (register-compatible with MFRC522), swapped in for
the original PN532 -- the PN532's ~150 mA read/write burst coincided with
the SoftAP's own power spikes; the WS1850S bursts at ~30 mA. See
ws1850s.py for the wire-level driver. NfcWriter below keeps the exact
method names/signatures the PN532-backed version had, so nothing else in
this file (or bbox_server.py) needed to change.

No LEDAnimator/Beeper/main() — bbox_ui.py handles all Box-side feedback.
"""

import time

from ws1850s import WS1850S

MIFARE_AUTH_A = WS1850S.PICC_AUTHENT1A
MIFARE_AUTH_B = WS1850S.PICC_AUTHENT1B

# NTAG/Classic need programming time after each page/block write. Bag2's
# writetoNFCcards.py sleeps 30ms after every write; dropping it let later
# pages silently fail to commit, leaving a half-written NDEF on the card.
WRITE_SETTLE_MS = 30

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
    def __init__(self, i2c, addr=WS1850S.DEFAULT_ADDR):
        self.dev = WS1850S(i2c, addr)

    def init(self):
        # WS1850S.__init__ already resets/configures the chip; this just
        # confirms the register bus is alive (mirrors the old begin() call).
        return self.dev.version()

    def antenna_on(self):
        """Energize the RF field. Call only while the poll trigger is held
        down -- see bbox_server.py's NFC_TRIGGER_PIN gating."""
        self.dev.antenna_on()

    def antenna_off(self):
        """De-energize the RF field between button presses -- the WS1850S
        keeps it on continuously otherwise, which is the bulk of its idle
        draw."""
        self.dev.antenna_off()

    def detect_tag(self, timeout=500):
        """Poll for a tag for up to `timeout` ms.

        The PN532's read_passive_target() blocked internally for `timeout`
        via its own firmware; the WS1850S has no such built-in timeout, so
        this repeats its (fast, hardware-timer-bounded) request/anticoll
        cycle until `timeout` elapses. Returns the same dict shape the
        PN532 path returned, or None.
        """
        deadline = time.ticks_add(time.ticks_ms(), timeout)
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            found = self.dev.read_uid_full()
            if found is not None:
                uid, sak = found
                tag = {
                    'uid': uid,
                    'uid_hex': ':'.join('%02X' % b for b in uid),
                    'uid_len': len(uid),
                    'atqa': None,
                    'sak': sak,
                }
                tag['tag_type'] = sak_type(sak)
                tag['is_classic'] = sak in (0x08, 0x18, 0x09)
                tag['is_ntag'] = sak == 0x00
                return tag
            time.sleep_ms(2)
        return None

    def mifare_auth(self, uid, block, key=b'\xFF\xFF\xFF\xFF\xFF\xFF', kt=MIFARE_AUTH_A):
        return self.dev.auth(kt, block, key, uid) == WS1850S.MI_OK

    def mifare_read(self, block):
        status, data = self.dev.read_block(block)
        if status != WS1850S.MI_OK or data is None:
            raise RuntimeError("Read err (block %d)" % block)
        return bytes(data)

    def mifare_write(self, block, data):
        status = self.dev.write_block(block, data)
        if status != WS1850S.MI_OK:
            raise RuntimeError("Classic write err (block %d)" % block)
        return True

    def ntag_write_page(self, page, data):
        status = self.dev.ul_write(page, data)
        if status != WS1850S.MI_OK:
            raise RuntimeError("NTAG write err (page %d)" % page)
        return True

    def ntag_read_page(self, page):
        status, data = self.dev.ul_read(page)
        if status != WS1850S.MI_OK or data is None:
            raise RuntimeError("Read err (page %d)" % page)
        return bytes(data[:4])


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
        except RuntimeError as e:
            print("# ntag page %d write failed: %s" % (page, str(e)))
            return False
        time.sleep_ms(WRITE_SETTLE_MS)
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
        except RuntimeError as e:
            print("# classic block %d write failed: %s" % (block, str(e)))
            return False
        time.sleep_ms(WRITE_SETTLE_MS)
    return written == blocks_needed


def write_text(nfc, tag, text, verify=True):
    """Write plain NDEF text `text` to the card. Returns True on success.

    With verify=True the card is read back and the decoded text compared
    against what we wrote. A partially-committed NDEF otherwise looks like
    a success here, and the wand then falls back to scanning raw card
    bytes -- where leftover text from a previous write can still match, so
    a bad "getcode" card silently launches whatever game was on it before.

    Wrapped in a broad except (not just the RuntimeError the low-level
    write calls raise) because a flaky I2C read/re-select during the
    write (detect_tag/mifare_auth) can also throw OSError -- letting that
    escape here took down the whole server loop on a transient timeout.
    """
    try:
        if tag['is_ntag']:
            ok = _write_ntag_text(nfc, text)
        elif tag['is_classic']:
            ok = _write_classic_text(nfc, tag, text)
        else:
            return False
        if not ok or not verify:
            return ok
        return _verify_text(nfc, tag, text)
    except Exception as e:
        print("# write_text err: %s" % str(e))
        return False


def _verify_text(nfc, tag, text):
    """Re-read the card and confirm it decodes back to `text`."""
    fresh = nfc.detect_tag(timeout=500)
    if fresh is None:
        print("# verify failed: card lifted before read-back")
        return False
    back = existing_text(nfc, fresh)
    if back == text.strip().lower():
        return True
    print("# verify failed: card reads back as %s, expected '%s'" % (repr(back), text))
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
