"""
dep_sender.py -- NFC-DEP target ("broadcast device") bench script, wand A.

Waits as a DEP target and serves PAYLOAD to any initiator (dep_receiver.py)
until Ctrl-C. Needs pn532_dep.py, dep_proto.py and PAYLOAD on the wand's
flash. Run with:  mpremote run dep_sender.py
"""

import time
import machine

from pn532_dep import PN532Dep, DepError, STATUS_RELEASED
from dep_proto import build_header, handle_request, MAX_CHUNK

# Mock Wand wiring (MockWand/lib/hubtype.py "wand").
I2C_SDA = 22
I2C_SCL = 23
I2C_FREQ = 100_000     # shipped value; the matrix also runs 400_000
NFC_ADDR = 0x24

PAYLOAD = "jumpin.py"  # file on this wand's flash to serve


def serve_link(nfc, header, data):
    """Answer requests until the initiator releases the link. Returns request count."""
    count = 0
    while True:
        try:
            req = nfc.get_data(MAX_CHUNK + 16, timeout_ms=2000)
        except DepError as e:
            if e.status == STATUS_RELEASED:
                return count
            raise
        nfc.set_data(handle_request(req, header, data))
        count += 1
        if req[0:1] == b'D':
            return count
        time.sleep_ms(1)


def main():
    i2c = machine.SoftI2C(sda=machine.Pin(I2C_SDA), scl=machine.Pin(I2C_SCL), freq=I2C_FREQ)
    nfc = PN532Dep(i2c, NFC_ADDR)
    print("# sender PN532 fw", nfc.begin(), "i2c", I2C_FREQ)
    with open(PAYLOAD, "rb") as f:
        data = f.read()
    header = build_header(PAYLOAD, data)
    print("# serving %s (%d bytes)" % (PAYLOAD, len(data)))
    while True:
        print("# waiting as target")
        mode, _ = nfc.init_as_target()
        t0 = time.ticks_ms()
        print("# link up, mode 0x%02X" % mode)
        try:
            n = serve_link(nfc, header, data)
            print("# link done: %d requests in %d ms" % (n, time.ticks_diff(time.ticks_ms(), t0)))
        except DepError as e:
            # Logged, then back to waiting: a lifted wand is an expected bench event.
            print("# link FAILED after %d ms: %s" % (time.ticks_diff(time.ticks_ms(), t0), e))
        time.sleep_ms(1)


main()
