"""
probe_reader.py - read the NT3H tag through the WS1850S the way the NFC
Station does (read_uid_full, ul_read pages 4-19, NDEF decode), and compare
with the I2C view of the same memory.

Needs ws1850s.py, nt3h.py and ndef.py on the board.
"""

import time
from machine import Pin, SoftI2C

from ws1850s import WS1850S
from nt3h import NT3H
import ndef

i2c = SoftI2C(sda=Pin(22), scl=Pin(23), freq=100_000)
print("scan", [hex(a) for a in i2c.scan()])
tag = NT3H(i2c)
rd = WS1850S(i2c)
print("ws1850s version", hex(rd.version()))


def reader_view():
    rd.antenna_on()
    time.sleep_ms(20)
    found = None
    for _ in range(40):
        found = rd.read_uid_full()
        if found:
            break
        time.sleep_ms(10)
    if not found:
        print("reader: no tag found")
        return None
    uid, sak = found
    print("reader: uid", uid.hex(), "sak", hex(sak))
    data = bytearray()
    for page in range(4, 20):
        status, d = rd.ul_read(page)
        if status != WS1850S.MI_OK or d is None:
            print("reader: page", page, "failed status", status)
            break
        data.extend(bytes(d[:4]))
    print("reader: pages4-19", bytes(data).hex())
    print("reader: text", repr(ndef.decode_ndef_text(bytes(data))))
    return bytes(data)


print("i2c view: block1", tag.read_block(1).hex(), "ns", hex(tag.ns_reg()))
r1 = reader_view()
print("i2c view after: ns", hex(tag.ns_reg()), "block1", tag.read_block(1).hex())
