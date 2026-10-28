"""
PN5180 NFC Reader/Writer Driver — MicroPython (SPI)
===================================================
Drop-in for MockWand's lib/pn532.py: same public methods and return
shapes, so NfcReader and read_ndef_text work unchanged.

Supports:
  • MIFARE Classic auth / read / write
  • NTAG / Ultralight page read / write
  • ISO14443A tag detection (UID + SAK), 4/7/10-byte UIDs

Usage:
    from pn5180 import PN5180
    from machine import Pin, SPI

    spi = SPI(2, baudrate=2_000_000, sck=Pin(7), mosi=Pin(43), miso=Pin(44))
    nfc = PN5180(spi, nss=Pin(3), busy=Pin(1), rst=Pin(9))
    nfc.begin()

    tag = nfc.read_passive_target()
    if tag:
        print(tag['uid_hex'], tag['sak'])
"""

import time
from machine import Pin

# Host commands
_WRITE_REGISTER          = 0x00
_WRITE_REGISTER_OR_MASK  = 0x01
_WRITE_REGISTER_AND_MASK = 0x02
_READ_REGISTER           = 0x04
_READ_EEPROM             = 0x07
_SEND_DATA               = 0x09
_READ_DATA               = 0x0A
_MIFARE_AUTHENTICATE     = 0x0C
_LOAD_RF_CONFIG          = 0x11
_RF_ON                   = 0x16
_RF_OFF                  = 0x17

# Registers
_SYSTEM_CONFIG = 0x00
_IRQ_STATUS    = 0x02
_IRQ_CLEAR     = 0x03
_CRC_RX_CONFIG = 0x12
_RX_STATUS     = 0x13
_CRC_TX_CONFIG = 0x19

_RX_IRQ = 0x01
_RX_ERRORS = 0x001C0000   # RX_STATUS: data integrity, protocol, collision
_MFC_CRYPTO_ON = 0x40

# MIFARE / NTAG PICC commands
MIFARE_AUTH_A = 0x60
MIFARE_AUTH_B = 0x61
MIFARE_READ   = 0x30
MIFARE_WRITE  = 0xA0   # MIFARE Classic 16-byte write
NTAG_WRITE    = 0xA2   # NTAG / Ultralight 4-byte page write


