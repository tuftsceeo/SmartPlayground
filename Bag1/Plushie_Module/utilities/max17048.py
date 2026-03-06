"""
MAX17048/MAX17049 Battery Fuel Gauge Library for MicroPython

Converted from Adafruit CircuitPython library
Original Author: ladyada
MicroPython conversion includes direct I2C register operations
"""

from micropython import const
import struct
import time

__version__ = "1.0.0"

MAX1704X_I2CADDR_DEFAULT = const(0x36)  # Default I2C address

_MAX1704X_VCELL_REG = const(0x02)
_MAX1704X_SOC_REG = const(0x04)
_MAX1704X_MODE_REG = const(0x06)
_MAX1704X_VERSION_REG = const(0x08)
_MAX1704X_HIBRT_REG = const(0x0A)
_MAX1704X_CONFIG_REG = const(0x0C)
_MAX1704X_VALERT_REG = const(0x14)
_MAX1704X_CRATE_REG = const(0x16)
_MAX1704X_VRESET_REG = const(0x18)
_MAX1704X_CHIPID_REG = const(0x19)
_MAX1704X_STATUS_REG = const(0x1A)
_MAX1704X_CMD_REG = const(0xFE)

ALERTFLAG_SOC_CHANGE = 0x20
ALERTFLAG_SOC_LOW = 0x10
ALERTFLAG_VOLTAGE_RESET = 0x08
ALERTFLAG_VOLTAGE_LOW = 0x04
ALERTFLAG_VOLTAGE_HIGH = 0x02
ALERTFLAG_RESET_INDICATOR = 0x01


