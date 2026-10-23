"""nt3h2111.py -- NXP NT3H2111 (MIKROE NFC Tag 2 Click) over I2C: an NDEF
text tag the Dial rewrites from its menus, read by a wand like a card.

Over I2C the chip's memory is 16-byte blocks: write the block number, then
read 16 bytes; or write the block number plus 16 bytes. Block 0 is the I2C
address byte, UID, lock bytes and the capability container (CC, bytes
12-15); its byte 0 reads back as the address and a write to it SETS the
address, so block 0 is only rewritten with that byte kept. NDEF starts at
block 1 (NFC page 4) -- the same bytes card_writer writes to an NTAG card.

While a reader's RF field holds the chip (arbitration), I2C writes NAK;
write_text() returns False and the caller retries.

Imported by dial_board.make_reader(), after the radio prewarm.
"""

import time

from card_writer import build_ndef_text

DEFAULT_ADDR = 0x55
ADDR_BYTE = DEFAULT_ADDR << 1   # block 0 byte 0 (8-bit form of the address)
CC = b'\xE1\x10\x6D\x00'        # NDEF v1.0, 872-byte data area, read/write
BLOCK = 16
WRITE_MS = 5                    # EEPROM program time per block (~4 ms)


class NT3H2111:
    def __init__(self, i2c, addr=DEFAULT_ADDR):
        self.i2c = i2c
        self.addr = addr

    def present(self):
        try:
            return self.addr in self.i2c.scan()
        except OSError:
            return False

    def read_block(self, n):
        self.i2c.writeto(self.addr, bytes([n]))
        return self.i2c.readfrom(self.addr, BLOCK)

    def write_block(self, n, data):
        self.i2c.writeto(self.addr, bytes([n]) + bytes(data))
        time.sleep_ms(WRITE_MS)

    def _ensure_cc(self):
        b0 = bytearray(self.read_block(0))
        if bytes(b0[12:16]) == CC:
            return
        b0[0] = ADDR_BYTE
        b0[12:16] = CC
        self.write_block(0, b0)

    def write_text(self, text):
        """Write `text` as one NDEF text record. True on success."""
        try:
            self._ensure_cc()
            data = build_ndef_text(text)
            data += bytes(-len(data) % BLOCK)
            for i in range(0, len(data), BLOCK):
                self.write_block(1 + i // BLOCK, data[i:i + BLOCK])
            return True
        except OSError as e:
            print("# tag write failed: %s" % str(e))
            return False
