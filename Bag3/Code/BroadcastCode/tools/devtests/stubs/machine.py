"""Stub: MicroPython machine, absent on a dev box."""


class Pin:
    OUT = 1
    IN = 0
    PULL_UP = 2

    def __init__(self, *a, **k):
        pass

    def value(self, *a):
        return 0


class SoftI2C:
    def __init__(self, *a, **k):
        pass

    def scan(self):
        return []

    def writeto(self, *a, **k):
        pass

    def readfrom(self, addr, n):
        return bytes(n)


class PWM:
    def __init__(self, *a, **k):
        pass

    def freq(self, *a):
        return 0

    def duty_u16(self, *a):
        return 0

    def deinit(self):
        pass


class RESET:
    pass


# reset_cause() values as on the esp32 port; tests set _reset_cause.
PWRON_RESET = 1
HARD_RESET = 2
WDT_RESET = 3
DEEPSLEEP_RESET = 4
SOFT_RESET = 5
_reset_cause = PWRON_RESET


def reset_cause():
    return _reset_cause


def reset():
    raise SystemExit("machine.reset()")


def unique_id():
    return b"\x01\x02\x03\x04\x05\x06"


def freq(*a):
    return 160_000_000
