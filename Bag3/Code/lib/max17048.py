"""
MAX17048 Battery Fuel Gauge Driver — MicroPython
=================================================
I2C driver for LiPo battery voltage and state-of-charge.
Auto-starts on power-up, no configuration needed.

Usage:
    from max17048 import MAX17048
    import machine

    i2c = machine.SoftI2C(sda=machine.Pin(22), scl=machine.Pin(23), freq=400_000)
    batt = MAX17048(i2c)

    print("%.2fV  %.1f%%" % (batt.voltage, batt.soc))
"""

# Registers (all 16-bit big-endian)
_VCELL   = 0x02
_SOC     = 0x04
_MODE    = 0x06
_VERSION = 0x08
_CONFIG  = 0x0C
_COMMAND = 0xFE


class MAX17048:
    
    def __init__(self, i2c, addr=0x36, quick_start=True):
        self.i2c = i2c
        self.addr = addr
        if quick_start:
            try:
                self.quick_start()
            except Exception:
                pass  # chip not present; let later reads fail


    def _read_reg16(self, reg):
        """Read a 16-bit big-endian register."""
        data = self.i2c.readfrom_mem(self.addr, reg, 2)
        return (data[0] << 8) | data[1]

    def _write_reg16(self, reg, value):
        """Write a 16-bit big-endian register."""
        self.i2c.writeto_mem(self.addr, reg, bytes([value >> 8, value & 0xFF]))

    @property
    def voltage(self):
        """Battery voltage in Volts."""
        raw = self._read_reg16(_VCELL)
        return raw * 78.125 / 1_000_000

    @property
    def soc(self):
        """State of charge in percent (0–100+)."""
        data = self.i2c.readfrom_mem(self.addr, _SOC, 2)
        return data[0] + data[1] / 256.0

    @property
    def version(self):
        """IC version number. Non-zero means communication is working."""
        return self._read_reg16(_VERSION)

    @property
    def charging(self):
        """Rough estimate: True if SoC is increasing (not precise)."""
        s1 = self.soc
        import time
        time.sleep_ms(500)
        s2 = self.soc
        return s2 > s1

    def reset(self):
        """Power-on-reset the fuel gauge."""
        self._write_reg16(_COMMAND, 0x5400)

    def quick_start(self):
        """Trigger a quick-start for faster initial SoC estimate."""
        self._write_reg16(_MODE, 0x4000)

    def is_connected(self):
        """Check if the MAX17048 is responding."""
        try:
            v = self.version
            return v != 0
        except Exception:
            return False

    def read_all(self):
        """Read voltage and SoC in one call. Returns (voltage, soc) tuple."""
        return self.voltage, self.soc

    def __repr__(self):
        try:
            v, s = self.read_all()
            return "MAX17048(%.2fV, %.1f%%)" % (v, s)
        except Exception:
            return "MAX17048(not responding)"