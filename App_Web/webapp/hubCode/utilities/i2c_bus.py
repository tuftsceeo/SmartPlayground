#accel.py
from machine import Pin, SoftI2C
from time import sleep_ms, ticks_ms, ticks_diff
from micropython import const

import utilities.lc709203f
import utilities.max17048

# Register addresses
_WHO_AM_I = const(0x0F)
_CTRL1 = const(0x20)
_CTRL2 = const(0x21)
_CTRL6 = const(0x25)
_STATUS = const(0x27)
_OUT_X_L = const(0x28)

_DEVICE_ID = const(0x44)

ODR_400_HZ = const(0b0111)
MODE_HIGH_PERFORMANCE = const(0b01)
RANGE_2G = const(0b00)

SCL = 23
SDA = 22
ADDRESS = 0x19

class Battery:
    def __init__(self):
        self.battery_sensor = None
        i2c = SoftI2C(scl = Pin(SCL), sda = Pin(SDA))
        try:
            self.battery_sensor = utilities.lc709203f.LC709203F(i2c)
        except:
            try:
                self.battery_sensor = utilities.max17048.MAX17048(i2c)
            except:
                print('no battery')

    def read(self):
        return self.battery_sensor.cell_percent if self.battery_sensor else None
    

class LIS2DW12:
    def __init__(self):
        self.i2c = SoftI2C(scl=Pin(SCL), sda=Pin(SDA))
        self.address = ADDRESS
        self._scale = 2
        
        if self.who_am_i() != _DEVICE_ID:
            raise RuntimeError("Failed to find LIS2DW12")
        
        self.reset()
        sleep_ms(10)
        
        self.set_mode(MODE_HIGH_PERFORMANCE)
        self.set_odr(ODR_400_HZ)
        self.set_range(RANGE_2G)
    
    def _read_register(self, register, length=1):
        return self.i2c.readfrom_mem(self.address, register, length)
    
    def _write_register(self, register, value):
        self.i2c.writeto_mem(self.address, register, bytes([value]))
    
    def who_am_i(self):
        return self._read_register(_WHO_AM_I)[0]
    
    def reset(self):
        self._write_register(_CTRL2, 0x40)
        sleep_ms(10)
    
    def set_odr(self, odr):
        ctrl1 = self._read_register(_CTRL1)[0]
        ctrl1 = (ctrl1 & 0x0F) | (odr << 4)
        self._write_register(_CTRL1, ctrl1)
    
    def set_mode(self, mode):
        ctrl1 = self._read_register(_CTRL1)[0]
        ctrl1 = (ctrl1 & 0xF3) | (mode << 2)
        self._write_register(_CTRL1, ctrl1)
    
    def set_range(self, range_val):
        ctrl6 = self._read_register(_CTRL6)[0]
        ctrl6 = (ctrl6 & 0xCF) | (range_val << 4)
        self._write_register(_CTRL6, ctrl6)
        self._scale = 2 ** (range_val + 1)
    
    def data_ready(self):
        status = self._read_register(_STATUS)[0]
        return bool(status & 0x01)
    
    def read_raw(self):
        data = self._read_register(_OUT_X_L, 6)
        
        x = data[0] | (data[1] << 8)
        y = data[2] | (data[3] << 8)
        z = data[4] | (data[5] << 8)
        if x >= 0x8000: x -= 0x10000
        if y >= 0x8000: y -= 0x10000
        if z >= 0x8000: z -= 0x10000
        return (x, y, z)
    
    def read_accel(self):
        x, y, z = self.read_raw()
        scale_factor = self._scale / 32768.0
        return (
            x * scale_factor,
            y * scale_factor,
            z * scale_factor
        )