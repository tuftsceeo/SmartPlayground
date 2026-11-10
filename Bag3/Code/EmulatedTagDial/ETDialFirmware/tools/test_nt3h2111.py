"""test_nt3h2111.py -- host tests for nt3h2111.py (CPython, fake I2C).

    python3 Bag3/Code/EmulatedTagDial/ETDialFirmware/tools/test_nt3h2111.py
"""

import os
import sys
import time
import types
import unittest

BD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BD)

sys.modules.setdefault("machine", types.ModuleType("machine"))
time.sleep_ms = lambda ms: None

import nt3h2111 as NT                           # noqa: E402
from card_writer import build_ndef_text         # noqa: E402


class FakeI2C:
    """NT3H2111 block memory at 0x55; block 0 starts blank (no CC)."""
    def __init__(self, cc=b'\x00\x00\x00\x00'):
        self.mem = {0: bytes([0xAA, 4, 1, 2, 3, 4, 5, 6, 7, 0x48, 0, 0]) + cc}
        self.writes = []
        self.ptr = 0
        self.nak = False

    def scan(self):
        return [0x28, 0x55]

    def writeto(self, addr, buf):
        if self.nak or addr != 0x55:
            raise OSError(19)
        buf = bytes(buf)
        self.ptr = buf[0]
        if len(buf) > 1:
            assert len(buf) == 17, len(buf)
            self.writes.append(self.ptr)
            self.mem[self.ptr] = buf[1:]

    def readfrom(self, addr, n):
        return self.mem.get(self.ptr, bytes(16))[:n]


class Driver(unittest.TestCase):
    def test_blocks_match_card_ndef(self):
        i2c = FakeI2C()
        text = "getcode:melody@004c"
        self.assertTrue(NT.NT3H2111(i2c).write_text(text))
        ndef = build_ndef_text(text)
        got = b"".join(i2c.mem[b] for b in range(1, 1 + (len(ndef) + 15) // 16))
        self.assertEqual(got[:len(ndef)], ndef)
        self.assertEqual(i2c.writes, [0, 1, 2])

    def test_block0_keeps_address(self):
        i2c = FakeI2C()
        NT.NT3H2111(i2c).write_text("stop")
        self.assertEqual(i2c.mem[0][0], 0xAA)
        self.assertEqual(i2c.mem[0][12:16], NT.CC)
        self.assertEqual(i2c.mem[0][1:12], bytes([4, 1, 2, 3, 4, 5, 6, 7, 0x48, 0, 0]))

    def test_cc_present_block0_untouched(self):
        i2c = FakeI2C(cc=NT.CC)
        NT.NT3H2111(i2c).write_text("stop")
        self.assertEqual(i2c.writes, [1])

    def test_nak_returns_false(self):
        i2c = FakeI2C()
        i2c.nak = True
        self.assertFalse(NT.NT3H2111(i2c).write_text("stop"))

    def test_present(self):
        self.assertTrue(NT.NT3H2111(FakeI2C()).present())
        self.assertFalse(NT.NT3H2111(FakeI2C(), addr=0x56).present())


if __name__ == "__main__":
    unittest.main()
