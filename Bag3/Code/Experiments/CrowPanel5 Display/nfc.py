"""NFC reader on the touch bus (WS1850S at 0x28, else PN532) behind the method names card_writer expects."""

import time

import display_lvgl
from pn532_bus import PN532Bus

MIFARE_AUTH_A = 0x60


class Reader:
    def __init__(self):
        self.pn = None
        self.ws = None
        self.error = "No NFC reader found"
        self._crypto = False

    def init(self):
        """True when a PN532 answered; otherwise .error says why."""
        bus = display_lvgl.BUS
        try:
            found = bus.scan()
        except Exception as e:
            self.error = f"I2C scan failed: {e}"
            return False
        if 0x28 in found:
            try:
                from ws1850s import WS1850S
                self.ws = WS1850S(bus, 0x28)
                self.ws.version()
                self.pn = self.ws
                return True
            except Exception as e:
                self.ws = None
                self.error = f"WS1850S error: {e}"
        for addr in (0x24, 0x22):
            if addr not in found:
                continue
            pn = PN532Bus(bus, addr)
            try:
                pn.start()
                self.pn = pn
                return True
            except Exception as e:
                self.error = f"PN532 error: {e}"
        return False

    @property
    def ok(self):
        return self.pn is not None

    def antenna_on(self):
        if self.ws:
            self.ws.antenna_on()
        else:
            self.pn.field(True)

    def antenna_off(self):
        try:
            if self.ws:
                self.ws.antenna_off()
            else:
                self.pn.field(False)
        except Exception:
            pass

    def crypto_on(self):
        return self.ws.crypto_on() if self.ws else self._crypto

    def antenna_is_on(self):
        return True

    def stop_crypto1(self):
        if self.ws:
            self.ws.stop_crypto1()
        self._crypto = False

    def detect_tag(self, timeout=500):
        deadline = time.ticks_add(time.ticks_ms(), timeout)
        while True:
            if self.ws:
                found = self.ws.read_uid_full()
                tag = None
                if found is not None:
                    uid, sak = found
                    tag = {"uid": uid, "uid_hex": ":".join("%02X" % b for b in uid), "sak": sak}
            else:
                tag = self.pn.read_passive_target(timeout=min(timeout, 150))
            if tag:
                sak = tag["sak"]
                tag["tag_type"] = "MIFARE Classic" if sak in (0x08, 0x18, 0x09) else ("NTAG/Ultralight" if sak == 0 else "Unknown")
                tag["is_classic"] = sak in (0x08, 0x18, 0x09)
                tag["is_ntag"] = sak == 0
                return tag
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                return None
            time.sleep_ms(2)

    def mifare_auth(self, uid, block, key=b"\xFF" * 6, kt=MIFARE_AUTH_A):
        self._crypto = True
        if self.ws:
            return self.ws.auth(kt, block, key, uid) == self.ws.MI_OK
        return self.pn.mifare_auth_block(uid, block, key, kt)

    def mifare_read(self, block):
        if self.ws:
            st, data = self.ws.read_block(block)
            if st != self.ws.MI_OK or data is None:
                raise RuntimeError(f"Read err (block {block})")
            return bytes(data)
        return self.pn.mifare_read_block(block)

    def mifare_write(self, block, data):
        if self.ws:
            if self.ws.write_block(block, data) != self.ws.MI_OK:
                raise RuntimeError(f"Classic write err (block {block})")
            return True
        return self.pn.mifare_write_block(block, data)

    def ntag_write_page(self, page, data):
        if self.ws:
            if self.ws.ul_write(page, data) != self.ws.MI_OK:
                raise RuntimeError(f"NTAG write err (page {page})")
            return True
        return self.pn.ntag_write_page(page, data)

    def ntag_read_page(self, page):
        if self.ws:
            st, data = self.ws.ul_read(page)
            if st != self.ws.MI_OK or data is None:
                raise RuntimeError(f"Read err (page {page})")
            return bytes(data[:4])
        return self.pn.ntag_read_page(page)

    def halt(self):
        pass
