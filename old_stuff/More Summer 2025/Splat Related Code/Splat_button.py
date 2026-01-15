import ubluetooth
import time
import struct
import binascii
import micropython


UUID_SERVICE = ubluetooth.UUID(0xfff0)
UUID_CHARACTERISTIC_RECV = ubluetooth.UUID(0xfff4)
UUID_CHARACTERISTIC_WRITE = ubluetooth.UUID(0xfff3)


class OpenSplat():
    def __init__(self, mac_address, verbose = False):
        self._ble = ubluetooth.BLE()
        self._ble.active(True)
        
        self.mac_address = mac_address
        
        self._connection = None
        self._conn_handle = None
        self._tx_char_handle = None
        self._rx_char_handle = None
        
        self._device_info = {}
        self._date_time = None
        self._time_schedule = []
        
        # Set up IRQ handler
        self._ble.irq(self._irq_handler)
        
        # Connection state
        self.connected = False
        self._addr_type = None
        self.addr = None
        self.target_addr = None
        self._value_handle = None
        self._start_handle = None
        self._end_handle = None
        self._verbose = verbose
        
    def _irq_handler(self, event, data):
        """Handle BLE IRQ events"""
        if event == 1:  # _IRQ_CENTRAL_CONNECT
            conn_handle, addr_type, addr = data
            self._conn_handle = conn_handle
            self.connected = True
            if self._verbose: print("Splat is connected")
            
        elif event == 2:  # _IRQ_CENTRAL_DISCONNECT
            conn_handle, addr_type, addr = data
            self._conn_handle = None
            self.connected = False
            if self._verbose: print("Splat is disconnected")
            
        elif event == 3:  # _IRQ_GATTS_WRITE
            # A client has written to a characteristic or descriptor
            conn_handle, attr_handle = data
            if self._verbose: print("Write")
            
        elif event == 4:  # _IRQ_GATTS_READ_REQUEST
            # A client has issued a read
            conn_handle, attr_handle = data
            if self._verbose: print("Read requested")
            
        elif event == 5:  # _IRQ_SCAN_RESULT
            self._addr_type, self.addr, adv_type, rssi, adv_data = data
            self.target_addr = ':'.join(['%02X' % i for i in self.addr])
            if self._verbose: print(f"Scan results {self.target_addr}")
            
        elif event == 6:  # _IRQ_SCAN_DONE
            # Scan completed
            if self._verbose: print("Scan completed")
            pass
            
        elif event == 7:  # _IRQ_PERIPHERAL_CONNECT
            conn_handle, addr_type, addr = data
            addr = ':'.join(['%02X' % i for i in addr])
            
            if addr_type == self._addr_type and addr == self.target_addr:
                self._conn_handle = conn_handle
                self._ble.gattc_discover_services(self._conn_handle)
                self.connected = True
                if self._verbose: print("Connection is successful")
            
        elif event == 8:  # _IRQ_PERIPHERAL_DISCONNECT      
            # Disconnected as a peripheral
            conn_handle, addr_type, addr = data
            self._conn_handle = None
            self.connected = False
            if self._verbose: print("Peripheral disconnected")
            
        elif event == 9:  # _IRQ_GATTC_SERVICE_RESULT
            # Called for each service found by gattc_discover_services
            #if self._verbose: print("Service Result")
            conn_handle, start_handle, end_handle, uuid = data
            if uuid == UUID_SERVICE:
                self._start_handle = start_handle
                self._end_handle = end_handle
                #if self._verbose: print(f"start handle {self._start_handle} and end handle {self._end_handle}")
                
        elif event == 10:  # _IRQ_GATTC_SERVICE_DONE
            # Called once service discovery is complete
            if self._start_handle and self._end_handle:
                try:
                    self._ble.gattc_discover_characteristics(
                        self._conn_handle, self._start_handle, self._end_handle
                    )
                except Exception as e:
                    print("Error discovering characteristics:", e)
            else:
                if self._verbose: print("Failed to find required service.")
            
        elif event == 11:  # _IRQ_GATTC_CHARACTERISTIC_RESULT
            # Called for each characteristic found by gattc_discover_characteristics
            conn_handle, def_handle, value_handle, properties, uuid = data
            if uuid == UUID_CHARACTERISTIC_WRITE:
                self._tx_char_handle = value_handle
            elif uuid == UUID_CHARACTERISTIC_RECV:
                self._rx_char_handle = value_handle
                
        elif event == 12:  # _IRQ_GATTC_CHARACTERISTIC_DONE
            # Called once characteristic discovery is complete
            self._subscribe_to_recv_characteristic()
            if self._verbose: print("characteristic discovery is complete")
            
        elif event == 13:  # _IRQ_GATTC_DESCRIPTOR_RESULT
            # Called for each descriptor found by gattc_discover_descriptors
            conn_handle, dsc_handle, uuid = data
            
        elif event == 14:  # _IRQ_GATTC_DESCRIPTOR_DONE
            # Called once descriptor discovery is complete
            pass
            
        elif event == 15:  # _IRQ_GATTC_READ_RESULT
            # Called after gattc_read() completes
            conn_handle, value_handle, char_data = data
            
        elif event == 16:  # _IRQ_GATTC_READ_DONE
            # Called after gattc_read() completes
            conn_handle, value_handle, status = data
            
        elif event == 17:  # _IRQ_GATTC_WRITE_DONE

            # Called after gattc_write() completes
            conn_handle, value_handle, status = data
            
        elif event == 18:  # _IRQ_GATTC_NOTIFY
            # Called when a peripheral sends a notification or indication
            print("GATT notify ")
            conn_handle, value_handle, notify_data = data
            print("notify data", notify_data, value_handle, self._rx_char_handle)
            if value_handle == self._rx_char_handle:
                self._process_notification(notify_data)
    
    def _process_notification(self, buffer):
        """Process notifications from the Splat device"""
        if len(buffer) >= 11 and buffer[0] == 0x66 and buffer[11] == 0x99:
            value = ':'.join(['%02X' % i for i in buffer])
            print("The first oif",value)
            # Implement Protocol.decode_device_info if needed
        elif len(buffer) >= 10 and buffer[0] == 0x13 and buffer[10] == 0x31:
            value = ':'.join(['%02X' % i for i in buffer])
            print("el if",value)
            if self._verbose: print("Received date/time")
            # Implement Protocol.decode_date_time if needed
        else:
            value = buffer[-1]
            print("Final else",value)
    
    def connect(self, timeout=30):
        """Connect to the Splat device"""
        if self._verbose: print("Scanning for Splat...")
        
        # Start scanning for the device
        self.target_addr = None
        self.target_addr_type = None
        
        # Start scanning
        self._ble.gap_scan(timeout * 1000, 30000, 30000)
        
        # Wait until we find the device with the right MAC address or timeout
        start_time = time.time()
        while not self.connected and (time.time() - start_time < timeout):
            # If we found our address in the scan, try to connect
            print(".", end ="")
            if self._verbose: print(f"Found {self.target_addr}")
            if not self.target_addr is None:
                #target_addr = binascii.unhexlify(self.target_addr.replace(':', ''))
                if self.target_addr == self.mac_address:
                    if self._verbose: print(f"Found Splat, attempting to connect...")
                    mac_address = binascii.unhexlify(self.mac_address.replace(':', ''))
                    self._ble.gap_connect(self._addr_type, mac_address)
                    time.sleep(0.5)
            self.target_addr = None
            time.sleep(0.1)
        
        # Stop scanning if we haven't already
        if self._verbose: print("Stopping scanning")
        self._ble.gap_scan(None)
        
        if not self.connected:
            print(f"Failed to connect to Splat after {timeout} seconds")
            return False
        
        if self._verbose: print(f"Connection status: {self.connected}")
        
        if self._verbose: print("Connected and discovering services...")
        self._ble.gattc_discover_services(self._conn_handle)


        # Wait for service discovery and setup to complete
        start_time = time.time()
        while (self._tx_char_handle is None or self._rx_char_handle is None) and (time.time() - start_time < timeout):
            #print("waiting here")
            time.sleep(0.5)
        
        if self._tx_char_handle is None or self._rx_char_handle is None:
            print("Failed to discover required characteristics")
            self.disconnect()
            return False

        if self._verbose: print("Successfully connected to Splat!")

        return True
    
    def disconnect(self):
        """Disconnect from device"""
        if self._conn_handle is not None:
            self._ble.gap_disconnect(self._conn_handle)
            self._conn_handle = None
            self.connected = False
            if self._verbose: print("Disconnected from Splat")
    
    def is_connected(self):
        """Check if connected to device"""
        return self.connected
    
    def _subscribe_to_recv_characteristic(self):
        """Subscribe to notifications from receive characteristic"""
        if self._rx_char_handle is None:
            if self._verbose: print("Cannot subscribe: characteristic not found")
            return
        
        # Enable notifications (write 0x0001 to the CCCD)
        self._ble.gattc_write(self._conn_handle, self._rx_char_handle + 1, b'\x01\x00')
    
    def _write_command(self, data):
        """Write command to Splat device"""
        if not self.is_connected() or self._tx_char_handle is None:
            if self._verbose: print("Not connected or TX characteristic not found")
            return False
        
        try:
            self._ble.gattc_write(self._conn_handle, self._tx_char_handle, data)
            if self._verbose: print(f"Data sent: {data}")
            return True
        except Exception as e:
            print("Error sending command:", e)
            return False
    
    # Command implementations
    def keepAlive(self):
        """Keep Alive reset 3 second and 5 minute timers"""
        packet = bytearray([0x01, 0x00])
        return self._write_command(packet)
    
    def soundOff(self):
        """Turn sound off"""
        packet = bytearray([0x02, 0x00])
        return self._write_command(packet)
    
    def allLEDsOff(self):
        """Turn all LEDs Off"""
        packet = bytearray([0x03, 0x00])
        return self._write_command(packet)
    
    def allTasksOff(self):
        """Turn all tasks off"""
        packet = bytearray([0x04, 0x00])
        return self._write_command(packet)
    
    def readSwitches(self):
        """Read switch state"""
        packet = bytearray([0x05, 0x00])
        return self._write_command(packet)
    
    def readBattery(self):
        """Read Battery voltage"""
        packet = bytearray([0x06, 0x00])
        return self._write_command(packet)
    
    def identifySplat(self):
        """Identify the Splat"""
        packet = bytearray([0x00, 0x10])
        return self._write_command(packet)
    
    def setVolume(self, vol):
        """Set volume level"""
        packet = bytearray([0x01, 0x10, vol])
        return self._write_command(packet)
    
    def playSound(self, soundIndex, vol):
        """Play system sound effect"""
        packet = bytearray([0x00, 0x20, soundIndex, vol])
        return self._write_command(packet)
    
    def playRecordedSound(self, soundIndex, vol):
        """Play uploaded sound"""
        packet = bytearray([0x01, 0x20, soundIndex, vol])
        return self._write_command(packet)
    
    def LEDsOff(self, lowByte, highByte):
        """Turn LEDs off"""
        packet = bytearray([0x04, 0x20, lowByte, highByte])
        return self._write_command(packet)
    
    def setLEDs(self, lowByte, highByte, red, green, blue):
        """Set color of LED"""
        packet = bytearray([0x01, 0x50, lowByte, highByte, red, green, blue])
        return self._write_command(packet)
    
    def setLEDs(self, leds, red, green, blue):
        #leds is an array of LED
        #splat.setLEDs([1,4,5],255,0,0)
        value = 0
        for led in leds:
            value = value | 1 << led 
        packet = bytearray([0x01, 0x50, value & 0xFF , value>>8 & 0xFF , red, green, blue])
        return self._write_command(packet)
    
    
    def playLEDSequence(self, seqIndex, red, green, blue, duration, loops):
        """Play light sequence"""
        #duration is in milliseconds
        packet = bytearray([0x01, 0x60, seqIndex, red, green, blue, duration, loops])
        return self._write_command(packet)
    
    def flashLEDs(self, lowByte, highByte, red, green, blue, duration, flashes):
        """Flash LEDs"""
        packet = bytearray([0x01, 0x70, lowByte, highByte, red, green, blue, duration, flashes])
        return self._write_command(packet)

# Example usage
def test_splat():
    # Create Splat instance
    splat = OpenSplat("AB:42:00:00:1A:C4")  # Use your Splat's MAC address
    
    if splat.connect(timeout=30):
        print("Connected to Splat!")
        

        # Example commands
        #splat.identifySplat()
        #time.sleep(1)
        
        # Turn on some LEDs (example: LEDs 0 and 1)
        #splat.setLEDs(0x03, 0x00, 255, 0, 0)  # Red color
        #time.sleep(2)
        
        # Play a sound
        #splat.playRecordedSound(1, 255)  # Sound index 1, volume 100
        #time.sleep(2)
        
        
        print("playing soud")
        time.sleep(2)
        #for i in range(14):
        #splat.setLEDs(255,252,255,0,0)
        #time.sleep(2)
        splat.playSound(20,255)
        print("sound played")
        print(splat.readBattery())
        splat._write_command([0x01,0x50,0x01,0x00,0xFF,0x00,0x00])
        # Turn all LEDs off
        #splat.allLEDsOff()
        time.sleep(1)
        
        # Disconnect
        splat.disconnect()
    else:
        print("Failed to connect to Splat")

if __name__ == "__main__":
    test_splat()