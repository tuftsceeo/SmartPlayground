"""
PN532 NFC Reader Driver — MicroPython (I2C)
============================================
Supports MIFARE Classic auth/read and NTAG/Ultralight page reads.

Usage:
    from pn532 import PN532
    import machine

    i2c = machine.SoftI2C(sda=machine.Pin(22), scl=machine.Pin(23), freq=100_000)
    nfc = PN532(i2c)
    nfc.begin()

    tag = nfc.read_passive_target()
    if tag:
        print(tag['uid_hex'], tag['sak'])
"""

import time

# Frame markers
_TFI_HOST2PN532 = 0xD4
_TFI_PN5322HOST = 0xD5

# Commands
CMD_GETFIRMWAREVERSION  = 0x02
CMD_SAMCONFIGURATION    = 0x14
CMD_INLISTPASSIVETARGET = 0x4A
CMD_INDATAEXCHANGE      = 0x40

# MIFARE commands
MIFARE_AUTH_A = 0x60
MIFARE_AUTH_B = 0x61
MIFARE_READ   = 0x30


class PN532:
    def __init__(self, i2c, addr=0x24):
        self.i2c = i2c
        self.addr = addr

    # ─── Low-level I2C protocol ───

    def _wait_ready(self, timeout=1000):
        start = time.ticks_ms()
        while True:
            try:
                status = self.i2c.readfrom(self.addr, 1)
                if status[0] == 0x01:
                    return True
            except OSError:
                pass
            if time.ticks_diff(time.ticks_ms(), start) > timeout:
                return False
            time.sleep_ms(10)

    def _write_command(self, cmd, params=b''):
        payload = bytes([_TFI_HOST2PN532, cmd]) + bytes(params)
        length = len(payload)
        lcs = (~length + 1) & 0xFF
        frame = bytearray([0x00, 0x00, 0xFF, length, lcs])
        frame.extend(payload)
        frame.append((~sum(payload) + 1) & 0xFF)
        frame.append(0x00)
        self.i2c.writeto(self.addr, frame)

    def _read_ack(self, timeout=500):
        if not self._wait_ready(timeout):
            raise RuntimeError("ACK timeout")
        ack = self.i2c.readfrom(self.addr, 7)
        ack_pattern = bytes([0x00, 0x00, 0xFF, 0x00, 0xFF, 0x00])
        if ack_pattern in bytes(ack):
            return True
        raw = bytes(ack)
        for i in range(len(raw) - 3):
            if raw[i] == 0x00 and raw[i+1] == 0xFF and raw[i+2] == 0x00 and raw[i+3] == 0xFF:
                return True
        raise RuntimeError("Bad ACK")

    def _read_response(self, timeout=1000):
        if not self._wait_ready(timeout):
            raise RuntimeError("Response timeout")
        buf = self.i2c.readfrom(self.addr, 64)
        raw = bytes(buf)
        offset = -1
        for i in range(len(raw) - 4):
            if raw[i] == 0x00 and raw[i+1] == 0xFF:
                if i+2 < len(raw) and raw[i+2] != 0x00:
                    offset = i; break
                elif (i+2 < len(raw) and raw[i+2] == 0x00
                      and i+3 < len(raw) and raw[i+3] != 0xFF):
                    offset = i; break
        if offset < 0:
            raise RuntimeError("No frame start")
        frame_len = raw[offset + 2]
        data_start = offset + 4
        data = raw[data_start:data_start + frame_len]
        if len(data) < frame_len:
            raise RuntimeError("Short response")
        return data

    def _send_command(self, cmd, params=b'', timeout=1000):
        self._write_command(cmd, params)
        time.sleep_ms(5)
        self._read_ack(timeout=timeout)
        resp = self._read_response(timeout=timeout)
        if len(resp) < 2 or resp[0] != _TFI_PN5322HOST or resp[1] != (cmd + 1):
            raise RuntimeError("Bad response")
        return resp[2:]

    # ─── High-level commands ───

    def begin(self):
        """Initialize PN532: get firmware version and configure SAM."""
        fw = self._send_command(CMD_GETFIRMWAREVERSION)
        self.fw_version = (fw[0], fw[1], fw[2])
        self._send_command(CMD_SAMCONFIGURATION, b'\x01\x00\x00')
        return self.fw_version

    def read_passive_target(self, baud=0x00, timeout=500):
        """
        Detect an ISO14443A tag.

        Returns dict with uid, uid_hex, atqa, sak, or None if no tag found.
        """
        try:
            resp = self._send_command(
                CMD_INLISTPASSIVETARGET, bytes([0x01, baud]), timeout=timeout
            )
        except RuntimeError:
            return None
        if len(resp) < 6 or resp[0] == 0:
            return None
        uid_len = resp[5]
        uid = resp[6:6 + uid_len]
        return {
            'uid': uid,
            'uid_hex': ':'.join('%02X' % b for b in uid),
            'uid_len': uid_len,
            'atqa': (resp[2] << 8) | resp[3],
            'sak': resp[4],
        }

    def mifare_auth_block(self, uid, block, key=b'\xFF\xFF\xFF\xFF\xFF\xFF', key_type=MIFARE_AUTH_A):
        """Authenticate a MIFARE Classic block. Returns True on success."""
        params = bytes([0x01, key_type, block]) + key + uid[:4]
        try:
            resp = self._send_command(CMD_INDATAEXCHANGE, params, timeout=1000)
            return (resp[0] & 0x3F) == 0x00
        except Exception:
            return False

    def mifare_read_block(self, block):
        """Read 16 bytes from an authenticated MIFARE Classic block."""
        params = bytes([0x01, MIFARE_READ, block])
        resp = self._send_command(CMD_INDATAEXCHANGE, params, timeout=1000)
        if (resp[0] & 0x3F) != 0x00:
            raise RuntimeError("Read err 0x%02X" % (resp[0] & 0x3F))
        return resp[1:17]

    def ntag_read_page(self, page):
        """Read 4 bytes from an NTAG/Ultralight page."""
        params = bytes([0x01, MIFARE_READ, page])
        resp = self._send_command(CMD_INDATAEXCHANGE, params, timeout=1000)
        if (resp[0] & 0x3F) != 0x00:
            raise RuntimeError("Read err 0x%02X" % (resp[0] & 0x3F))
        return resp[1:5]