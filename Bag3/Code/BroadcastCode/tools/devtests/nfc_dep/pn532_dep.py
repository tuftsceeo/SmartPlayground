"""
pn532_dep.py -- bench-only PN532 driver for NFC-DEP (peer-to-peer) over I2C.

Standalone: not imported by MockWand firmware. Framing follows
MockWand/lib/pn532.py, with two differences that DEP needs:

  * responses are read at a caller-sized length (MockWand's driver reads a
    fixed 64 bytes, which caps a response at ~57 data bytes);
  * the ready poll sleeps 1 ms instead of 10 ms, and there is no fixed 5 ms
    sleep after each command.

Command references: NXP UM0701-02 (PN532 User Manual), sections 7.3.x/7.3.14+.
Errors raise DepError; nothing here returns None for a failure except
jump_for_dep() for the expected "no target in field" status.
"""

import time
from binascii import hexlify

_TFI_HOST2PN532 = 0xD4
_TFI_PN5322HOST = 0xD5

CMD_GETFIRMWAREVERSION = 0x02
CMD_SAMCONFIGURATION = 0x14
CMD_RFCONFIGURATION = 0x32
CMD_INDATAEXCHANGE = 0x40
CMD_INJUMPFORDEP = 0x56
CMD_INRELEASE = 0x52
CMD_TGINITASTARGET = 0x8C
CMD_TGGETDATA = 0x86
CMD_TGSETDATA = 0x8E

BAUD_106 = 0x00
BAUD_212 = 0x01
BAUD_424 = 0x02

# Normal information frame: LEN counts TFI + command code + data, max 255.
# InDataExchange responses spend 3 of those on TFI, code and status.
MAX_FRAME_DATA = 252

# PN532 status codes seen in DEP (UM0701 table 13).
STATUS_TIMEOUT = 0x01
STATUS_RELEASED = 0x29

# RFConfiguration item 0x02 timeout codes: 0x00 = none, n = 100 us * 2^(n-1).
# 0x0B = 102.4 ms, 0x0C = 204.8 ms, 0x0D = 409.6 ms, 0x0E = 819.2 ms.
# This bounds how long the initiator's PN532 waits for the target's reply,
# which includes the target host's I2C round trip. Raise it if InDataExchange
# returns status 0x01 mid-transfer.
TIMEOUT_CODE = 0x0B
ATR_TIMEOUT_CODE = 0x0B

# Target identity presented to the initiator. SEL_RES 0x40 marks NFC-DEP support.
_MIFARE_PARAMS = bytes([0x04, 0x00, 0x12, 0x34, 0x56, 0x40])
_FELICA_PARAMS = bytes([0x01, 0xFE, 0xA2, 0xA3, 0xA4, 0xA5, 0xA6, 0xA7,
                        0xC0, 0xC1, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7,
                        0xFF, 0xFF])
_NFCID3T = bytes([0xAA, 0x99, 0x88, 0x77, 0x66, 0x55, 0x44, 0x33, 0x22, 0x11])
TG_MODE_DEP_ONLY = 0x02

# PN532 error codes (UM0701 table 13), for readable error messages.
STATUS_NAMES = {
    0x01: "timeout", 0x02: "CRC error", 0x03: "parity error",
    0x04: "bad anticollision bit count", 0x05: "framing error",
    0x06: "abnormal bit collision", 0x07: "buffer too small",
    0x09: "RF buffer overflow", 0x0A: "RF field not on in time",
    0x0B: "RF protocol error", 0x0D: "overheat", 0x0E: "internal buffer overflow",
    0x10: "invalid parameter", 0x12: "DEP unsupported command",
    0x13: "DEP bad frame format", 0x25: "DEP invalid device state",
    0x26: "operation not allowed", 0x27: "command not valid in this state",
    0x29: "released by initiator", 0x2A: "card ID mismatch",
    0x2B: "card disappeared", 0x2C: "NFCID3 mismatch", 0x2D: "over-current",
    0x2E: "DEP NAD missing",
}

_ACK_FRAME = b'\x00\x00\xFF\x00\xFF\x00'

# Polling request required as PassiveInitiatorData at 212/424 kbps.
_FELICA_POLL = bytes([0x00, 0xFF, 0xFF, 0x00, 0x00])


def status_str(status):
    """Return e.g. '0x01 (timeout)' for a PN532 status byte."""
    return "0x%02X (%s)" % (status, STATUS_NAMES.get(status, "unknown"))


class DepError(Exception):
    """PN532 protocol failure.

    .status is the PN532 status byte, or None for a host-side failure (I2C,
    framing, timeout waiting for the ready bit). .timing is the command's
    phase timing dict at the point of failure (see PN532Dep.timing).
    """

    def __init__(self, msg, status=None):
        if status is not None:
            msg = "%s status %s" % (msg, status_str(status))
        super().__init__(msg)
        self.status = status
        self.timing = None


