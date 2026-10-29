"""
OPT3002 Light Sensor Driver — MicroPython
==========================================
I2C driver for ambient light measurement in lux.

Usage:
    from opt3002 import OPT3002
    import machine

    i2c = machine.SoftI2C(sda=machine.Pin(22), scl=machine.Pin(23), freq=400_000)
    light = OPT3002(i2c)
    light.init()

    print("%.1f lux" % light.lux)
"""

import time

# Registers
_RESULT        = 0x00
_CONFIG        = 0x01
_LOW_LIMIT     = 0x02
_HIGH_LIMIT    = 0x03
_MANUFACTURER  = 0x7E
_DEVICE_ID     = 0x7F

# Config presets (16-bit big-endian)
MODE_CONTINUOUS_100MS = 0xC610   # continuous, auto-range, 100ms conversion
MODE_CONTINUOUS_800MS = 0xC810   # continuous, auto-range, 800ms conversion
MODE_SINGLE_800MS     = 0xCA10   # single-shot, auto-range, 800ms conversion
MODE_SHUTDOWN         = 0xC010   # shutdown / low power

# Expected IDs
_EXPECTED_MFR = 0x5449   # "TI"
_EXPECTED_DEV = 0x3001


class OPT3002:
    def __init__(self, i2c, addr=0x44):
        self.i2c = i2c
        self.addr = addr

    def _read_reg16(self, reg):
        data = self.i2c.readfrom_mem(self.addr, reg, 2)
        return (data[0] << 8) | data[1]

    def _write_reg16(self, reg, value):
        self.i2c.writeto_mem(self.addr, reg, bytes([value >> 8, value & 0xFF]))

    @property
    def manufacturer_id(self):
        return self._read_reg16(_MANUFACTURER)

    @property
    def device_id(self):
        return self._read_reg16(_DEVICE_ID)

    def init(self, mode=MODE_CONTINUOUS_100MS):
        """
        Initialize the light sensor.

        Args:
            mode: Config register value. Defaults to continuous 100ms.
                  Use MODE_CONTINUOUS_800MS for higher accuracy.
                  Use MODE_SINGLE_800MS for one-shot reads.
        """
        mfr = self.manufacturer_id
        if mfr != _EXPECTED_MFR:
            raise RuntimeError("OPT3002 not found (MFR=0x%04X, expected 0x%04X)" % (mfr, _EXPECTED_MFR))

        self._write_reg16(_CONFIG, mode)
        self._mode = mode

        # Wait for first conversion
        if mode & 0x0600:  # check conversion time bits
            time.sleep_ms(120)
        else:
            time.sleep_ms(850)

    @property
    def lux(self):
        """Read ambient light level in lux."""
        raw = self._read_reg16(_RESULT)
        exponent = (raw >> 12) & 0x0F
        mantissa = raw & 0x0FFF
        return 0.01 * mantissa * (1 << exponent)

    def read_single(self):
        """Trigger a single-shot 800ms measurement and return lux."""
        self._write_reg16(_CONFIG, MODE_SINGLE_800MS)
        time.sleep_ms(850)
        return self.lux

    @property
    def config(self):
        """Read current config register."""
        return self._read_reg16(_CONFIG)

    @property
    def conversion_ready(self):
        """Check if a new result is available (config bit 7)."""
        cfg = self._read_reg16(_CONFIG)
        return bool(cfg & 0x0080)

    def set_limits(self, low_lux=0, high_lux=83865):
        """
        Set high/low lux limits for interrupt (note: INT not routed on this board).
        Useful for the flag bits in the config register.
        """
        self._write_reg16(_LOW_LIMIT, self._lux_to_raw(low_lux))
        self._write_reg16(_HIGH_LIMIT, self._lux_to_raw(high_lux))

    def shutdown(self):
        """Put sensor in low-power shutdown mode."""
        self._write_reg16(_CONFIG, MODE_SHUTDOWN)

    @staticmethod
    def _lux_to_raw(lux):
        """Convert lux value to raw register format."""
        if lux <= 0:
            return 0
        # Find smallest exponent where mantissa fits in 12 bits
        for exp in range(16):
            mantissa = int(lux / (0.01 * (1 << exp)))
            if mantissa <= 0x0FFF:
                return (exp << 12) | mantissa
        return 0xFFFF  # max

    def is_connected(self):
        try:
            return self.manufacturer_id == _EXPECTED_MFR
        except Exception:
            return False

    def __repr__(self):
        try:
            return "OPT3002(%.1f lux)" % self.lux
        except Exception:
            return "OPT3002(not responding)"