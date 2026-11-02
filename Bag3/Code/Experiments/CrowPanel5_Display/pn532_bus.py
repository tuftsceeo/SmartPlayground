"""PN532 on the CrowPanel's touch bus (GPIO19/20), through lvgl_micropython's i2c.I2C.Bus.

pn532.py wants a machine.I2C-like object; i2c.I2C.Bus already has readfrom/writeto with the same
signatures, so the wand driver runs unchanged on it. This adds RF field control and a bounded
detect (the wand driver's default retries never return without a card).
"""

import time

from pn532 import PN532

CMD_RFCONFIGURATION = 0x32
_ITEM_FIELD = 0x01
_ITEM_RETRIES = 0x05


class PN532Bus(PN532):
    def start(self):
        """Wake and configure; returns the firmware tuple. Retries: the first transfer can fail."""
        err = None
        for _ in range(4):
            try:
                fw = self.begin()
                # MxRtyATR, MxRtyPSL, MxRtyPassiveActivation: a detect returns instead of waiting
                self._send_command(CMD_RFCONFIGURATION, bytes([_ITEM_RETRIES, 0xFF, 0x01, 0x02]))
                return fw
            except Exception as e:
                err = e
                time.sleep_ms(50)
        raise err

    def field(self, on):
        self._send_command(CMD_RFCONFIGURATION, bytes([_ITEM_FIELD, 0x02 if on else 0x00]))

    def detect(self, timeout=120):
        """UID hex string, or None when no card answers."""
        tag = self.read_passive_target(timeout=timeout)
        return tag["uid_hex"] if tag else None
