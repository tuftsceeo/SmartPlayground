import machine
from machine import Pin, SoftI2C
from pn532_i2c import PN532_I2C
from icons import SSD1306_SMART
import utime

SDA = 6
SCL = 7

#nav switches
switch_down = Pin(8, Pin.IN)
switch_select = Pin(9, Pin.IN)
switch_up= Pin(10, Pin.IN)

i2c = SoftI2C(scl = Pin(7), sda = Pin(6))
display = SSD1306_SMART(128, 64, i2c,switch_up)


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

    
def on_detect(uid):
    print(f'detected {uid}')
    display.text(f"detected",10,20,1)
    display.text(f"{uid}",10,30,1)
    display.show()

def on_remove(uid):
    print(f'removed {uid}')
    display.text(f"removed",10,40,1)
    display.text(f"{uid}",10,50,1)
    display.show()

nfc = NFC(on_detect, on_remove)
display.clear()
display.text('welcome',10,0,1)
display.text(nfc.version(), 10,10,1)
display.show()

while nfc.rf is not None:
    try:
        nfc.read(timeout = 1.0)
    except Exception as e:
        nfc.reset()
        
