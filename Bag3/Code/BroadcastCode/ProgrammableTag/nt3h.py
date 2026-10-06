"""
nt3h.py - MicroPython driver for the NXP NT3H2111 (NTAG I2C plus, 2 KB),
as fitted to the MIKROE NFC Tag 2 Click.

The chip is a passive NFC Forum Type 2 tag with an I2C side. The RF side
(phone / wand reader) sees 4-byte pages; the I2C side sees 16-byte blocks
(block = 4 pages). Default 7-bit I2C address is 0x55.

Memory map (2k part; check against the NT3H2111 datasheet):
    block 0x00        UID, I2C address (byte 0), lock bytes, capability container
    blocks 0x01-0x77  user memory (NDEF TLV starts at block 1)
    block 0x7A        configuration registers (never written here)
    block 0xFE        session registers (NS_REG at byte 6)

Block 0 and everything above the user area are never written by this driver.
"""

import time


class NT3H:
    DEFAULT_ADDR = 0x55

    BLOCK_SIZE = 16
    FIRST_USER_BLOCK = 0x01
    LAST_USER_BLOCK = 0x77
    SESSION_BLOCK = 0xFE
    NS_REG = 0x06

    # NS_REG bits
    NS_RF_FIELD_PRESENT = 0x01
    NS_EEPROM_WR_BUSY   = 0x02
    NS_EEPROM_WR_ERR    = 0x04

    WRITE_TIMEOUT_MS = 50

    def __init__(self, i2c, addr=DEFAULT_ADDR):
        self.i2c = i2c
        self.addr = addr

    # --- raw access ---
    def read_block(self, block):
        return bytes(self.i2c.readfrom_mem(self.addr, block, self.BLOCK_SIZE))

    def write_block(self, block, data):
        if block < self.FIRST_USER_BLOCK or block > self.LAST_USER_BLOCK:
            raise ValueError(f"block {block:#x} outside user memory")
        if len(data) != self.BLOCK_SIZE:
            raise ValueError("block write needs exactly 16 bytes")
        self.i2c.writeto_mem(self.addr, block, data)
        return self._wait_write_done()

    def _read_session_reg(self, reg):
        self.i2c.writeto(self.addr, bytes([self.SESSION_BLOCK, reg]), False)
        return self.i2c.readfrom(self.addr, 1)[0]

    def ns_reg(self):
        return self._read_session_reg(self.NS_REG)

    def _wait_write_done(self):
        """Wait for the EEPROM write to finish. True on success."""
        time.sleep_ms(5)
        t0 = time.ticks_ms()
        while True:
            try:
                ns = self.ns_reg()
                if not (ns & self.NS_EEPROM_WR_BUSY):
                    return not (ns & self.NS_EEPROM_WR_ERR)
            except OSError:
                pass
            if time.ticks_diff(time.ticks_ms(), t0) > self.WRITE_TIMEOUT_MS:
                return False
            time.sleep_ms(1)

    # --- status ---
    def present(self):
        try:
            self.read_block(0)
            return True
        except OSError:
            return False

    def rf_field_present(self):
        return bool(self.ns_reg() & self.NS_RF_FIELD_PRESENT)

    def read_uid(self):
        b0 = self.read_block(0)
        return bytes([0x04]) + b0[1:7]

    def read_cc(self):
        return self.read_block(0)[12:16]

    # --- 4-byte page view (what the RF side / wand reader sees) ---
    def read_page(self, page):
        block = page // 4
        off = (page % 4) * 4
        return self.read_block(block)[off:off + 4]

    def write_page(self, page, data):
        if len(data) != 4:
            raise ValueError("page write needs exactly 4 bytes")
        block = page // 4
        off = (page % 4) * 4
        buf = bytearray(self.read_block(block))
        buf[off:off + 4] = data
        return self.write_block(block, bytes(buf))

    # --- NDEF TLV area ---
    def read_tlv_area(self, max_blocks=8):
        """Read user memory from block 1 until the terminator or max_blocks."""
        out = b''
        for i in range(max_blocks):
            blk = self.FIRST_USER_BLOCK + i
            if blk > self.LAST_USER_BLOCK:
                break
            out += self.read_block(blk)
            if 0xFE in out:
                break
        return out

    def write_ndef(self, tlv):
        """Write a complete TLV (03 len ... FE) starting at block 1."""
        n = (len(tlv) + self.BLOCK_SIZE - 1) // self.BLOCK_SIZE
        if self.FIRST_USER_BLOCK + n - 1 > self.LAST_USER_BLOCK:
            raise ValueError("record too large")
        tlv = bytes(tlv) + b'\x00' * (n * self.BLOCK_SIZE - len(tlv))
        for i in range(n):
            chunk = tlv[i * self.BLOCK_SIZE:(i + 1) * self.BLOCK_SIZE]
            if not self.write_block(self.FIRST_USER_BLOCK + i, chunk):
                return False
        return True
