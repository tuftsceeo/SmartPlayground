"""
nfc_ws1850s.py -- drive the display's WS1850S reader through nfc_reader.py.

The icon display has a reader on the XIAO ESP32-C6's I2C bus: the same chip
as the Broadcast Box (WS1850S at 0x28), on the same pins as the wand
(SDA 22 / SCL 23, 100 kHz). The wand's nfc_reader.py -- which this tree
carries verbatim -- was written against a PN532 and calls exactly four
methods on its reader object:

    read_passive_target(timeout=)      mifare_auth_block(uid, block, key, key_type)
    mifare_read_block(block)           ntag_read_page(page)

This module presents those four on top of the WS1850S, so the card-reading
logic (NDEF text, MIFARE Classic sectors, NTAG pages) stays one shared file
rather than two that drift. The mapping is the same one card_writer.py makes
on the Box and the Dial; only the read half is here, because this device
never writes a card.

Two differences from the PN532 the shim has to absorb:

  * No firmware-side timeout. The PN532 blocked inside its own firmware for
    `timeout` ms; the WS1850S has no such thing, so detection repeats a fast
    request/anticoll cycle until the deadline.
  * Crypto1 latches. Any MIFARE auth -- successful or not -- leaves the
    reader in encrypted mode, and every later detect fails until it is
    cleared. stop_crypto1() therefore runs before each detection, exactly
    where card_writer.py's read path puts it.
"""

import time

from ws1850s import WS1850S

# The two key-type constants nfc_reader.py imports from here. Same values
# the PN532 driver used (0x60/0x61) -- they are the MIFARE command bytes,
# not anything either chip invented.
MIFARE_AUTH_A = WS1850S.PICC_AUTHENT1A
MIFARE_AUTH_B = WS1850S.PICC_AUTHENT1B

DEFAULT_ADDR = WS1850S.DEFAULT_ADDR      # 0x28


def sak_type(sak):
    """Human-readable card type for a SAK byte, for boot/debug printing."""
    if sak == 0x00:
        return "NTAG/Ultralight"
    if sak in (0x08, 0x09):
        return "MIFARE Classic 1K"
    if sak == 0x18:
        return "MIFARE Classic 4K"
    return "unknown (SAK 0x%02X)" % sak


class Ws1850sReader:
    """A WS1850S wearing the four method names nfc_reader.py calls."""

    def __init__(self, i2c, addr=DEFAULT_ADDR):
        self.dev = WS1850S(i2c, addr)

    def begin(self):
        """Confirm the register bus is alive and energize the field.

        Returns the chip's version byte. Raises if the bus is dead -- a
        reader that cannot be talked to is a wiring fault, and a display
        that silently never reads a card is the hardest failure to spot.

        The antenna stays on for the life of the session: this device polls
        continuously like the wand, unlike the Box, which gates the field on
        a button to keep its current draw down.
        """
        version = self.dev.version()
        self.dev.antenna_on()
        return version

    # ── the four PN532-shaped methods ───────────────────────────────
    def read_passive_target(self, baud=0x00, timeout=500):
        """Poll for an ISO14443A tag. Returns the PN532's dict shape, or None.

        `baud` is accepted and ignored: the PN532 took it, the WS1850S has
        no equivalent, and keeping the signature means nfc_reader.py needs
        no special case.
        """
        self.dev.stop_crypto1()   # see the module docstring on Crypto1 latching
        deadline = time.ticks_add(time.ticks_ms(), timeout)
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            found = self.dev.read_uid_full()
            if found is not None:
                uid, sak = found
                return {
                    'uid': uid,
                    'uid_hex': ':'.join('%02X' % b for b in uid),
                    'uid_len': len(uid),
                    'atqa': None,      # the WS1850S path does not surface it
                    'sak': sak,
                }
            time.sleep_ms(2)
        return None

    def mifare_auth_block(self, uid, block,
                          key=b'\xFF\xFF\xFF\xFF\xFF\xFF', key_type=MIFARE_AUTH_A):
        """Authenticate a MIFARE Classic block. True on success."""
        return self.dev.auth(key_type, block, key, uid) == WS1850S.MI_OK

    def mifare_read_block(self, block):
        """16 bytes from an authenticated MIFARE Classic block."""
        status, data = self.dev.read_block(block)
        if status != WS1850S.MI_OK or data is None:
            raise RuntimeError("Classic read err (block %d)" % block)
        return bytes(data)

    def ntag_read_page(self, page):
        """4 bytes from an NTAG/Ultralight page."""
        status, data = self.dev.ul_read(page)
        if status != WS1850S.MI_OK or data is None:
            raise RuntimeError("NTAG read err (page %d)" % page)
        return bytes(data[:4])

    # ── housekeeping nfc_reader.py does not call, but callers may ───
    def stop_crypto1(self):
        self.dev.stop_crypto1()

    def antenna_off(self):
        self.dev.antenna_off()
