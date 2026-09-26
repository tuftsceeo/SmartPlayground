"""
dep_receiver.py -- NFC-DEP initiator bench script, wand B.

Polls for a DEP target (dep_sender.py), pulls its file in CHUNK-byte pieces,
verifies the sha256, writes /dep_rx.bin and prints timing. RUNS transfers,
then exits. Needs pn532_dep.py and dep_proto.py on the wand's flash.
Run with:  mpremote run dep_receiver.py
"""

import time
import machine

import pn532_dep
from pn532_dep import PN532Dep, DepError, BAUD_106, BAUD_212, BAUD_424
from dep_proto import pull, ProtoError

# Mock Wand wiring (MockWand/lib/hubtype.py "wand").
I2C_SDA = 22
I2C_SCL = 23
I2C_FREQ = 100_000     # shipped value; the matrix also runs 400_000
NFC_ADDR = 0x24

BAUD = BAUD_106        # BAUD_106 / BAUD_212 / BAUD_424
CHUNK = 240            # 64 / 128 / 192 / 240
RUNS = 3
OUT = "/dep_rx.bin"

_BAUD_KBPS = {BAUD_106: 106, BAUD_212: 212, BAUD_424: 424}


def one_run(nfc):
    """Wait for a target, pull once, print a result line. Returns True on verified transfer."""
    t_poll = time.ticks_ms()
    while nfc.jump_for_dep(BAUD) is None:
        time.sleep_ms(1)
    t_link = time.ticks_ms()
    rtts = []
    last = [time.ticks_us()]

    def exchange(req, max_resp):
        return nfc.exchange(req, max_resp)

    got = [0]

    def on_chunk(off, n):
        got[0] = off
        now = time.ticks_us()
        rtts.append(time.ticks_diff(now, last[0]))
        last[0] = now

    try:
        name, data = pull(exchange, CHUNK, on_chunk)
    except (DepError, ProtoError) as e:
        print("RESULT FAIL err=%r after_ms=%d bytes_received=%d"
              % (str(e), time.ticks_diff(time.ticks_ms(), t_link), got[0]))
        return False
    t_done = time.ticks_ms()
    nfc.release()
    with open(OUT, "wb") as f:
        f.write(data)
    xfer_ms = time.ticks_diff(t_done, t_link)
    rtts.sort()
    print("RESULT OK name=%s bytes=%d i2c=%d baud=%d chunk=%d timeout_code=0x%02X "
          "poll_ms=%d xfer_ms=%d Bps=%d rtt_us_min=%d med=%d max=%d"
          % (name, len(data), I2C_FREQ, _BAUD_KBPS[BAUD], CHUNK, pn532_dep.TIMEOUT_CODE,
             time.ticks_diff(t_link, t_poll), xfer_ms, len(data) * 1000 // max(xfer_ms, 1),
             rtts[0], rtts[len(rtts) // 2], rtts[-1]))
    return True


def main():
    i2c = machine.SoftI2C(sda=machine.Pin(I2C_SDA), scl=machine.Pin(I2C_SCL), freq=I2C_FREQ)
    nfc = PN532Dep(i2c, NFC_ADDR)
    print("# receiver PN532 fw", nfc.begin(), "i2c", I2C_FREQ)
    nfc.configure_initiator()
    ok = 0
    for i in range(RUNS):
        print("# run %d/%d: bring wands together" % (i + 1, RUNS))
        if one_run(nfc):
            ok += 1
        print("# separate wands")
        time.sleep_ms(2000)
    print("SUMMARY ok=%d/%d" % (ok, RUNS))


main()
