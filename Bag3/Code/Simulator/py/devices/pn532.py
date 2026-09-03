"""Stub PN532 — import surface only; NFC is shimmed at NfcReader."""

MIFARE_AUTH_A = 0
MIFARE_AUTH_B = 1


class PN532:
    def __init__(self, i2c, addr=0x24):
        self.i2c = i2c
        self.addr = addr

    def begin(self):
        return (0x32, 1, 6)

    def read_passive_target(self, timeout=1000):
        return None

    def SAM_configuration(self):
        pass

    def mifare_classic_authenticate_block(self, *a, **k):
        return False

    def mifare_classic_read_block(self, *a, **k):
        return None