class PN5180:
    def __init__(self, spi, nss, busy, rst=None):
        self.spi = spi
        self.nss = nss
        self.busy = busy
        self.rst = rst
        self.nss.init(Pin.OUT, value=1)
        self.busy.init(Pin.IN)
        if self.rst:
            self.rst.init(Pin.OUT, value=1)
        self.fw_version = None
        self.field_off_ms = 5
        self.field_on_ms = 5

    # ─── Low-level SPI protocol ───

    def _busy_rise(self, us=100):
        start = time.ticks_us()
        while not self.busy.value():
            if time.ticks_diff(time.ticks_us(), start) > us:
                return

    def _wait_busy(self, level, timeout=100):
        start = time.ticks_ms()
        while self.busy.value() != level:
            if time.ticks_diff(time.ticks_ms(), start) > timeout:
                return False
        return True

    def _cmd(self, frame, n=0, timeout=100):
        if not self._wait_busy(0, timeout):
            raise RuntimeError("BUSY stuck high")
        self.nss(0); self.spi.write(bytes(frame)); self.nss(1)
        self._busy_rise()
        self._wait_busy(0, timeout)
        if not n:
            return None
        buf = bytearray(n)
        self.nss(0); self.spi.readinto(buf, 0xFF); self.nss(1)
        self._busy_rise()
        self._wait_busy(0, timeout)
        return buf

    def _reg_write(self, reg, val):
        self._cmd([_WRITE_REGISTER, reg] + _le(val))

    def _reg_or(self, reg, val):
        self._cmd([_WRITE_REGISTER_OR_MASK, reg] + _le(val))

    def _reg_and(self, reg, val):
        self._cmd([_WRITE_REGISTER_AND_MASK, reg] + _le(val))

    def _reg_read(self, reg):
        b = self._cmd([_READ_REGISTER, reg], 4)
        return b[0] | b[1] << 8 | b[2] << 16 | b[3] << 24

    def _crc(self, tx, rx):
        for reg, on in ((_CRC_TX_CONFIG, tx), (_CRC_RX_CONFIG, rx)):
            if on:
                self._reg_or(reg, 1)
            else:
                self._reg_and(reg, 0xFFFFFFFE)

    def _transceive(self, data, bits=0, timeout=10):
        """Send `data` (last byte `bits` long, 0 = 8) and return the reply,
        or None if nothing arrived within `timeout` ms or the reply has a
        CRC, protocol or collision error."""
        self._reg_and(_SYSTEM_CONFIG, 0xFFFFFFF8)
        self._reg_or(_SYSTEM_CONFIG, 0x00000003)
        self._reg_write(_IRQ_CLEAR, 0xFFFFFFFF)
        self._cmd([_SEND_DATA, bits] + list(data))
        start = time.ticks_ms()
        while not (self._reg_read(_IRQ_STATUS) & _RX_IRQ):
            if time.ticks_diff(time.ticks_ms(), start) > timeout:
                return None
        rx = self._reg_read(_RX_STATUS)
        n = rx & 0x1FF
        if not n or rx & _RX_ERRORS:
            return None
        return self._cmd([_READ_DATA, 0x00], n)

    def _field_reset(self):
        self._cmd([_RF_OFF, 0x00])
        time.sleep_ms(self.field_off_ms)
        self._cmd([_RF_ON, 0x00])
        time.sleep_ms(self.field_on_ms)

    # ─── High-level commands ───

    def begin(self):
        """Reset, read versions, load ISO14443A 106 kbit/s and turn the field on.

        Returns a 3-tuple (product_major, fw_major, fw_minor) so callers that
        unpack `ic, ver, rev = nfc.begin()` keep working.
        """
        if self.rst:
            self.rst(0); time.sleep_ms(10); self.rst(1); time.sleep_ms(50)
        prod = self._cmd([_READ_EEPROM, 0x10, 2], 2)
        fw = self._cmd([_READ_EEPROM, 0x12, 2], 2)
        if prod[1] in (0x00, 0xFF):
            raise RuntimeError("PN5180 not responding")
        self.fw_version = (prod[1], fw[1], fw[0])
        self._cmd([_LOAD_RF_CONFIG, 0x00, 0x80])
        self._cmd([_RF_ON, 0x00])
        time.sleep_ms(5)
        return self.fw_version

    def _select(self):
        """One WUPA + anticollision/select cascade. Returns the tag dict or None."""
        self._reg_and(_SYSTEM_CONFIG, ~_MFC_CRYPTO_ON & 0xFFFFFFFF)
        self._crc(False, False)
        atqa = self._transceive([0x52], 7)
        if not atqa or len(atqa) < 2:
            return None
        uid = b''
        for sel in (0x93, 0x95, 0x97):
            self._crc(False, False)
            r = self._transceive([sel, 0x20])
            if not r or len(r) != 5 or r[0] ^ r[1] ^ r[2] ^ r[3] ^ r[4]:
                return None
            self._crc(True, True)
            sak = self._transceive([sel, 0x70] + list(r[:5]))
            if not sak:
                return None
            if sak[0] & 0x04:
                uid += bytes(r[1:4])
            else:
                uid += bytes(r[:4])
                return {
                    'uid': uid,
                    'uid_hex': ':'.join('%02X' % b for b in uid),
                    'uid_len': len(uid),
                    'atqa': (atqa[1] << 8) | atqa[0],
                    'sak': sak[0],
                }
        return None

    def read_passive_target(self, baud=0x00, timeout=500):
        """
        Detect an ISO14443A tag, retrying until `timeout` ms.

        Returns dict with uid, uid_hex, uid_len, atqa, sak, or None if no
        tag found. On success the card is selected and ready for auth
        (Classic) or page read/write (NTAG).
        """
        start = time.ticks_ms()
        while True:
            self._field_reset()
            try:
                tag = self._select()
            except RuntimeError:
                tag = None
            if tag or time.ticks_diff(time.ticks_ms(), start) > timeout:
                return tag
            time.sleep_ms(1)

    # ─── MIFARE Classic ───

    def mifare_auth_block(self, uid, block, key=b'\xFF\xFF\xFF\xFF\xFF\xFF', key_type=MIFARE_AUTH_A):
        """Authenticate a MIFARE Classic block. Returns True on success."""
        try:
            resp = self._cmd([_MIFARE_AUTHENTICATE] + list(key) + [key_type, block] + list(uid[:4]), 1, timeout=1000)
            return resp[0] == 0x00
        except Exception:
            return False

    def _read16(self, addr, tries=3):
        """READ (0x30): 16 bytes. Retries a dropped or corrupted reply; the
        card keeps its selected/authenticated state across a lost frame."""
        self._crc(True, True)
        for _ in range(tries):
            resp = self._transceive([MIFARE_READ, addr])
            if resp and len(resp) >= 16:
                return bytes(resp[:16])
        raise RuntimeError("Read err")

    def _ack(self, data):
        resp = self._transceive(data)
        return bool(resp) and (resp[0] & 0x0F) == 0x0A

    def mifare_read_block(self, block):
        """Read 16 bytes from an authenticated MIFARE Classic block."""
        return self._read16(block)

    def mifare_write_block(self, block, data):
        """Write 16 bytes to an authenticated MIFARE Classic block."""
        if len(data) != 16:
            raise ValueError("MIFARE write needs exactly 16 bytes")
        self._crc(True, False)
        if not (self._ack([MIFARE_WRITE, block]) and self._ack(list(data))):
            raise RuntimeError("Classic write err")
        return True

    # ─── NTAG / Ultralight ───

    def ntag_read_page(self, page):
        """Read 4 bytes from an NTAG/Ultralight page.

        (The PICC READ returns 16 bytes / 4 pages; we return the first 4
        so callers get the single requested page.)
        """
        return self._read16(page)[:4]

    def ntag_write_page(self, page, data):
        """Write 4 bytes to a single NTAG/Ultralight page."""
        if len(data) != 4:
            raise ValueError("NTAG write needs exactly 4 bytes")
        self._crc(True, False)
        if not self._ack([NTAG_WRITE, page] + list(data)):
            raise RuntimeError("NTAG write err")
        return True


def _le(v):
    return [v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF, (v >> 24) & 0xFF]
