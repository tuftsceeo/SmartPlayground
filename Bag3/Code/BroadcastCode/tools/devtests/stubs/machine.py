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


class RESET:
    pass


def reset():
    raise SystemExit("machine.reset()")


def unique_id():
    return b"\x01\x02\x03\x04\x05\x06"


def freq(*a):
    return 160_000_000
