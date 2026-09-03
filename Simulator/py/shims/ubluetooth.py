"""Fake `ubluetooth` module — import safety only."""


class BLE:
    def __init__(self, *a, **k):
        self._active = False

    def active(self, on=None):
        if on is None:
            return self._active
        self._active = bool(on)

    def config(self, *a, **k):
        return None

    def irq(self, *a, **k):
        pass

    def gap_advertise(self, *a, **k):
        pass

    def gap_scan(self, *a, **k):
        pass

    def gatts_register_services(self, *a, **k):
        return ()
