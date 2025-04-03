# adxl345.py
import ustruct
from machine import I2C

class ADXL345:
    # Register Map
    ADXL345_DEVID = 0x00
    ADXL345_POWER_CTL = 0x2D
    ADXL345_TAP_AXES = 0x2A
    ADXL345_THRESH_TAP = 0x1D
    ADXL345_DUR = 0x21
    ADXL345_INT_ENABLE = 0x2E
    ADXL345_INT_SOURCE = 0x30

    def __init__(self, i2c, addr=0x53):
        self.i2c = i2c
        self.addr = addr
        self._check_device()

    def _check_device(self):
        dev_id = self.i2c.readfrom_mem(self.addr, self.ADXL345_DEVID, 1)
        if dev_id[0] != 0xE5:
            raise Exception('ADXL345 not found')

    def power_on(self):
        # Put the ADXL345 into measurement mode
        self.i2c.writeto_mem(self.addr, self.ADXL345_POWER_CTL, b'\x08')

    def set_tap_threshold(self, threshold):
        # Set the tap threshold (0-255)
        self.i2c.writeto_mem(self.addr, self.ADXL345_THRESH_TAP, ustruct.pack('B', threshold))

    def set_tap_duration(self, duration):
        # Set the tap duration (0-255)
        self.i2c.writeto_mem(self.addr, self.ADXL345_DUR, ustruct.pack('B', duration))

    def enable_tap_detection(self, single_tap=True, double_tap=False):
        # Enable single-tap detection on X, Y, and Z axes
        axes = 0x07 if single_tap else 0x00
        self.i2c.writeto_mem(self.addr, self.ADXL345_TAP_AXES, ustruct.pack('B', axes))
        self.i2c.writeto_mem(self.addr, self.ADXL345_INT_ENABLE, b'\x40' if single_tap else b'\x00')

    def is_tapped(self):
        # Read the interrupt source to check for a tap
        int_source = self.i2c.readfrom_mem(self.addr, self.ADXL345_INT_SOURCE, 1)
        return int_source[0] & 0x40 != 0
