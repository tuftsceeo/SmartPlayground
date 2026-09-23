"""Fake `network` module — import safety only."""

STA_IF = 0
AP_IF = 1


class WLAN:
    def __init__(self, interface=STA_IF):
        self.interface = interface
        self._active = False

    def active(self, on=None):
        if on is None:
            return self._active
        self._active = bool(on)

    def connect(self, *a, **k):
        pass

    def disconnect(self):
        pass

    def status(self):
        return 0

    def ifconfig(self, *a, **k):
        return ("192.168.1.2", "255.255.255.0", "192.168.1.1", "8.8.8.8")

    def config(self, *a, **k):
        if a and a[0] == "mac":
            return b"\xaa\xbb\xcc\xdd\xee\xff"
        return None