class PN532Dep:
    """PN532 over I2C with DEP initiator and target commands."""

    def __init__(self, i2c, addr=0x24):
        self.i2c = i2c
        self.addr = addr
        self.tg = 1
        # Set True to print one line per command (code, sizes, phase timings).
        self.trace = False
        # Phase timings of the most recent command, in microseconds:
        #   write  -- I2C write of the command frame
        #   ack    -- wait for ready + ACK read
        #   wait   -- wait for ready before the response (PN532 + RF time)
        #   read   -- I2C read of the response frame (bus time)
        # plus 'cmd', 'tx' (command frame bytes) and 'rx' (response data bytes).
        self.timing = {}
        self.polls = 0      # ready-bit polls in the last _wait_ready()

    # ─── Framing ───

    def _wait_ready(self, timeout_ms):
        """Poll the I2C status byte every 1 ms; timeout_ms=None waits forever."""
        start = time.ticks_ms()
        last_err = None
        self.polls = 0
        while True:
            self.polls += 1
            try:
                if self.i2c.readfrom(self.addr, 1)[0] == 0x01:
                    return
            except OSError as e:
                # The PN532 NACKs its address while busy on some boards.
                last_err = e
            if timeout_ms is not None and time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
                raise DepError("ready timeout after %d ms, %d polls (last I2C error: %r)"
                               % (timeout_ms, self.polls, last_err))
            time.sleep_ms(1)

    def _write_command(self, cmd, params):
        payload = bytes([_TFI_HOST2PN532, cmd]) + bytes(params)
        n = len(payload)
        if n > 255:
            raise DepError("command frame too long: %d" % n)
        frame = bytearray([0x00, 0x00, 0xFF, n, (~n + 1) & 0xFF])
        frame.extend(payload)
        frame.append((~sum(payload) + 1) & 0xFF)
        frame.append(0x00)
        self.i2c.writeto(self.addr, frame)

    def _read_ack(self, timeout_ms):
        self._wait_ready(timeout_ms)
        raw = bytes(self.i2c.readfrom(self.addr, 7))
        if raw[1:7] != b'\x00\x00\xFF\x00\xFF\x00':
            raise DepError("bad ACK: %s" % hexlify(raw))

    def _read_response(self, cmd, max_data):
        """Read one response frame; max_data sizes the I2C read. Caller has waited for ready."""
        # status(1) + preamble/start(3) + LEN/LCS(2) + TFI/code(2) + data + DCS/post(2)
        raw = bytes(self.i2c.readfrom(self.addr, max_data + 10))
        i = raw.find(b'\x00\xFF', 1)
        if i < 0 or i + 4 > len(raw):
            raise DepError("no frame start: %s" % hexlify(raw[:16]))
        n = raw[i + 2]
        if (n + raw[i + 3]) & 0xFF:
            raise DepError("bad LCS: %s" % hexlify(raw[:i + 4]))
        body = raw[i + 4:i + 4 + n]
        if len(body) < n:
            raise DepError("frame LEN %d exceeds read size (raise max_data above %d)" % (n, max_data))
        if (sum(body) + raw[i + 4 + n]) & 0xFF:
            raise DepError("bad DCS, LEN %d: %s" % (n, hexlify(raw[:i + 6 + n])))
        if body[0] != _TFI_PN5322HOST or body[1] != cmd + 1:
            raise DepError("unexpected response %s to cmd 0x%02X" % (hexlify(body[:2]), cmd))
        return body[2:]

    def command(self, cmd, params=b'', max_data=32, timeout_ms=1000):
        """Send a command and return its response data (after TFI/code).

        Records phase timings in self.timing; on failure the timings so far
        are attached to the raised DepError as .timing.
        """
        tm = {'cmd': cmd, 'tx': len(params) + 2}
        self.timing = tm
        t = time.ticks_us()
        try:
            self._write_command(cmd, params)
            t1 = time.ticks_us()
            tm['write'] = time.ticks_diff(t1, t)
            self._read_ack(timeout_ms)
            t2 = time.ticks_us()
            tm['ack'] = time.ticks_diff(t2, t1)
            self._wait_ready(timeout_ms)
            t3 = time.ticks_us()
            tm['wait'] = time.ticks_diff(t3, t2)
            tm['polls'] = self.polls
            resp = self._read_response(cmd, max_data)
            tm['read'] = time.ticks_diff(time.ticks_us(), t3)
        except DepError as e:
            e.timing = tm
            if self.trace:
                print("#  cmd 0x%02X FAILED %s timing=%r" % (cmd, e, tm))
            raise
        except OSError as e:
            err = DepError("I2C OSError %r during cmd 0x%02X" % (e, cmd))
            err.timing = tm
            if self.trace:
                print("#  cmd 0x%02X FAILED %s timing=%r" % (cmd, err, tm))
            raise err
        tm['rx'] = len(resp)
        if self.trace:
            print("#  cmd 0x%02X tx=%d rx=%d write=%d ack=%d wait=%d(polls %d) read=%d us"
                  % (cmd, tm['tx'], tm['rx'], tm['write'], tm['ack'], tm['wait'],
                     tm['polls'], tm['read']))
        return resp

    def _status_error(self, what, status):
        """DepError for a non-zero PN532 status, carrying this command's timing."""
        err = DepError(what, status)
        err.timing = self.timing
        return err

    def abort(self):
        """Cancel a pending command (host ACK frame, UM0701 6.2.1.3).

        Needed after a host-side ready timeout: the PN532 is still executing
        the command and would otherwise reject or garble the next one.
        """
        self.i2c.writeto(self.addr, _ACK_FRAME)
        time.sleep_ms(1)
        if self.trace:
            print("#  abort sent")

    # ─── Setup ───

    def begin(self):
        """Return (ic, ver, rev) and put the SAM in normal mode."""
        fw = self.command(CMD_GETFIRMWAREVERSION)
        self.command(CMD_SAMCONFIGURATION, b'\x01\x00\x00')
        return fw[0], fw[1], fw[2]

    def configure_initiator(self, passive_retries=0x02):
        """Bound InJumpForDEP's blocking and set the reply timeout (TIMEOUT_CODE)."""
        # Item 0x05 MaxRetries: MxRtyATR, MxRtyPSL, MxRtyPassiveActivation.
        self.command(CMD_RFCONFIGURATION, bytes([0x05, 0x01, 0x01, passive_retries]))
        # Item 0x02 timings: RFU, ATR_RES timeout, retry timeout.
        self.command(CMD_RFCONFIGURATION, bytes([0x02, 0x00, ATR_TIMEOUT_CODE, TIMEOUT_CODE]))

    # ─── Initiator ───

    def jump_for_dep(self, baud=BAUD_106, timeout_ms=1000):
        """Activate a passive DEP target. Returns the ATR_RES info bytes, or None if none in field."""
        if baud == BAUD_106:
            params = bytes([0x00, baud, 0x00])
        else:
            params = bytes([0x00, baud, 0x01]) + _FELICA_POLL
        resp = self.command(CMD_INJUMPFORDEP, params, max_data=64, timeout_ms=timeout_ms)
        status = resp[0] & 0x3F
        if status == STATUS_TIMEOUT:
            return None
        if status:
            raise self._status_error("InJumpForDEP", status)
        self.tg = resp[1]
        return resp[2:]

    def exchange(self, data, max_resp, timeout_ms=1000):
        """Send data to the target and return its reply."""
        if len(data) > MAX_FRAME_DATA:
            raise DepError("request too long: %d" % len(data))
        resp = self.command(CMD_INDATAEXCHANGE, bytes([self.tg]) + bytes(data),
                            max_data=max_resp + 1, timeout_ms=timeout_ms)
        status = resp[0]
        if status & 0x40:
            raise DepError("chained (MI) reply, raw status 0x%02X, not supported; lower CHUNK" % status)
        if status & 0x3F:
            raise self._status_error("InDataExchange", status & 0x3F)
        return resp[1:]

    def release(self):
        """Release the current target so the next jump_for_dep() starts a fresh link."""
        status = self.command(CMD_INRELEASE, bytes([self.tg]))[0] & 0x3F
        if status:
            raise self._status_error("InRelease", status)

    # ─── Target ───

    def init_as_target(self, timeout_ms=None):
        """Wait for an initiator to activate this PN532. Returns (mode, initiator command bytes)."""
        params = (bytes([TG_MODE_DEP_ONLY]) + _MIFARE_PARAMS + _FELICA_PARAMS
                  + _NFCID3T + b'\x00' + b'\x00')
        resp = self.command(CMD_TGINITASTARGET, params, max_data=64, timeout_ms=timeout_ms)
        return resp[0], resp[1:]

    def get_data(self, max_data, timeout_ms=1000):
        """Return the next initiator frame. Raises DepError(status=0x29) on release."""
        resp = self.command(CMD_TGGETDATA, b'', max_data=max_data + 1, timeout_ms=timeout_ms)
        status = resp[0] & 0x3F
        if status:
            raise self._status_error("TgGetData", status)
        return resp[1:]

    def set_data(self, data, timeout_ms=1000):
        """Send the reply to the frame last read with get_data()."""
        if len(data) > MAX_FRAME_DATA + 1:
            raise DepError("reply too long: %d" % len(data))
        resp = self.command(CMD_TGSETDATA, data, timeout_ms=timeout_ms)
        status = resp[0] & 0x3F
        if status:
            raise self._status_error("TgSetData", status)
