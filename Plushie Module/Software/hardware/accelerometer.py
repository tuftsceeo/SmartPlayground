"""
Educational Module System - Accelerometer Interface
-------------------------------------------------
This module provides an interface for the H3LIS331DL 3-axis accelerometer.
"""
import machine
from machine import Pin, SoftI2C
import math

# I2C address and constants for the H3LIS331DL accelerometer
H3LIS331DL_DEFAULT_ADDRESS = 0x19

# H3LIS331DL Register Map
H3LIS331DL_REG_WHOAMI = 0x0F      # Who Am I Register
H3LIS331DL_REG_CTRL1 = 0x20       # Control Register-1
H3LIS331DL_REG_CTRL2 = 0x21       # Control Register-2
H3LIS331DL_REG_CTRL3 = 0x22       # Control Register-3
H3LIS331DL_REG_CTRL4 = 0x23       # Control Register-4
H3LIS331DL_REG_CTRL5 = 0x24       # Control Register-5
H3LIS331DL_REG_REFERENCE = 0x26   # Reference
H3LIS331DL_REG_STATUS = 0x27      # Status Register
H3LIS331DL_REG_OUT_X_L = 0x28     # X-Axis LSB
H3LIS331DL_REG_OUT_X_H = 0x29     # X-Axis MSB
H3LIS331DL_REG_OUT_Y_L = 0x2A     # Y-Axis LSB
H3LIS331DL_REG_OUT_Y_H = 0x2B     # Y-Axis MSB
H3LIS331DL_REG_OUT_Z_L = 0x2C     # Z-Axis LSB
H3LIS331DL_REG_OUT_Z_H = 0x2D     # Z-Axis MSB

# Accelerometer configuration constants
H3LIS331DL_ACCL_PM_PD = 0x00      # Power down Mode
H3LIS331DL_ACCL_PM_NRMl = 0x20    # Normal Mode
H3LIS331DL_ACCL_PM_0_5 = 0x40     # Low-Power Mode, ODR = 0.5Hz
H3LIS331DL_ACCL_PM_1 = 0x60       # Low-Power Mode, ODR = 1Hz
H3LIS331DL_ACCL_PM_2 = 0x80       # Low-Power Mode, ODR = 2Hz
H3LIS331DL_ACCL_PM_5 = 0xA0       # Low-Power Mode, ODR = 5Hz
H3LIS331DL_ACCL_PM_10 = 0xC0      # Low-Power Mode, ODR = 10Hz
H3LIS331DL_ACCL_DR_50 = 0x00      # ODR = 50Hz
H3LIS331DL_ACCL_DR_100 = 0x08     # ODR = 100Hz
H3LIS331DL_ACCL_DR_400 = 0x10     # ODR = 400Hz
H3LIS331DL_ACCL_DR_1000 = 0x18    # ODR = 1000Hz

# Axis configuration
H3LIS331DL_ACCL_LPEN = 0x00       # Normal Mode, Axis disabled
H3LIS331DL_ACCL_XAXIS = 0x04      # X-Axis enabled
H3LIS331DL_ACCL_YAXIS = 0x02      # Y-Axis enabled
H3LIS331DL_ACCL_ZAXIS = 0x01      # Z-Axis enabled

# Acceleration scale selection
H3LIS331DL_ACCL_BDU_CONT = 0x00      # Continuous update
H3LIS331DL_ACCL_BDU_NOT_CONT = 0x80  # Output registers not updated until MSB and LSB reading
H3LIS331DL_ACCL_BLE_MSB = 0x40       # MSB first
H3LIS331DL_ACCL_RANGE_400G = 0x30    # Full scale = +/-400g
H3LIS331DL_ACCL_RANGE_200G = 0x10    # Full scale = +/-200g
H3LIS331DL_ACCL_RANGE_100G = 0x00    # Full scale = +/-100g
H3LIS331DL_ACCL_SIM_3 = 0x01         # 3-Wire Interface
H3LIS331DL_RAW_DATA_MAX = 65536

