"""Read and discard USB stdin so Ctrl-C keeps working.

MicroPython v1.28 (esp32 port, USB-Serial-JTAG): the RX interrupt moves bytes
out of the USB FIFO only while the 259-byte stdin ring buffer has room, and
checks for Ctrl-C only on the bytes it moves (ports/esp32/usb_serial_jtag.c,
usb_serial_jtag_handle_rx). A program that never reads stdin fills that buffer
with whatever the host sends, and from then on every Ctrl-C stays in the FIFO
unseen. Reading stdin calls usb_serial_jtag_poll_rx(), which moves the waiting
bytes, so a 0x03 among them raises KeyboardInterrupt as normal.
See Bag3/Code/known_issues/2026-11-17-wand-ctrlc-stdin-full.md.

Import and create a Drainer only after the radio is up.
"""

import sys
import time
import select

PERIOD_MS = 250
MAX_BYTES = 1024   # per drain() call; the rest waits for the next call


class Drainer:
    def __init__(self, period_ms=PERIOD_MS):
        self._poll = select.poll()
        self._poll.register(sys.stdin, select.POLLIN)
        self._buf = sys.stdin.buffer
        self._byte = bytearray(1)
        self._period = period_ms
        self._last = time.ticks_ms()

    def drain(self):
        # ipoll() reuses one result tuple and readinto() fills _byte in
        # place, so after the first call nothing is allocated per byte.
        n = 0
        while n < MAX_BYTES:
            for _ev in self._poll.ipoll(0):
                break
            else:
                return
            self._buf.readinto(self._byte)
            n += 1

    def tick(self):
        """drain() at most once every period_ms. Call every loop pass."""
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last) >= self._period:
            self._last = now
            self.drain()
