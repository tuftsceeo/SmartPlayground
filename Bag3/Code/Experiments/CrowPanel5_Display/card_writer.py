# Copy of BDialFirmware/card_writer.py (NfcWriter removed)
"""card_writer.py - plain NDEF text writer. Copy of the Dial's, without the WS1850S NfcWriter;
nfc.py supplies the reader object (same method names)."""

import time


# Chatty per-attempt tracing. Off by default: the failure lines below are
# NOT gated by this -- a real failure always prints. This only controls the
# step-by-step success narration used when diagnosing the reader.
VERBOSE = False


def _log(msg):
    print("# [nfc] %s" % msg)


def _dbg(msg):
    if VERBOSE:
        print("# [nfc] %s" % msg)


MIFARE_AUTH_A = 0x60
MIFARE_AUTH_B = 0x61

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
#
# Text ('T') AND URI ('U') records: this file only ever WRITES Text
# records (build_ndef_text() above), but older tags from Bag1/Bag2 can
# carry either -- Bag2's own writetoNFCcards.py and this file's write
# path both only emit 'T', yet Bag2/Code/lib/nfc_reader.py (and both
# Bag2's and Bag3's readfromNFCcards.py diagnostic tools) always decoded
# both, so some tags in circulation may be URI records (e.g. from a
# generic/off-the-shelf NFC writer app, which defaults to URI). This
# ported copy had silently dropped the URI branch -- restored below so
# reading matches what Bag2 could always read; still never written here.
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
                elif bytes(rec_type) == b'U' and len(payload) > 1:
                    # URI abbreviation code (NFC Forum RTD-URI) -- payload[0]
                    # is an index into this table, not raw text; the rest of
                    # the payload is appended after the matched prefix.
                    prefixes = [
                        "", "http://www.", "https://www.", "http://",
                        "https://", "tel:", "mailto:",
                    ]
                    pre = prefixes[payload[0]] if payload[0] < len(prefixes) else ""
                    return (pre + bytes(payload[1:]).decode('utf-8', 'replace')).strip().lower()
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
        _log("write: NDEF too big (%d blocks)" % blocks_needed)
        return False

    written = 0
    for i in range(blocks_needed):
        block = writable_blocks[i]
        sector = block // 4
        first_block = sector * 4
        chunk = ndef[i * 16: i * 16 + 16]

        nfc.stop_crypto1()  # see existing_text: required before any REQA
        resel = nfc.detect_tag(timeout=300)
        if resel is None:
            _log("write: blk%d reselect FAILED (crypto=%s ant=%s) -- ABORT"
                 % (block, nfc.crypto_on(), nfc.antenna_is_on()))
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
            _log("write: blk%d NO auth (crypto=%s) -- ABORT"
                 % (block, nfc.crypto_on()))
            return False
        try:
            nfc.mifare_write(block, chunk)
            written += 1
        except RuntimeError as e:
            print("# classic block %d write failed: %s" % (block, str(e)))
            return False
        time.sleep_ms(WRITE_SETTLE_MS)
    nfc.stop_crypto1()
    _dbg("write: classic wrote %d/%d blocks" % (written, blocks_needed))
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
    _dbg("write: start text=%s uid=%s type=%s crypto=%s"
         % (repr(text), tag['uid_hex'], tag['tag_type'], nfc.crypto_on()))
    try:
        if tag['is_ntag']:
            ok = _write_ntag_text(nfc, text)
        elif tag['is_classic']:
            ok = _write_classic_text(nfc, tag, text)
        else:
            _log("write: unknown tag type -- ABORT")
            return False
        if not ok:
            _log("write: FAILED before verify")
            return False
        if not verify:
            _dbg("write: OK (unverified)")
            return True
        vok = _verify_text(nfc, tag, text)
        _log("write: verify %s" % ("OK" if vok else "FAILED"))
        return vok
    except Exception as e:
        _log("write: EXCEPTION %s" % str(e))
        return False


def _verify_text(nfc, tag, text):
    """Re-read the card and confirm it decodes back to `text`."""
    nfc.stop_crypto1()
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
    _dbg("read: start uid=%s type=%s crypto=%s"
         % (tag['uid_hex'], tag['tag_type'], nfc.crypto_on()))
    try:
        if tag['is_ntag']:
            data = bytearray()
            for page in range(4, 20):
                try:
                    data.extend(nfc.ntag_read_page(page))
                except Exception as e:
                    _log("read: ntag page %d stopped: %s" % (page, str(e)))
                    break
            out = _decode_ndef_text(data)
            _dbg("read: ntag decoded %s" % repr(out))
            return out
        if tag['is_classic']:
            data = bytearray()
            for sector in (1, 2):
                fb = sector * 4
                authed = False
                misses = 0
                for ki in range(len(COMMON_KEYS)):
                    key = COMMON_KEYS[ki]
                    for kt in (MIFARE_AUTH_A, MIFARE_AUTH_B):
                        # Any auth -- successful or not -- latches the reader
                        # into encrypted mode (MFCrypto1On). While that bit is
                        # set the reader cannot answer a plain REQA, so the
                        # re-select below finds nothing. Clear it first, every
                        # time. Toggling the antenna does NOT clear it.
                        nfc.stop_crypto1()
                        resel = nfc.detect_tag(timeout=150)
                        if resel is None:
                            misses += 1
                            _dbg("read: sec%d reselect miss (crypto=%s ant=%s)"
                                 % (sector, nfc.crypto_on(), nfc.antenna_is_on()))
                            continue
                        if nfc.mifare_auth(resel['uid'], fb, key, kt):
                            _dbg("read: sec%d auth OK key#%d kt=%s"
                                 % (sector, ki, kt))
                            for blk in range(fb, fb + 3):
                                try:
                                    data.extend(nfc.mifare_read(blk))
                                except Exception:
                                    data.extend(b'\x00' * 16)
                            authed = True
                            break
                    if authed:
                        break
                nfc.stop_crypto1()  # leave the reader in plain mode
                if not authed:
                    _log("read: sec%d NO auth after %d reselect misses (crypto=%s)"
                         % (sector, misses, nfc.crypto_on()))
                    data.extend(b'\x00' * 48)
            out = _decode_ndef_text(data)
            _dbg("read: classic decoded %s" % repr(out))
            return out
        _log("read: unknown tag type, no read path")
        return None
    except Exception as e:
        _log("read: EXCEPTION %s" % str(e))
        return None
