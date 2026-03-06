"""
LIS2DW12 Accelerometer Driver — MicroPython
============================================
I2C driver with hardware wake-up interrupt support.

Usage:
    from lis2dw12 import LIS2DW12
    import machine

    i2c = machine.SoftI2C(sda=machine.Pin(22), scl=machine.Pin(23), freq=400_000)
    accel = LIS2DW12(i2c)
    accel.init()
    accel.enable_wake_int1(threshold=8)

    # Poll interrupt pin
    int1 = machine.Pin(1, machine.Pin.IN)
    if int1.value():
        accel.clear_wake()
        print("Shake detected!")

    # Or read raw values
    x, y, z = accel.read()
"""

import struct
import time

# Registers
_WHO_AM_I     = 0x0F
_CTRL1        = 0x20
_CTRL2        = 0x21
_CTRL4_INT1   = 0x23
_CTRL5_INT2   = 0x24
_CTRL6        = 0x25
_CTRL7        = 0x3F
_STATUS       = 0x27
_OUT_X_L      = 0x28
_WAKE_UP_THS  = 0x34
_WAKE_UP_DUR  = 0x35
_WAKE_UP_SRC  = 0x38

# WHO_AM_I expected value
_DEVICE_ID = 0x44

# Full-scale range configs for CTRL6 (low-noise enabled)
RANGE_2G  = 0x04
RANGE_4G  = 0x14
RANGE_8G  = 0x24
RANGE_16G = 0x34

# Sensitivity: 14-bit left-justified in 16-bit register
# Correct factor = range / (2^14) per LSB
_SENSITIVITY = {
    RANGE_2G:  0.000061,   # 2/32768 ≈ 0.061 mg/LSB
    RANGE_4G:  0.000122,   # 4/32768 ≈ 0.122 mg/LSB
    RANGE_8G:  0.000244,   # 8/32768 ≈ 0.244 mg/LSB
    RANGE_16G: 0.000488,   # 16/32768 ≈ 0.488 mg/LSB
}

# Wake-up threshold: 1 LSB = full_scale / 64
_WAKE_LSB_G = {
    RANGE_2G:  0.03125,
    RANGE_4G:  0.0625,
    RANGE_8G:  0.125,
    RANGE_16G: 0.25,
}


class LIS2DW12:
    def __init__(self, i2c, addr=0x19):
        self.i2c = i2c
        self.addr = addr
        self._range = RANGE_4G
        self._sens = _SENSITIVITY[RANGE_4G]

    def _read_reg(self, reg, n=1):
        return self.i2c.readfrom_mem(self.addr, reg, n)

    def _write_reg(self, reg, val):
        self.i2c.writeto_mem(self.addr, reg, bytes([val]))

    @property
    def device_id(self):
        return self._read_reg(_WHO_AM_I)[0]

    def init(self, odr_mode=0x54, fs_range=RANGE_4G):
        """
        Initialize the accelerometer.

        Args:
            odr_mode: CTRL1 value. Default 0x54 = 100Hz High-Performance.
                      Other options: 0x14=12.5Hz, 0x34=50Hz, 0x64=200Hz
            fs_range: Full-scale range. RANGE_2G/4G/8G/16G.
        """
        who = self.device_id
        if who != _DEVICE_ID:
            raise RuntimeError("LIS2DW12 not found (got 0x%02X, expected 0x%02X)" % (who, _DEVICE_ID))

        # Soft reset
        self._write_reg(_CTRL2, 0x40)
        time.sleep_ms(10)

        # Set ODR + mode
        self._write_reg(_CTRL1, odr_mode)

        # Set range + low-noise
        self._range = fs_range
        self._sens = _SENSITIVITY[fs_range]
        self._write_reg(_CTRL6, fs_range)

        time.sleep_ms(20)

    def read(self):
        """Read acceleration in g. Returns (x, y, z) tuple."""
        data = self._read_reg(_OUT_X_L, 6)
        x = struct.unpack('<h', data[0:2])[0] * self._sens
        y = struct.unpack('<h', data[2:4])[0] * self._sens
        z = struct.unpack('<h', data[4:6])[0] * self._sens
        return x, y, z

    @property
    def data_ready(self):
        return bool(self._read_reg(_STATUS)[0] & 0x01)

    def enable_wake_int1(self, threshold=8, duration=0x00):
        """
        Enable wake-up interrupt on INT1 pin.

        Args:
            threshold: Wake-up threshold in LSBs (1 LSB = full_scale/64).
                       At ±4g: 8 = 0.5g, 12 = 0.75g, 16 = 1.0g
            duration:  WAKE_UP_DUR register value.
                       0x00 = no filter, 0x40 = 2 samples, 0x60 = 3 samples
        """
        self._write_reg(_WAKE_UP_THS, threshold & 0x3F)
        self._write_reg(_WAKE_UP_DUR, duration)
        self._write_reg(_CTRL4_INT1, 0x20)  # route wake-up to INT1
        self._write_reg(_CTRL7, 0x20)       # enable interrupts
        time.sleep_ms(10)
        self.clear_wake()  # clear any pending

    def enable_wake_int2(self, threshold=8, duration=0x00):
        """Enable wake-up interrupt on INT2 pin. Same args as int1."""
        self._write_reg(_WAKE_UP_THS, threshold & 0x3F)
        self._write_reg(_WAKE_UP_DUR, duration)
        self._write_reg(_CTRL5_INT2, 0x20)  # route wake-up to INT2
        self._write_reg(_CTRL7, 0x20)       # enable interrupts
        time.sleep_ms(10)
        self.clear_wake()

    def clear_wake(self):
        """Clear wake-up interrupt by reading WAKE_UP_SRC. Returns source byte."""
        return self._read_reg(_WAKE_UP_SRC)[0]

    @property
    def wake_threshold_g(self):
        """Current wake-up threshold in g."""
        ths = self._read_reg(_WAKE_UP_THS)[0] & 0x3F
        return ths * _WAKE_LSB_G[self._range]