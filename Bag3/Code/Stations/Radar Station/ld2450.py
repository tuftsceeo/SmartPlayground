"""
ld2450.py -- MicroPython driver for the Hi-Link HLK-LD2450 24GHz mmWave
radar. No official MicroPython library exists for this sensor (see the
top-level plan's prior-art table); this is a from-scratch, non-blocking
implementation informed by reading marconicivitavecchia/esp32-radar and
csRon/HLK-LD2450 (both MIT), not a port of either.

Protocol (see the plan for the full derivation):

  Report frame (streamed continuously at 10Hz, no request needed):
    AA FF 03 00 | T1[8] | T2[8] | T3[8] | 55 CC        (30 bytes)
  Each target is 8 bytes: x[2] y[2] speed[2] resolution[2], little-endian,
  sign-magnitude (MSB = sign flag over a 15-bit magnitude) for x/y/speed.
  An all-zero 8-byte block means that target slot is empty.

  Command frame (only needed for configuration, not for reading data):
    FD FC FB FA | len[2] | cmd_word[2] | value[...] | 04 03 02 01

Design note: both reference implementations block on read_until() /
read(n). This station's main loop must ALSO service a JSON link to the
browser (see json_link.py), so this driver is a byte-fed, non-blocking
state machine instead: feed() never blocks, and resyncs on garbage so a
single dropped byte at 256000 baud doesn't desynchronize the stream
permanently. Deliberately no module-level state -- one LD2450 instance
per UART, so a second sensor (out of scope for this plan; see priority 4)
is just a second instance.
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

# generous upper bound on how much garbage to accumulate before we give up
# looking for a header and drop the buffer -- guards against a wired-but-
# silent sensor filling memory with buffered noise.
MAX_BUFFER = 512


def _decode_signed(lo, hi):
    """Decode one LD2450 sign-magnitude int16 from its two bytes
    (little-endian). MSB of the high byte is a sign flag (1 = positive,
    per the datasheet's convention) over a 15-bit magnitude in the
    remaining bits -- NOT two's complement."""
    raw = lo | (hi << 8)
    magnitude = raw & 0x7FFF
    if raw & 0x8000:
        return magnitude
    return -magnitude


class Target:
    __slots__ = ("i", "x", "y", "speed", "resolution")

    def __init__(self, i, x, y, speed, resolution):
        self.i = i          # target slot index 0..2 (positional, not an identity)
        self.x = x          # mm, +right (see config.SIGN_X to flip)
        self.y = y          # mm, +forward/away from sensor (see config.SIGN_Y)
        self.speed = speed  # cm/s, radial (line-of-sight) only -- see plan
        self.resolution = resolution  # mm, distance resolution/gate size


class LD2450:
    def __init__(self, uart, sign_x=1, sign_y=1):
        self.uart = uart
        self.sign_x = sign_x
        self.sign_y = sign_y
        self._buf = bytearray()
        self.frames_ok = 0
        self.frames_dropped = 0
        self.resyncs = 0

    # ---- data path (non-blocking) -------------------------------------
    def feed(self):
        """Pull whatever bytes are currently waiting on the UART into the
        internal buffer. Never blocks. Call this every loop iteration."""
        n = self.uart.any()
        if n:
            data = self.uart.read(n)
            if data:
                self._buf.extend(data)

    def poll(self):
        """Parse as many complete report frames as are currently buffered.
        Returns a list of lists-of-Target (one list per frame, oldest
        first; usually 0 or 1 frames per call at normal poll rates).

        Note: buffer trims below use `buf[:] = buf[n:]` slice assignment,
        not `del buf[:n]` -- confirmed on-device (Gate A) that this
        MicroPython build's bytearray does not support slice deletion
        (`del ba[:n]` raises TypeError: 'bytearray' object doesn't
        support item deletion), even though slice assignment works fine.
        """
        self.feed()
        frames = []
        buf = self._buf
        while True:
            start = buf.find(REPORT_HEADER)
            if start < 0:
                # no header in the buffer at all -- keep only enough tail
                # bytes to catch a header that's split across two reads
                if len(buf) > 4:
                    buf[:] = buf[len(buf) - 3:]
                break
            if start > 0:
                # garbage before the header -- drop it and count a resync
                buf[:] = buf[start:]
                self.resyncs += 1
            if len(buf) < REPORT_LEN:
                break  # header seen, but the rest of the frame hasn't arrived yet
            frame = buf[:REPORT_LEN]
            if frame[-2:] != REPORT_TAIL:
                # header matched but tail didn't -- treat header byte as
                # garbage and resync one byte forward rather than
                # discarding the whole window, so we recover fast
                buf[:] = buf[1:]
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
            # sensor is producing bytes we can't make sense of -- bail out
            # rather than growing unbounded
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

    # ---- config path (blocking with timeout -- startup only) ---------
    def _send_config_cmd(self, cmd_word, value=b""):
        length = len(cmd_word) + len(value)
        frame = CONFIG_HEADER + bytes([length & 0xFF, (length >> 8) & 0xFF])
        frame += cmd_word + value + CONFIG_TAIL
        self.uart.write(frame)

    def _read_config_reply(self, timeout_ms=500):
        """Blocking-with-timeout read for a config-frame reply. Only used
        during setup (enable_config/end_config/set_mode), never in the
        streaming loop -- so blocking briefly here doesn't starve the
        browser link."""
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
