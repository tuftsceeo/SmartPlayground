"""
radar_test.py -- bench-only scripts for Gate A (protocol bring-up). Not
part of the station's normal boot path -- run these interactively from
the REPL (mpremote connect ... then `import radar_test` or `mpremote run`)
while wiring up the sensor for the first time. See the top-level plan's
Gate A prompt for exactly what to run and what to report.

Each function is self-contained and constructs its own UART from
config.py, so these can be run one at a time from a fresh REPL without
needing radar_server.py or main.py to exist yet.
"""

import time
from machine import UART

import config
import ld2450


def _make_uart():
    return UART(
        config.UART_ID,
        baudrate=config.UART_BAUD,
        bits=8,
        parity=None,
        stop=1,
        tx=config.UART_TX,
        rx=config.UART_RX,
    )


def hexdump(seconds=5):
    """Gate A step 3: dump raw bytes as hex for `seconds`, unparsed. Look
    for AA FF 03 00 ... 55 CC every 30 bytes."""
    uart = _make_uart()
    deadline = time.ticks_add(time.ticks_ms(), int(seconds * 1000))
    total = 0
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        n = uart.any()
        if n:
            data = uart.read(n)
            total += len(data)
            print(" ".join("%02x" % b for b in data))
        time.sleep_ms(5)
    print("# total bytes: %d over %ss (~%.1f B/s)" % (total, seconds, total / seconds))


def frame_stats(seconds=60):
    """Gate A step 4: run the real (non-blocking) parser for `seconds` and
    report frame rate / drops / resyncs -- the evidence for whether
    256000 baud is clean on this board."""
    uart = _make_uart()
    radar = ld2450.LD2450(uart, sign_x=config.SIGN_X, sign_y=config.SIGN_Y)
    deadline = time.ticks_add(time.ticks_ms(), int(seconds * 1000))
    n_frames = 0
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        for frame in radar.poll():
            n_frames += 1
            if n_frames % 10 == 0:
                _print_targets(frame)
        time.sleep_ms(10)
    print("# --- frame_stats over %ss ---" % seconds)
    print("# frames_ok=%d  frames_dropped=%d  resyncs=%d" % (
        radar.frames_ok, radar.frames_dropped, radar.resyncs))
    print("# effective rate: %.1f frames/s (expect ~10)" % (n_frames / seconds))


def sign_check(seconds=30):
    """Gate A step 5: run continuously while walking left/right/toward/
    away in front of the sensor, printing every target every frame so the
    sign convention (SIGN_X / SIGN_Y in config.py) can be read off by eye
    against the reported direction of travel."""
    uart = _make_uart()
    radar = ld2450.LD2450(uart, sign_x=config.SIGN_X, sign_y=config.SIGN_Y)
    deadline = time.ticks_add(time.ticks_ms(), int(seconds * 1000))
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        for frame in radar.poll():
            _print_targets(frame)
        time.sleep_ms(50)


def _print_targets(targets):
    if not targets:
        print("# (no targets)")
        return
    parts = []
    for t in targets:
        parts.append("slot=%d x=%d y=%d speed=%d res=%d" % (t.i, t.x, t.y, t.speed, t.resolution))
    print("# " + " | ".join(parts))
