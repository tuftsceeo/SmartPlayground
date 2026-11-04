"""CPython check of modem/main.py's per-board pin/ring selection.

Extracts and execs just the board-detection block (up to the RING_SLOTS
if/else), under a faked os.uname().machine, so this doesn't need the full
test_sim.py radio/UART harness. Two boards: the S3 (unchanged defaults)
and the C6 (new pins, halved ring, antenna GPIOs driven).

Run: python tests/test_board_select.py
"""

import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.path.join(HERE, "..", "modem", "main.py")


def _extract(src, start_marker, end_marker):
    i = src.index(start_marker)
    j = src.index(end_marker, i)
    return src[i:j]


def _run_for_machine(machine_str, external_antenna):
    with open(SRC_PATH) as f:
        src = f.read()
    # Two disjoint slices: the board-detection functions, and the UART
    # pin / RING_SLOTS selection further down. Skips the radio bring-up
    # lines between them, which need real network/espnow modules.
    funcs = _extract(src, "def _is_esp32c6():", "\n_configure_antenna()\n")
    uart_block = _extract(src, "UART_ID = 1", "SLOT_LEN = P.REC_HDR_LEN")
    block = funcs + "\n" + uart_block

    uname_mod = types.SimpleNamespace(machine=machine_str)
    fake_os = types.SimpleNamespace(uname=lambda: uname_mod)

    pins_driven = []

    class FakePin:
        OUT = "out"

        def __init__(self, num, mode):
            self.num = num

        def value(self, v):
            pins_driven.append((self.num, v))

    fake_machine = types.SimpleNamespace(Pin=FakePin)
    fake_time = types.SimpleNamespace(sleep_ms=lambda ms: None)

    # _is_esp32c6() and _configure_antenna() do local `import os` / `from
    # machine import Pin`; patch sys.modules so those reach the fakes.
    saved = {}
    for name, fake in (("os", fake_os), ("machine", fake_machine),
                       ("time", fake_time)):
        saved[name] = sys.modules.get(name)
        sys.modules[name] = fake

    g = {
        "os": fake_os, "machine": fake_machine, "time": fake_time,
        "MODEM_EXTERNAL_ANTENNA": external_antenna,
    }
    try:
        exec(compile(block, SRC_PATH, "exec"), g)
        g["_configure_antenna"]()
    finally:
        for name, mod in saved.items():
            if mod is not None:
                sys.modules[name] = mod
            else:
                del sys.modules[name]
    return g, pins_driven


def test_s3_defaults():
    g, pins = _run_for_machine("ESP32S3 module", True)
    assert g["UART_TX"] == 43 and g["UART_RX"] == 44
    assert g["RING_SLOTS"] == 128
    assert pins == [], "antenna pins must not be touched on an S3"


def test_c6_pins_and_ring():
    g, pins = _run_for_machine("ESP32C6 module", True)
    assert g["UART_TX"] == 0 and g["UART_RX"] == 1
    assert g["RING_SLOTS"] == 64
    assert pins == [(3, 0), (14, 1)], pins


def test_c6_onboard_antenna():
    g, pins = _run_for_machine("ESP32C6 module", False)
    assert pins == [(3, 0), (14, 0)], pins


if __name__ == "__main__":
    tests = [test_s3_defaults, test_c6_pins_and_ring, test_c6_onboard_antenna]
    for fn in tests:
        fn()
        print("ok  ", fn.__name__)
    print("%d passed" % len(tests))
