import bluetooth
import time
import struct

NAME_FLAG = 0x09

class Yell:
    def __init__(self):
        self._ble = bluetooth.BLE()
        self._ble.active(True)
        
    def advertise(self, name = 'Pico', interval_us=100000):
        short = name[:8]
        payload = struct.pack("BB", len(short) + 1, NAME_FLAG) + name[:8]  # byte length, byte type, value
        self._ble.gap_advertise(interval_us, adv_data=payload)
        
    def stop_advertising(self):
        self._ble.gap_advertise(None)

p = Yell()
p.advertise('!Fred')
time.sleep(10)
p.advertise('!rocks')
time.sleep(10)


p.stop_advertising()
