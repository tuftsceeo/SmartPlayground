"""
dep_sender.py -- NFC-DEP target ("broadcast device") bench script, wand A.

Waits as a DEP target and serves PAYLOAD to any initiator (dep_receiver.py)
until Ctrl-C. Needs pn532_dep.py, dep_proto.py and PAYLOAD on the wand's
flash. Run with:  mpremote run dep_sender.py

Per link it prints a summary with the target host's own latency: how long
TgGetData waited for the next request, and how long TgSetData took to
hand the reply to the PN532. The second is the part that eats into the
initiator's reply timeout (pn532_dep.TIMEOUT_CODE on wand B).
"""

import gc
import time
import machine
from binascii import hexlify

from pn532_dep import PN532Dep, DepError, STATUS_RELEASED
from dep_proto import build_header, handle_request, stats, ProtoError, MAX_CHUNK

# Mock Wand wiring (MockWand/lib/hubtype.py "wand").
I2C_SDA = 22
I2C_SCL = 23
I2C_FREQ = 100_000     # shipped value; the matrix also runs 400_000
NFC_ADDR = 0x24

PAYLOAD = "jumpin.py"  # file on this wand's flash to serve
TRACE = False          # True: one line per PN532 command and per request


def serve_link(nfc, header, data, log):
    """Answer requests until the initiator releases the link or sends 'D'.

    log collects 'get'/'set' durations (us), per-op counts and the last request.
    """
    while True:
        try:
            req = nfc.get_data(MAX_CHUNK + 16, timeout_ms=2000)
        except DepError as e:
            if e.status == STATUS_RELEASED:
                log['end'] = "released"
                return
            raise
        log['get'].append(nfc.timing['ack'] + nfc.timing['wait'] + nfc.timing['read'])
        log['last'] = hexlify(req[:6])
        op = req[0:1]
        log['ops'][op] = log['ops'].get(op, 0) + 1
        t = time.ticks_us()
        try:
            resp = handle_request(req, header, data)
        except ProtoError as e:
            print("# bad request %s: %s" % (hexlify(req), e))
            raise
        nfc.set_data(resp)
        log['set'].append(time.ticks_diff(time.ticks_us(), t))
        if TRACE:
            print("#  req %s -> %d bytes, set %d us" % (log['last'], len(resp), log['set'][-1]))
        if op == b'D':
            log['end'] = "done"
            return
        time.sleep_ms(1)


def main():
    i2c = machine.SoftI2C(sda=machine.Pin(I2C_SDA), scl=machine.Pin(I2C_SCL), freq=I2C_FREQ)
    print("# sender i2c.scan:", ["0x%02X" % a for a in i2c.scan()])
    nfc = PN532Dep(i2c, NFC_ADDR)
    nfc.trace = TRACE
    print("# sender PN532 fw", nfc.begin(), "i2c", I2C_FREQ, "mem_free", gc.mem_free())
    with open(PAYLOAD, "rb") as f:
        data = f.read()
    header = build_header(PAYLOAD, data)
    print("# serving %s (%d bytes), sha256 %s" % (PAYLOAD, len(data), hexlify(header[4:12])))
    links = 0
    while True:
        print("# waiting as target")
        mode, atr_req = nfc.init_as_target()
        links += 1
        t0 = time.ticks_ms()
        print("# link %d up, mode 0x%02X, initiator cmd %s" % (links, mode, hexlify(atr_req)))
        log = {'get': [], 'set': [], 'ops': {}, 'last': None, 'end': None}
        try:
            serve_link(nfc, header, data, log)
            print("# link %d %s in %d ms, ops %r" % (links, log['end'],
                  time.ticks_diff(time.ticks_ms(), t0), log['ops']))
        except DepError as e:
            # Logged, then back to waiting: a lifted wand is an expected bench event.
            print("# link %d FAILED after %d ms: %s" % (links, time.ticks_diff(time.ticks_ms(), t0), e))
            print("#   last request %s, ops %r, failing cmd timing %r" % (log['last'], log['ops'], e.timing))
            if e.status is None:
                nfc.abort()
        print("#   tg_get_us %s" % stats(log['get']))
        print("#   tg_set_us %s" % stats(log['set']))
        time.sleep_ms(1)


main()
