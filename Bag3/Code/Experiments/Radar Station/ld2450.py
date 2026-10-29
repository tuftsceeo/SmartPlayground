"""
ld2450.py -- MicroPython driver for the Hi-Link HLK-LD2450 24GHz mmWave
radar.

Report frame (streamed continuously at 10Hz):
  AA FF 03 00 | T1[8] | T2[8] | T3[8] | 55 CC   (30 bytes)
Each target: x[2] y[2] speed[2] resolution[2], little-endian,
sign-magnitude (MSB = sign flag over 15-bit magnitude) for x/y/speed.
All-zero 8-byte block = empty slot.

Command frame (config only):
  FD FC FB FA | len[2] | cmd_word[2] | value[...] | 04 03 02 01

Non-blocking, byte-fed state machine: feed() never blocks; poll()
resyncs on garbage. One instance per UART, no module-level state.
"""

REPORT_HEADER = b"\xaa\xff\x03\x00"
REPORT_TAIL = b"\x55\xcc"
REPORT_LEN = 30  # header(4) + 3*target(8) + tail(2)

CONFIG_HEADER = b"\xfd\xfc\xfb\xfa"
CONFIG_TAIL = b"\x04\x03\x02\x01"

CMD_ENABLE_CONFIG = b"\xff\x00"
CMD_END_CONFIG = b"\xfe\x00"
CMD_SINGLE_TARGET = b"\x80\x00"
CMD_MULTI_TARGET = b"\x90\x00"
CMD_READ_VERSION = b"\xa0\x00"

# Max unparsed bytes to buffer before dropping and resyncing.
MAX_BUFFER = 512


def _decode_signed(lo, hi):
    """Sign-magnitude int16 from 2 little-endian bytes. MSB of hi byte:
    1=positive, 0=negative, over a 15-bit magnitude. Not two's complement."""
    raw = lo | (hi << 8)
    magnitude = raw & 0x7FFF
    if raw & 0x8000:
        return magnitude
    return -magnitude


def _hex(data):
    return "".join("%02x" % b for b in data) if data else ""


def _parse_version_reply(reply):
    """reply: raw bytes from CONFIG_HEADER through CONFIG_TAIL, as
    returned by _read_config_reply(), for the 0x00A0 read-version
    command. Layout: header(4) len(2) ack_word(2) status(2)
    firmware_type(2) major(2) minor(4) tail(4) -- confirmed against the
    datasheet's own worked example (bytes 02 01 16 24 06 22 -> "V1.02.
    22062416"): each version byte is BCD -- its hex digits ARE the
    intended decimal digits -- and the 4 minor bytes print in reverse
    transmission order."""
    if not reply or len(reply) < 18:
        return {"ok": False, "raw_hex": _hex(reply)}
    status = reply[8] | (reply[9] << 8)
    if status != 0:
        return {"ok": False, "raw_hex": _hex(reply)}
    fw_type = reply[10] | (reply[11] << 8)
    major_lo, major_hi = reply[12], reply[13]
    build = "".join("%02x" % b for b in reversed(reply[14:18]))
    version = "V%x.%02x.%s" % (major_hi, major_lo, build)
    return {"ok": True, "fw_type": fw_type, "version": version, "raw_hex": _hex(reply)}


class Target:
    __slots__ = ("i", "x", "y", "speed", "resolution")

    def __init__(self, i, x, y, speed, resolution):
        self.i = i          # target slot 0..2, positional not identity
        self.x = x          # mm, +right (config.SIGN_X)
        self.y = y          # mm, +forward (config.SIGN_Y)
        self.speed = speed  # cm/s, radial (line-of-sight) only
        self.resolution = resolution  # mm, distance gate size


class LD2450:
    def __init__(self, uart, sign_x=1, sign_y=1):
        self.uart = uart
        self.sign_x = sign_x
        self.sign_y = sign_y
        self._buf = bytearray()
        self.frames_ok = 0
        self.frames_dropped = 0
        self.resyncs = 0

    def feed(self):
        """Read all waiting UART bytes into the internal buffer. Non-blocking."""
        n = self.uart.any()
        if n:
            data = self.uart.read(n)
            if data:
                self._buf.extend(data)

    def poll(self):
        """Parse buffered bytes into complete report frames. Returns a list
        of lists-of-Target, oldest first.

        Buffer trims use `buf[:] = buf[n:]`, not `del buf[:n]`: this
        MicroPython build's bytearray does not support slice deletion.
        """
        self.feed()
        frames = []
        buf = self._buf
        while True:
            start = buf.find(REPORT_HEADER)
            if start < 0:
                if len(buf) > 4:
                    buf[:] = buf[len(buf) - 3:]  # keep tail for a split header
                break
            if start > 0:
                buf[:] = buf[start:]
                self.resyncs += 1
            if len(buf) < REPORT_LEN:
                break  # frame incomplete, wait for more bytes
            frame = buf[:REPORT_LEN]
            if frame[-2:] != REPORT_TAIL:
                buf[:] = buf[1:]  # resync 1 byte forward
                self.resyncs += 1
                self.frames_dropped += 1
                continue
            buf[:] = buf[REPORT_LEN:]
            targets = self._decode_frame(frame)
            if targets is not None:
                frames.append(targets)
                self.frames_ok += 1
            else:
                self.frames_dropped += 1
        if len(buf) > MAX_BUFFER:
            buf[:] = b""
            self.resyncs += 1
        return frames

    def _decode_frame(self, frame):
        targets = []
        for i in range(3):
            off = 4 + i * 8
            tb = frame[off:off + 8]
            if tb == b"\x00\x00\x00\x00\x00\x00\x00\x00":
                continue  # empty target slot
            x = _decode_signed(tb[0], tb[1]) * self.sign_x
            y = _decode_signed(tb[2], tb[3]) * self.sign_y
            speed = _decode_signed(tb[4], tb[5])
            resolution = tb[6] | (tb[7] << 8)
            targets.append(Target(i, x, y, speed, resolution))
        return targets

    def _send_config_cmd(self, cmd_word, value=b""):
        length = len(cmd_word) + len(value)
        frame = CONFIG_HEADER + bytes([length & 0xFF, (length >> 8) & 0xFF])
        frame += cmd_word + value + CONFIG_TAIL
        self.uart.write(frame)

    def _read_config_reply(self, timeout_ms=500):
        """Blocking-with-timeout read for a config-frame reply. Setup only."""
        import time
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
        buf = bytearray()
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            n = self.uart.any()
            if n:
                buf.extend(self.uart.read(n))
                i = buf.find(CONFIG_TAIL)
                if i >= 0:
                    return bytes(buf[:i + len(CONFIG_TAIL)])
            time.sleep_ms(5)
        return None

    def enable_config(self):
        self._send_config_cmd(CMD_ENABLE_CONFIG, b"\x01\x00")
        return self._read_config_reply()

    def end_config(self):
        self._send_config_cmd(CMD_END_CONFIG)
        return self._read_config_reply()

    def set_multi_target(self):
        self._send_config_cmd(CMD_MULTI_TARGET)
        return self._read_config_reply()

    def set_single_target(self):
        self._send_config_cmd(CMD_SINGLE_TARGET)
        return self._read_config_reply()

    def read_version(self):
        """Query the LD2450's own onboard firmware version (distinct from
        the ESP32's MicroPython version). Returns a dict; see
        _parse_version_reply() for the layout, confirmed against the
        datasheet's own worked example."""
        self.enable_config()
        self._send_config_cmd(CMD_READ_VERSION)
        reply = self._read_config_reply()
        self.end_config()
        return _parse_version_reply(reply)
