"""
dep_receiver.py -- NFC-DEP initiator bench script, wand B.

Polls for a DEP target (dep_sender.py), pulls its file in CHUNK-byte pieces,
verifies the sha256, writes /dep_rx.bin and prints timing. RUNS transfers,
then exits. Needs pn532_dep.py and dep_proto.py on the wand's flash.
Run with:  mpremote run dep_receiver.py

Each run prints one RESULT line, followed by '#' detail lines that split
every chunk exchange into PN532 phases (see PN532Dep.timing):
  wait -- ready-bit wait before the response: RF time plus the target's reply
  read -- I2C read of the response frame (bus time on this wand)
If 'read' dominates, the I2C bus is the bottleneck; if 'wait' does, it is the
air link or the target host.
"""

import gc
import time
import machine
from binascii import hexlify

import pn532_dep
from pn532_dep import PN532Dep, DepError, BAUD_106, BAUD_212, BAUD_424
from dep_proto import pull, stats, ProtoError

# Mock Wand wiring (MockWand/lib/hubtype.py "wand").
I2C_SDA = 22
I2C_SCL = 23
I2C_FREQ = 100_000     # shipped value; the matrix also runs 400_000
NFC_ADDR = 0x24

BAUD = BAUD_106        # BAUD_106 / BAUD_212 / BAUD_424
CHUNK = 240            # 64 / 128 / 192 / 240
RUNS = 3
OUT = "/dep_rx.bin"
TRACE = False          # True: one line per PN532 command

_BAUD_KBPS = {BAUD_106: 106, BAUD_212: 212, BAUD_424: 424}


def wait_for_link(nfc):
    """Poll InJumpForDEP until a target answers. Returns (poll_ms, attempts, ATR_RES bytes)."""
    t0 = time.ticks_ms()
    attempts = 0
    errors = 0
    while True:
        attempts += 1
        try:
            atr = nfc.jump_for_dep(BAUD)
        except DepError as e:
            # A partial activation (wand at the edge of range) shows up here.
            errors += 1
            print("#  poll %d error: %s timing=%r" % (attempts, e, e.timing))
            if e.status is None:
                nfc.abort()
            atr = None
        if atr is not None:
            if errors:
                print("#  link after %d poll errors" % errors)
            return time.ticks_diff(time.ticks_ms(), t0), attempts, atr
        time.sleep_ms(1)


def one_run(nfc):
    """Wait for a target, pull once, print a RESULT line. Returns True on verified transfer."""
    poll_ms, attempts, atr = wait_for_link(nfc)
    t_link = time.ticks_ms()
    # ATR_RES: NFCID3t(10) DIDt BSt BRt TO PPt [Gt]; TO sets the target's response waiting time.
    print("# link up after %d ms / %d polls, tg=%d ATR_RES %s (TO=0x%02X)"
          % (poll_ms, attempts, nfc.tg, hexlify(atr), atr[13] & 0x0F if len(atr) > 13 else 0xFF))
    rtts, waits, reads, polls = [], [], [], []
    state = {'op': None, 'off': 0, 'hdr_us': 0}

    def exchange(req, max_resp):
        state['op'] = req[0:1]
        t = time.ticks_us()
        resp = nfc.exchange(req, max_resp)
        dt = time.ticks_diff(time.ticks_us(), t)
        tm = nfc.timing
        if state['op'] == b'C':
            rtts.append(dt)
            waits.append(tm['wait'])
            reads.append(tm['read'])
            polls.append(tm['polls'])
        elif state['op'] == b'H':
            state['hdr_us'] = dt
        return resp

    def on_chunk(off, n):
        state['off'] = off

    try:
        name, data = pull(exchange, CHUNK, on_chunk)
    except (DepError, ProtoError) as e:
        print("RESULT FAIL err=%r after_ms=%d bytes_received=%d op=%r chunks_ok=%d"
              % (str(e), time.ticks_diff(time.ticks_ms(), t_link), state['off'], state['op'], len(rtts)))
        print("#   failing cmd timing %r" % getattr(e, 'timing', None))
        print("#   rtt_us %s" % stats(rtts))
        if getattr(e, 'status', 0) is None:
            nfc.abort()
        try:
            nfc.release()
        except DepError as re:
            print("#   release after failure: %s" % re)
        return False
    t_done = time.ticks_ms()
    nfc.release()
    with open(OUT, "wb") as f:
        f.write(data)
    xfer_ms = time.ticks_diff(t_done, t_link)
    rtts_sorted = sorted(rtts)
    print("RESULT OK name=%s bytes=%d i2c=%d baud=%d chunk=%d timeout_code=0x%02X "
          "poll_ms=%d xfer_ms=%d Bps=%d rtt_us_min=%d med=%d max=%d"
          % (name, len(data), I2C_FREQ, _BAUD_KBPS[BAUD], CHUNK, pn532_dep.TIMEOUT_CODE,
             poll_ms, xfer_ms, len(data) * 1000 // max(xfer_ms, 1),
             rtts_sorted[0], rtts_sorted[len(rtts_sorted) // 2], rtts_sorted[-1]))
    print("#   header_us %d" % state['hdr_us'])
    print("#   wait_us %s" % stats(waits))
    print("#   read_us %s" % stats(reads))
    print("#   ready_polls %s" % stats(polls))
    return True


def main():
    i2c = machine.SoftI2C(sda=machine.Pin(I2C_SDA), scl=machine.Pin(I2C_SCL), freq=I2C_FREQ)
    print("# receiver i2c.scan:", ["0x%02X" % a for a in i2c.scan()])
    nfc = PN532Dep(i2c, NFC_ADDR)
    nfc.trace = TRACE
    print("# receiver PN532 fw", nfc.begin(), "i2c", I2C_FREQ, "mem_free", gc.mem_free())
    nfc.configure_initiator()
    print("# config baud=%d chunk=%d runs=%d timeout_code=0x%02X atr_timeout_code=0x%02X"
          % (_BAUD_KBPS[BAUD], CHUNK, RUNS, pn532_dep.TIMEOUT_CODE, pn532_dep.ATR_TIMEOUT_CODE))
    ok = 0
    for i in range(RUNS):
        print("# run %d/%d: bring wands together" % (i + 1, RUNS))
        if one_run(nfc):
            ok += 1
        print("# separate wands")
        time.sleep_ms(2000)
    print("SUMMARY ok=%d/%d" % (ok, RUNS))


main()
