"""
probe_nt3h.py - bench check for the NFC Tag 2 Click on a XIAO ESP32-C6.

Run with the firmware files on the board (nt3h.py, ndef.py). Prints PASS/FAIL
per stage. Writes only to user block 0x20, which is outside the NDEF area,
and restores it afterwards.
"""

import time
from machine import Pin, SoftI2C

from nt3h import NT3H

I2C_SDA = 22
I2C_SCL = 23
TEST_BLOCK = 0x20


def result(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'} {name} {detail}")
    return ok


i2c = SoftI2C(sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=100_000)
found = i2c.scan()
print("scan:", [hex(a) for a in found])
result("nt3h at 0x55", NT3H.DEFAULT_ADDR in found)
result("oled at 0x3c", 0x3C in found)

if NT3H.DEFAULT_ADDR in found:
    tag = NT3H(i2c)
    b0 = tag.read_block(0)
    print("block0:", b0.hex())
    print("uid:", tag.read_uid().hex(), "cc:", tag.read_cc().hex())
    for blk in range(1, 5):
        print(f"block{blk}:", tag.read_block(blk).hex())
    print("ns_reg:", hex(tag.ns_reg()))

    saved = tag.read_block(TEST_BLOCK)
    pattern = bytes(range(0xA0, 0xB0))
    ok = tag.write_block(TEST_BLOCK, pattern)
    result("write ack", ok)
    result("readback", tag.read_block(TEST_BLOCK) == pattern)
    tag.write_block(TEST_BLOCK, saved)
    result("restore", tag.read_block(TEST_BLOCK) == saved)
