"""
PN532 compatibility shim — backed by the WS1850S (M5Stack RFID2)
================================================================
Bag3 replaces the PN532 NFC reader with an M5Stack RFID2 unit built
around the WS1850S (an MFRC522-register-compatible IC at I2C 0x28).

The wand games and lib/nfc_reader.py were all written against the PN532
driver API:

    from pn532 import PN532, MIFARE_AUTH_A, MIFARE_AUTH_B
    nfc = PN532(i2c, PN532_ADDR)
    nfc.begin()
    tag = nfc.read_passive_target(timeout=250)   # -> dict | None
    nfc.mifare_auth_block(uid, block, key, key_type)
    nfc.mifare_read_block(block)                 # -> 16 bytes
    nfc.ntag_read_page(page)                     # -> 4 bytes

This module keeps that exact surface so none of the game code has to
change. The actual PN532 wire protocol is gone; every call is translated
to the WS1850S driver (lib/ws1850s.py) underneath.

The legacy PN532 I2C address (0x24) is transparently remapped to the
WS1850S default (0x28), so callers passing the old PN532_ADDR still work.
"""

import time
from ws1850s import WS1850S

# MIFARE key-type constants — same values the PN532 driver exported, and
# they happen to match the WS1850S PICC_AUTHENT1A/1B codes exactly.
MIFARE_AUTH_A = 0x60
MIFARE_AUTH_B = 0x61
MIFARE_READ   = 0x30

# Old PN532 I2C address — remapped to the WS1850S default.
_LEGACY_PN532_ADDR = 0x24


class PN532:
    """PN532-shaped facade over a WS1850S reader."""

    def __init__(self, i2c, addr=WS1850S.DEFAULT_ADDR):
        # Accept the legacy PN532 address (or None) and point at the WS1850S.
        if addr in (None, _LEGACY_PN532_ADDR):
            addr = WS1850S.DEFAULT_ADDR
        self.i2c = i2c
        self.addr = addr
        self._dev = WS1850S(i2c, addr)
        self.fw_version = None

    # ─── High-level lifecycle ───

    def begin(self):
        """
        (Re)initialize the reader. Returns a 3-tuple shaped like the PN532's
        firmware-version tuple so callers that unpack `ic, ver, rev` keep
        working. Here it carries the WS1850S VersionReg in the first slot.
        """
        self._dev.init()
        ver = self._dev.version()
        self.fw_version = (ver, 0, 0)
        return self.fw_version

    # ─── Tag detection ───

    def read_passive_target(self, baud=0x00, timeout=500):
        """
        Poll for an ISO14443A tag for up to `timeout` ms.

        Returns a dict {uid, uid_hex, uid_len, atqa, sak} on success, or
        None if no tag appeared within the window. On success the card is
        left in the ACTIVE state, ready for auth (Classic) or page reads
        (Ultralight/NTAG) — same contract as the old PN532 driver.
        """
        # Clear any leftover MIFARE Classic Crypto1 state from a previous
        # auth/read. The WS1850S leaves Crypto1 enabled after auth, which
        # encrypts the next anticollision/SELECT and makes it silently fail —
        # that would break multi-sector reads and re-detecting the next card.
        try:
            self._dev.stop_crypto1()
        except Exception:
            pass
        deadline = time.ticks_add(time.ticks_ms(), timeout)
        while True:
            try:
                result = self._dev.read_uid_full()
            except Exception:
                result = None
            if result is not None:
                uid, sak = result
                return {
                    'uid': bytes(uid),
                    'uid_hex': ':'.join('%02X' % b for b in uid),
                    'uid_len': len(uid),
                    'atqa': 0,          # WS1850S doesn't surface ATQA; unused downstream
                    'sak': sak,
                }
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                return None
            time.sleep_ms(10)

    # ─── MIFARE Classic ───

    def mifare_auth_block(self, uid, block, key=b'\xFF\xFF\xFF\xFF\xFF\xFF',
                          key_type=MIFARE_AUTH_A):
        """Authenticate a MIFARE Classic block. Returns True on success.

        The card must already be selected (call read_passive_target first),
        exactly as with the PN532 flow in nfc_reader.py.
        """
        try:
            return self._dev.auth(key_type, block, key, uid) == WS1850S.MI_OK
        except Exception:
            return False

    def mifare_read_block(self, block):
        """Read 16 bytes from an authenticated MIFARE Classic block."""
        status, data = self._dev.read_block(block)
        if status != WS1850S.MI_OK or data is None:
            raise RuntimeError("Classic read err on block %d" % block)
        return bytes(data[:16])

    # ─── NTAG / Ultralight ───

    def ntag_read_page(self, page):
        """Read 4 bytes from a single NTAG/Ultralight page.

        WS1850S READ returns 16 bytes (4 pages) at once; we slice out the
        requested page so the byte stream lines up with the PN532's
        page-at-a-time contract that nfc_reader.py relies on.
        """
        status, data = self._dev.ul_read(page)
        if status != WS1850S.MI_OK or data is None:
            raise RuntimeError("NTAG read err on page %d" % page)
        return bytes(data[:4])
