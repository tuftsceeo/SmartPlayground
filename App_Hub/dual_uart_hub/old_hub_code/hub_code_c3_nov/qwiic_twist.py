"""
Fixed QwiicTwist class using direct I2C (no qwiic_i2c dependency)
Based on working direct I2C communication
"""
from machine import I2C, Pin
import struct

class QwiicTwist:
    def __init__(self, i2c_driver=None, address=0x3F):
        self.address = address
        
        if i2c_driver is None:
            # Use working I2C setup
            self._i2c = I2C(0, sda=Pin(6), scl=Pin(7), freq=100000)
        else:
            self._i2c = i2c_driver
    
    @property
    def connected(self):
        """Check if device is connected"""
        try:
            self._i2c.writeto(self.address, b'')
            return True
        except:
            return False
    
    def begin(self):
        """Initialize - just check connection"""
        return self.connected
    
    def set_color(self, red, green, blue):
        """Set LED color"""
        self._i2c.writeto_mem(self.address, 0x0D, bytes([int(red)]))   # Red
        self._i2c.writeto_mem(self.address, 0x0E, bytes([int(green)])) # Green  
        self._i2c.writeto_mem(self.address, 0x0F, bytes([int(blue)]))  # Blue
    
    @property
    def count(self):
        """Get encoder count"""
        lsb = self._i2c.readfrom_mem(self.address, 0x05, 1)[0]
        msb = self._i2c.readfrom_mem(self.address, 0x06, 1)[0]
        return struct.unpack('>h', bytes([msb, lsb]))[0]
    
    @count.setter
    def count(self, value):
        """Set encoder count"""
        data = struct.pack('>h', int(value))
        self._i2c.writeto_mem(self.address, 0x05, bytes([data[1]]))  # LSB
        self._i2c.writeto_mem(self.address, 0x06, bytes([data[0]]))  # MSB
    
    @property
    def pressed(self):
        """Check if button is currently pressed"""
        status = self._i2c.readfrom_mem(self.address, 0x01, 1)[0]
        return (status >> 1) & 0x01  # Bit 1 = buttonPressed
    
    @property
    def clicked(self):
        """Check if button was clicked (and clear the flag)"""
        status = self._i2c.readfrom_mem(self.address, 0x01, 1)[0]
        clicked = (status >> 2) & 0x01  # Bit 2 = buttonClicked
        
        # Clear the clicked bit
        if clicked:
            new_status = status & ~(1 << 2)
            self._i2c.writeto_mem(self.address, 0x01, bytes([new_status]))
            
        return clicked