class MAX17048:
    """Driver for the MAX17048/MAX17049 battery fuel gauge.
    
    :param i2c: The I2C bus object (machine.I2C)
    :param address: The I2C device address. Defaults to 0x36
    """

    def __init__(self, i2c, address=MAX1704X_I2CADDR_DEFAULT):
        self.i2c = i2c
        self.address = address
        
        # Verify chip version
        if self.chip_version & 0xFFF0 != 0x0010:
            raise RuntimeError("Failed to find MAX1704X - check your wiring!")
        
        self.reset()
        self.enable_sleep = False
        self.sleep = False

    def _read_register(self, reg, num_bytes):
        """Read num_bytes from register reg"""
        return self.i2c.readfrom_mem(self.address, reg, num_bytes)
    
    def _write_register(self, reg, data):
        """Write data bytes to register reg"""
        self.i2c.writeto_mem(self.address, reg, data)
    
    def _read_u16_be(self, reg):
        """Read unsigned 16-bit big-endian value from register"""
        data = self._read_register(reg, 2)
        return struct.unpack('>H', data)[0]
    
    def _read_s16_be(self, reg):
        """Read signed 16-bit big-endian value from register"""
        data = self._read_register(reg, 2)
        return struct.unpack('>h', data)[0]
    
    def _read_u8(self, reg):
        """Read unsigned 8-bit value from register"""
        data = self._read_register(reg, 1)
        return data[0]
    
    def _write_u16_be(self, reg, value):
        """Write unsigned 16-bit big-endian value to register"""
        data = struct.pack('>H', value)
        self._write_register(reg, data)
    
    def _write_u8(self, reg, value):
        """Write unsigned 8-bit value to register"""
        self._write_register(reg, bytes([value]))
    
    def _read_bit(self, reg, bit):
        """Read a single bit from a register"""
        value = self._read_u8(reg)
        return bool(value & (1 << bit))
    
    def _write_bit(self, reg, bit, value):
        """Write a single bit to a register"""
        current = self._read_u8(reg)
        if value:
            current |= (1 << bit)
        else:
            current &= ~(1 << bit)
        self._write_u8(reg, current)
    
    def _read_bits(self, reg, shift, num_bits):
        """Read multiple bits from a register"""
        value = self._read_u8(reg)
        mask = (1 << num_bits) - 1
        return (value >> shift) & mask
    
    def _write_bits(self, reg, shift, num_bits, value):
        """Write multiple bits to a register"""
        current = self._read_u8(reg)
        mask = ((1 << num_bits) - 1) << shift
        current = (current & ~mask) | ((value << shift) & mask)
        self._write_u8(reg, current)

    @property
    def chip_version(self):
        """Read the chip version"""
        return self._read_u16_be(_MAX1704X_VERSION_REG)
    
    @property
    def chip_id(self):
        """Read the chip ID"""
        return self._read_u8(_MAX1704X_CHIPID_REG)

    def reset(self):
        """Perform a soft reset of the chip"""
        try:
            self._write_u16_be(_MAX1704X_CMD_REG, 0x5400)
            # If we get here without exception, wait for reset
            time.sleep_ms(125)
        except OSError:
            # Expected NACK after reset command in some cases
            time.sleep_ms(125)
        
        # Wait for chip to be ready after reset
        time.sleep_ms(10)
        
        # Clear reset alert - try multiple times as chip may need time
        for attempt in range(10):
            try:
                time.sleep_ms(10)
                self.reset_alert = False
                return
            except OSError:
                if attempt == 9:
                    # Last attempt failed, but this might be OK
                    # Some chips don't set the alert properly
                    return
                continue

    @property
    def cell_voltage(self):
        """The voltage of the battery cell in volts"""
        # Read twice to ensure we get a fresh value, not cached by I2C
        self._read_u16_be(_MAX1704X_VCELL_REG)
        time.sleep_ms(10)
        raw = self._read_u16_be(_MAX1704X_VCELL_REG)
        return raw * 78.125 / 1_000_000

    @property
    def cell_percent(self):
        """The state of charge as a percentage (0-100)"""
        # Read twice to ensure we get a fresh value, not cached by I2C
        self._read_u16_be(_MAX1704X_SOC_REG)
        time.sleep_ms(10)
        raw = self._read_u16_be(_MAX1704X_SOC_REG)
        return raw / 256.0

    @property
    def charge_rate(self):
        """Charge or discharge rate in percent per hour"""
        # Read twice to ensure we get a fresh value, not cached by I2C
        self._read_s16_be(_MAX1704X_CRATE_REG)
        time.sleep_ms(10)
        raw = self._read_s16_be(_MAX1704X_CRATE_REG)
        return raw * 0.208

    @property
    def sleep(self):
        """Whether the chip is in sleep mode"""
        return self._read_bit(_MAX1704X_CONFIG_REG + 1, 7)
    
    @sleep.setter
    def sleep(self, value):
        """Set sleep mode"""
        self._write_bit(_MAX1704X_CONFIG_REG + 1, 7, value)

    @property
    def enable_sleep(self):
        """Whether sleep mode is enabled"""
        return self._read_bit(_MAX1704X_MODE_REG, 5)
    
    @enable_sleep.setter
    def enable_sleep(self, value):
        """Enable or disable sleep mode"""
        self._write_bit(_MAX1704X_MODE_REG, 5, value)

    @property
    def hibernating(self):
        """Whether the chip is currently hibernating"""
        return self._read_bit(_MAX1704X_MODE_REG, 4)

    @property
    def quick_start(self):
        """Quick start bit"""
        return self._read_bit(_MAX1704X_MODE_REG, 6)
    
    @quick_start.setter
    def quick_start(self, value):
        """Trigger quick start"""
        self._write_bit(_MAX1704X_MODE_REG, 6, value)

    @property
    def active_alert(self):
        """Whether there is an active alert"""
        return self._read_bit(_MAX1704X_CONFIG_REG + 1, 5)

    @property
    def alert_reason(self):
        """The alert status bits (bits 0-5)"""
        return self._read_u8(_MAX1704X_STATUS_REG) & 0x3F

    @property
    def reset_alert(self):
        """Reset indicator alert flag"""
        return self._read_bit(_MAX1704X_STATUS_REG, 0)
    
    @reset_alert.setter
    def reset_alert(self, value):
        """Clear or set reset alert"""
        self._write_bit(_MAX1704X_STATUS_REG, 0, value)

    @property
    def voltage_high_alert(self):
        """Voltage high alert flag"""
        return self._read_bit(_MAX1704X_STATUS_REG, 1)
    
    @voltage_high_alert.setter
    def voltage_high_alert(self, value):
        """Clear or set voltage high alert"""
        self._write_bit(_MAX1704X_STATUS_REG, 1, value)

    @property
    def voltage_low_alert(self):
        """Voltage low alert flag"""
        return self._read_bit(_MAX1704X_STATUS_REG, 2)
    
    @voltage_low_alert.setter
    def voltage_low_alert(self, value):
        """Clear or set voltage low alert"""
        self._write_bit(_MAX1704X_STATUS_REG, 2, value)

    @property
    def voltage_reset_alert(self):
        """Voltage reset alert flag"""
        return self._read_bit(_MAX1704X_STATUS_REG, 3)
    
    @voltage_reset_alert.setter
    def voltage_reset_alert(self, value):
        """Clear or set voltage reset alert"""
        self._write_bit(_MAX1704X_STATUS_REG, 3, value)

    @property
    def SOC_low_alert(self):
        """State of charge low alert flag"""
        return self._read_bit(_MAX1704X_STATUS_REG, 4)
    
    @SOC_low_alert.setter
    def SOC_low_alert(self, value):
        """Clear or set SOC low alert"""
        self._write_bit(_MAX1704X_STATUS_REG, 4, value)

    @property
    def SOC_change_alert(self):
        """State of charge change alert flag"""
        return self._read_bit(_MAX1704X_STATUS_REG, 5)
    
    @SOC_change_alert.setter
    def SOC_change_alert(self, value):
        """Clear or set SOC change alert"""
        self._write_bit(_MAX1704X_STATUS_REG, 5, value)

    @property
    def reset_voltage(self):
        """The voltage threshold for detecting battery swap (in volts)"""
        raw = self._read_bits(_MAX1704X_VRESET_REG, 1, 7)
        return raw * 0.04  # 40mV per LSB

    @reset_voltage.setter
    def reset_voltage(self, reset_v):
        """Set the reset voltage threshold"""
        if not 0 <= reset_v <= (127 * 0.04):
            raise ValueError("Reset voltage must be between 0 and 5.08 Volts")
        value = int(reset_v / 0.04)
        self._write_bits(_MAX1704X_VRESET_REG, 1, 7, value)

    @property
    def comparator_disabled(self):
        """Whether the voltage comparator is disabled"""
        return self._read_bit(_MAX1704X_VRESET_REG, 0)
    
    @comparator_disabled.setter
    def comparator_disabled(self, value):
        """Enable or disable the voltage comparator"""
        self._write_bit(_MAX1704X_VRESET_REG, 0, value)

    @property
    def voltage_alert_min(self):
        """The minimum voltage alert threshold (in volts)"""
        raw = self._read_u8(_MAX1704X_VALERT_REG)
        return raw * 0.02  # 20mV per LSB

    @voltage_alert_min.setter
    def voltage_alert_min(self, minvoltage):
        """Set the minimum voltage alert threshold"""
        if not 0 <= minvoltage <= (255 * 0.02):
            raise ValueError("Alert voltage must be between 0 and 5.1 Volts")
        value = int(minvoltage / 0.02)
        self._write_u8(_MAX1704X_VALERT_REG, value)

    @property
    def voltage_alert_max(self):
        """The maximum voltage alert threshold (in volts)"""
        raw = self._read_u8(_MAX1704X_VALERT_REG + 1)
        return raw * 0.02  # 20mV per LSB

    @voltage_alert_max.setter
    def voltage_alert_max(self, maxvoltage):
        """Set the maximum voltage alert threshold"""
        if not 0 <= maxvoltage <= (255 * 0.02):
            raise ValueError("Alert voltage must be between 0 and 5.1 Volts")
        value = int(maxvoltage / 0.02)
        self._write_u8(_MAX1704X_VALERT_REG + 1, value)

    @property
    def activity_threshold(self):
        """Activity threshold voltage for hibernation (in volts)"""
        raw = self._read_u8(_MAX1704X_HIBRT_REG + 1)
        return raw * 0.00125  # 1.25mV per LSB

    @activity_threshold.setter
    def activity_threshold(self, threshold_voltage):
        """Set the activity threshold for hibernation"""
        if not 0 <= threshold_voltage <= (255 * 0.00125):
            raise ValueError("Activity voltage change must be between 0 and 0.31875 Volts")
        value = int(threshold_voltage / 0.00125)
        self._write_u8(_MAX1704X_HIBRT_REG + 1, value)

    @property
    def hibernation_threshold(self):
        """Hibernation threshold in percent per hour"""
        raw = self._read_u8(_MAX1704X_HIBRT_REG)
        return raw * 0.208  # 0.208% per hour

    @hibernation_threshold.setter
    def hibernation_threshold(self, threshold_percent):
        """Set the hibernation threshold"""
        if not 0 <= threshold_percent <= (255 * 0.208):
            raise ValueError("Activity percentage/hour change must be between 0 and 53%")
        value = int(threshold_percent / 0.208)
        self._write_u8(_MAX1704X_HIBRT_REG, value)


    def hibernate(self):
        """Enter hibernation mode immediately.
        
        Sets both thresholds to maximum to force hibernation.
        Check status with hibernating property.
        """
        self._write_u8(_MAX1704X_HIBRT_REG, 0xFF)
        self._write_u8(_MAX1704X_HIBRT_REG + 1, 0xFF)

    def wake(self):
        """Exit hibernation mode immediately.
        
        Sets both thresholds to zero to disable hibernation.
        Check status with hibernating property.
        """
        self._write_u8(_MAX1704X_HIBRT_REG, 0x00)
        self._write_u8(_MAX1704X_HIBRT_REG + 1, 0x00)