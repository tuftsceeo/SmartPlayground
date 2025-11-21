
from machine import SoftI2C, Pin
import time

# I2C address of the device
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

# Accl Datarate configuration
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

# Accl Data update & Axis configuration
H3LIS331DL_ACCL_LPEN = 0x00       # Normal Mode, Axis disabled
H3LIS331DL_ACCL_XAXIS = 0x04      # X-Axis enabled
H3LIS331DL_ACCL_YAXIS = 0x02      # Y-Axis enabled
H3LIS331DL_ACCL_ZAXIS = 0x01      # Z-Axis enabled

# Acceleration Full-scale selection
H3LIS331DL_ACCL_BDU_CONT = 0x00      # Continuous update, Normal Mode, 4-Wire Interface, LSB first
H3LIS331DL_ACCL_BDU_NOT_CONT = 0x80  # Output registers not updated until MSB and LSB reading
H3LIS331DL_ACCL_BLE_MSB = 0x40       # MSB first
H3LIS331DL_ACCL_RANGE_400G = 0x30    # Full scale = +/-400g
H3LIS331DL_ACCL_RANGE_200G = 0x10    # Full scale = +/-200g
H3LIS331DL_ACCL_RANGE_100G = 0x00    # Full scale = +/-100g
H3LIS331DL_ACCL_SIM_3 = 0x01         # 3-Wire Interface
H3LIS331DL_RAW_DATA_MAX = 65536

H3LIS331DL_DEFAULT_RANGE = H3LIS331DL_ACCL_RANGE_100G
H3LIS331DL_SCALE_FS = H3LIS331DL_RAW_DATA_MAX / 4 / ((H3LIS331DL_DEFAULT_RANGE >> 4) + 1)

class H3LIS331DL:
    def __init__(self, i2c, address=H3LIS331DL_DEFAULT_ADDRESS):
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
        
        return(xAccl/ H3LIS331DL_SCALE_FS, yAccl/ H3LIS331DL_SCALE_FS, zAccl/ H3LIS331DL_SCALE_FS)



# Example usage
def demo():
    i2c = SoftI2C(scl = Pin(23), sda = Pin(22))

    h3lis331dl = H3LIS331DL(i2c)
    data = []
    h3lis331dl.select_datarate()
    h3lis331dl.select_data_config()
    
    while True:
        accl = h3lis331dl.read_accl()
        print("{0:6.3f},{1:6.3f},{2:6.3f}".format(accl['x'] / H3LIS331DL_SCALE_FS, accl['y'] / H3LIS331DL_SCALE_FS, accl['z'] / H3LIS331DL_SCALE_FS))
        time.sleep(0.5)

