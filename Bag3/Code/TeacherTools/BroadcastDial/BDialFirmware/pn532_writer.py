"""pn532_writer.py -- a PN532 (0x24) behind card_writer.NfcWriter's method
names, so station.py and card_writer.write_text/existing_text drive it the
same as the WS1850S. Built by nfc_detect.make_reader() when a PN532 answers
on Port A. Untested on a Dial.
"""

import time

from pn532 import PN532, MIFARE_AUTH_A
from card_writer import sak_type

CMD_RFCONFIGURATION = 0x32
CMD_INRELEASE = 0x52


class Pn532Writer:
    def __init__(self, i2c, addr=0x24):
        self.dev = PN532(i2c, addr)
        self._ant = False

    def init(self):
        return self.dev.begin()

    def _rf(self, on):
        # RFConfiguration item 1 (RF field): bit 0 = field on.
        self.dev._send_command(CMD_RFCONFIGURATION, bytes([0x01, 0x01 if on else 0x00]))
        self._ant = on

    def antenna_on(self):
        self._rf(True)

    def antenna_off(self):
        self._rf(False)

    def antenna_is_on(self):
        return self._ant

    def crypto_on(self):
        return False    # the PN532 tracks Crypto1 itself

    def stop_crypto1(self):
        # Release the selected target so the next InListPassiveTarget is a
        # fresh select (what stop_crypto1 + REQA does on the WS1850S).
        try:
            self.dev._send_command(CMD_INRELEASE, b'\x00')
        except Exception:
            pass

    def halt(self):
        self.stop_crypto1()

    def detect_tag(self, timeout=500):
        tag = self.dev.read_passive_target(timeout=timeout)
        if tag is None:
            return None
        sak = tag['sak']
        tag['tag_type'] = sak_type(sak)
        tag['is_classic'] = sak in (0x08, 0x18, 0x09)
        tag['is_ntag'] = sak == 0x00
        return tag

    def mifare_auth(self, uid, block, key=b'\xFF\xFF\xFF\xFF\xFF\xFF', kt=MIFARE_AUTH_A):
        return self.dev.mifare_auth_block(uid, block, key, kt)

    def mifare_read(self, block):
        return self.dev.mifare_read_block(block)

    def mifare_write(self, block, data):
        return self.dev.mifare_write_block(block, data)

    def ntag_write_page(self, page, data):
        return self.dev.ntag_write_page(page, data)

    def ntag_read_page(self, page):
        return self.dev.ntag_read_page(page)
