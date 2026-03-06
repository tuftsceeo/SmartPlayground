import machine
from machine import Pin, SoftI2C
from utilities.pn532_i2c import PN532_I2C
import utime

SDA = 22
SCL = 23

i2c = SoftI2C(scl = Pin(SCL), sda = Pin(SDA))

class NFC:
    def __init__(self, detect_callback = None, removed_calback = None):
        self.on_detect = detect_callback
        self.on_remove = removed_calback
        self.error_count = 0
        self.last_read_failed = False
        self.detected_cards = set()
        
        #i2c = machine.I2C(0, scl=machine.Pin(SCL), sda=machine.Pin(SDA), freq=100000)
        self.rf = PN532_I2C(i2c, debug=False)
        self.rf.SAM_configuration()
        
    def version(self):
        try:
            ic, ver, rev, support = self.rf.get_firmware_version()
            return 'Firmware: {0}.{1}'.format(ver, rev)
        except Exception as e:
            self.rf = None
            return f'No NFC detected: {e}'
            
    def read(self, timeout = 1.0):
        uid = self.rf.read_passive_target(timeout=timeout)
        self.error_count = 0  # Reset error count on success
        if uid:
            uid_tuple = tuple(uid)
            # New card detected
            if uid_tuple not in self.detected_cards:
                self.detected_cards.add(uid_tuple)
                if self.on_detect: self.on_detect(list(uid))
            self.last_read_failed = False
        else:
            # No card detected - check for removals - if there was no reading then the card is no longer there.
            if self.detected_cards and not self.last_read_failed:
                for card in self.detected_cards:
                    if self.on_remove: self.on_remove(list(card))
                self.detected_cards.clear()
            self.last_read_failed = False
        
    def reset(self):
        self.error_count += 1
        self.last_read_failed = True

        if self.error_count > 5:
            try:
                self.rf.SAM_configuration()
                self.error_count = 0
            except Exception:
                pass