# Default configuration
H3LIS331DL_DEFAULT_RANGE = H3LIS331DL_ACCL_RANGE_100G
H3LIS331DL_SCALE_FS = H3LIS331DL_RAW_DATA_MAX / 4 / ((H3LIS331DL_DEFAULT_RANGE >> 4) + 1)

class H3LIS331DL:
    """Interface for the H3LIS331DL 3-axis accelerometer"""
    
    def __init__(self, i2c, address=H3LIS331DL_DEFAULT_ADDRESS):
        """Initialize the accelerometer.
        
        Args:
            i2c: I2C interface
            address: I2C address of the accelerometer
        """
        self._addr = address
        self._i2c = i2c
        self.select_datarate()
        self.select_data_config()
    
    def _write_register(self, register, value):
        """Write a byte to the specified register"""
        self._i2c.writeto_mem(self._addr, register, bytes([value]))
    
    def _read_register(self, register):
        """Read a byte from the specified register"""
        return self._i2c.readfrom_mem(self._addr, register, 1)[0]
    
    def select_datarate(self):
        """Select the data rate of the accelerometer from the given provided values"""
        DATARATE_CONFIG = (H3LIS331DL_ACCL_PM_NRMl | H3LIS331DL_ACCL_DR_50 | 
                           H3LIS331DL_ACCL_XAXIS | H3LIS331DL_ACCL_YAXIS | H3LIS331DL_ACCL_ZAXIS)
        self._write_register(H3LIS331DL_REG_CTRL1, DATARATE_CONFIG)
    
    def select_data_config(self):
        """Select the data configuration of the accelerometer from the given provided values"""
        DATA_CONFIG = (H3LIS331DL_DEFAULT_RANGE | H3LIS331DL_ACCL_BDU_CONT)
        self._write_register(H3LIS331DL_REG_CTRL4, DATA_CONFIG)
    
    def read_accl(self):
        """Read data from accelerometer and return X, Y, Z acceleration values"""
        # Read X-axis data
        data0 = self._read_register(H3LIS331DL_REG_OUT_X_L)
        data1 = self._read_register(H3LIS331DL_REG_OUT_X_H)
        
        xAccl = data1 * 256 + data0
        if xAccl > H3LIS331DL_RAW_DATA_MAX / 2:
            xAccl -= H3LIS331DL_RAW_DATA_MAX
        
        # Read Y-axis data
        data0 = self._read_register(H3LIS331DL_REG_OUT_Y_L)
        data1 = self._read_register(H3LIS331DL_REG_OUT_Y_H)
        
        yAccl = data1 * 256 + data0
        if yAccl > H3LIS331DL_RAW_DATA_MAX / 2:
            yAccl -= H3LIS331DL_RAW_DATA_MAX
        
        # Read Z-axis data
        data0 = self._read_register(H3LIS331DL_REG_OUT_Z_L)
        data1 = self._read_register(H3LIS331DL_REG_OUT_Z_H)
        
        zAccl = data1 * 256 + data0
        if zAccl > H3LIS331DL_RAW_DATA_MAX / 2:
            zAccl -= H3LIS331DL_RAW_DATA_MAX
        
        return {'x': xAccl, 'y': yAccl, 'z': zAccl}
    
    def read_g(self):
        """Read accelerometer values in g units"""
        accl = self.read_accl()
        return {
            'x': accl['x'] / H3LIS331DL_SCALE_FS,
            'y': accl['y'] / H3LIS331DL_SCALE_FS,
            'z': accl['z'] / H3LIS331DL_SCALE_FS
        }

class Accelerometer:
    """Interface for the 3-axis accelerometer"""
    
    # Orientation constants
    ORIENTATION_UP = "UP"
    ORIENTATION_DOWN = "DOWN"
    ORIENTATION_LEFT = "LEFT"
    ORIENTATION_RIGHT = "RIGHT"
    ORIENTATION_FRONT = "FRONT"
    ORIENTATION_BACK = "BACK"
    
    def __init__(self, scl_pin=23, sda_pin=22):
        """Initialize the accelerometer.
        
        Args:
            scl_pin: I2C SCL pin
            sda_pin: I2C SDA pin
        """
        self.i2c = SoftI2C(scl=Pin(scl_pin), sda=Pin(sda_pin))
        
        # Check available I2C devices
        devices = self.i2c.scan()
        self.available = H3LIS331DL_DEFAULT_ADDRESS in devices
        
        if self.available:
            self.sensor = H3LIS331DL(self.i2c)
            # Initialize with default configuration
            self.sensor.select_datarate()
            self.sensor.select_data_config()
            
            # Data for shake detection
            self.last_reading = {'x': 0, 'y': 0, 'z': 0}
            self.shake_threshold = 0.5  # g units
            self.movement_threshold = 0.1  # g units
        else:
            print("H3LIS331DL accelerometer not found!")
    
    def read_raw(self):
        """Read raw accelerometer values"""
        if not self.available:
            return {'x': 0, 'y': 0, 'z': 0}
        
        return self.sensor.read_accl()
    
    def read_g(self):
        """Read accelerometer values in g units"""
        if not self.available:
            return {'x': 0, 'y': 0, 'z': 0}
        
        return self.sensor.read_g()
    
    def get_orientation(self):
        """Determine the current orientation"""
        if not self.available:
            return self.ORIENTATION_UP
        
        accel = self.read_g()
        x, y, z = accel['x'], accel['y'], accel['z']
        
        # Simple orientation detection based on dominant axis
        if z > 0.7:
            return self.ORIENTATION_UP
        elif z < -0.7:
            return self.ORIENTATION_DOWN
        elif x > 0.7:
            return self.ORIENTATION_RIGHT
        elif x < -0.7:
            return self.ORIENTATION_LEFT
        elif y > 0.7:
            return self.ORIENTATION_FRONT
        elif y < -0.7:
            return self.ORIENTATION_BACK
        else:
            return self.ORIENTATION_UP  # Default if no orientation is dominant
    
    def get_tilt_angles(self):
        """Get tilt angles in degrees for each axis"""
        if not self.available:
            return (0, 0, 0)
        
        accel = self.read_g()
        x, y, z = accel['x'], accel['y'], accel['z']
        
        # Convert g values to angles in degrees
        angle_x = math.atan2(x, math.sqrt(y*y + z*z)) * 180 / math.pi
        angle_y = math.atan2(y, math.sqrt(x*x + z*z)) * 180 / math.pi
        angle_z = math.atan2(z, math.sqrt(x*x + y*y)) * 180 / math.pi
        
        return (angle_x, angle_y, angle_z)
    
    def detect_shake(self):
        """Detect shaking and return shake intensity (0-100)"""
        if not self.available:
            return 0
        
        current = self.read_g()
        last = self.last_reading
        
        # Calculate movement magnitude across all axes
        delta_sq = (current['x'] - last['x'])**2 + (current['y'] - last['y'])**2 + (current['z'] - last['z'])**2
        
        self.last_reading = current
        
        # Scale to 0-100 intensity range
        if delta_sq < self.movement_threshold:
            return 0
        
        intensity = min(100, int(delta_sq * 100 / self.shake_threshold))
        return intensity
    
    def detect_movement(self):
        """Detect general movement and return intensity (0-100)"""
        if not self.available:
            return 0
        
        current = self.read_g()
        last = self.last_reading
        
        # Calculate movement magnitude across all axes
        delta_sq = (current['x'] - last['x'])**2 + (current['y'] - last['y'])**2 + (current['z'] - last['z'])**2
        
        self.last_reading = current
        
        # Scale to 0-100 intensity range with lower threshold than shake
        intensity = min(100, int(delta_sq * 100 / self.movement_threshold))
        return intensity 