## ble_splat.py 
import ubluetooth
import time
import struct
import binascii
import micropython
import config

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
        
        self.on_splat_pressed = None  # Callback function
        
        self.sound = config.sound
        self.volume = config.volume
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
        
        #button variables
        self.button1_pressed = False
        self.button2_pressed = False
        self.button3_pressed = False
        self.button4_pressed = False
        self.splat_pressed = False
    
    



            
        
    def _irq_handler(self, event, data):
        """Handle BLE IRQ events"""
        if event == 1:  # _IRQ_CENTRAL_CONNECT
            conn_handle, addr_type, addr = data
            self._conn_handle = conn_handle
            self.connected = True
            if self._verbose: print("Connected as central")
            
        elif event == 2:  # _IRQ_CENTRAL_DISCONNECT
            self._reset_connection_state()
            if self._verbose: print("Disconnected")
            
        elif event == 5:  # _IRQ_SCAN_RESULT
            self._addr_type, self.addr, adv_type, rssi, adv_data = data
            self.target_addr = ':'.join(['%02X' % i for i in self.addr])
            
            if self._verbose: print(f"Found: {self.target_addr} (RSSI: {rssi})")
            
            if self.target_addr == self.mac_address and not self._connecting:
                self._ble.gap_scan(None)
                self._scanning = False
                self._connecting = True
                try:
                    self._ble.gap_connect(self._addr_type, self.addr)
                    if self._verbose: print("Connecting...")
                except Exception as e:
                    print(f"Connection failed: {e}")
                    self._connecting = False
            
        elif event == 6:  # _IRQ_SCAN_DONE
            self._scanning = False
            if self._verbose: print("Scan complete")
            
        elif event == 7:  # _IRQ_PERIPHERAL_CONNECT
            conn_handle, addr_type, addr = data
            addr_str = ':'.join(['%02X' % i for i in addr])
            
            if addr_str == self.mac_address:
                self._conn_handle = conn_handle
                self.connected = True
                self._connecting = False
                if self._verbose: print("Connected! Discovering services...")
                self._ble.gattc_discover_services(self._conn_handle)
            
        elif event == 8:  # _IRQ_PERIPHERAL_DISCONNECT
            self._reset_connection_state()
            if self._verbose: print("Peripheral disconnected")
            
        elif event == 9:  # _IRQ_GATTC_SERVICE_RESULT
            conn_handle, start_handle, end_handle, uuid = data
            if uuid == UUID_SERVICE:
                self._start_handle = start_handle
                self._end_handle = end_handle
                if self._verbose: print(f"Service found: {start_handle}-{end_handle}")
                
        elif event == 10:  # _IRQ_GATTC_SERVICE_DONE
            if self._start_handle and self._end_handle:
                self._ble.gattc_discover_characteristics(
                    self._conn_handle, self._start_handle, self._end_handle
                )
            else:
                print("Required service not found")
            
        elif event == 11:  # _IRQ_GATTC_CHARACTERISTIC_RESULT
            conn_handle, def_handle, value_handle, properties, uuid = data
            if uuid == UUID_CHARACTERISTIC_WRITE:
                self._tx_char_handle = value_handle
            elif uuid == UUID_CHARACTERISTIC_RECV:
                self._rx_char_handle = value_handle
                
        elif event == 12:  # _IRQ_GATTC_CHARACTERISTIC_DONE
            if self._rx_char_handle:
                self._subscribe_to_notifications()
            if self._verbose: print("Setup complete!")
            
        elif event == 17:  # _IRQ_GATTC_WRITE_DONE
            conn_handle, value_handle, status = data
            if self._verbose and status != 0:
                print(f"Write error: {status}")
            
        elif event == 18:  # _IRQ_GATTC_NOTIFY
            conn_handle, value_handle, notify_data = data
            if value_handle == self._rx_char_handle:
                self._process_notification(notify_data)
    
    def _reset_connection_state(self):
        """Reset all connection-related state"""
        self.connected = False
        self._conn_handle = None
        self._connecting = False
        self._tx_char_handle = None
        self._rx_char_handle = None
        self._start_handle = None
        self._end_handle = None
    
    def _process_notification(self, buffer):
        sound = 0
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
            data = [d for d in buffer]
            #print("return set of data", data)
            if (data[0] == 3 and len(data)==3):
                sound = self.decode_button(data[2])
            else:
                pass
                #print("something else came through")

            
            #if sound:
            #    self.playSound(sound,255)
    def _subscribe_to_notifications(self):
        """Subscribe to device notifications"""
        if self._rx_char_handle:
            try:
                self._ble.gattc_write(self._conn_handle, self._rx_char_handle + 1, b'\x01\x00')
                if self._verbose: print("Subscribed to notifications")
            except Exception as e:
                print(f"Subscription failed: {e}")
    
    def _write_command(self, data):
        """Send command to device"""
        if not self.connected or not self._tx_char_handle:
            print("Device not ready")
            return False
        
        try:
            self._ble.gattc_write(self._conn_handle, self._tx_char_handle, data)
            if self._verbose: print(f"Sent: {[hex(b) for b in data]}")
            return True
        except Exception as e:
            print(f"Send error: {e}")
            return False
    
    def decode_button(self,value):
        sound = 0
        was_pressed = self.splat_pressed  # Remember previous state
        
        if(value & 0b1000 or value & 0b0100 or value & 0b0010 or value & 0b0001):
            self.playSound(self.sound, self.volume)
            self.splat_pressed = True
            print("ble splat pressed")
            
            # Only call callback on NEW press (transition from False to True)
            if not was_pressed and self.on_splat_pressed:
                self.on_splat_pressed()

        if(value == 0):
            self.splat_pressed = False
            sound = 0
        
        return sound
       
    def connect(self, timeout=30):
        """Connect to the Splat device"""
        self._ble.active(True) 
        if self.connected:
            return True
            
        print(f"Connecting to {self.mac_address}...")
        self._reset_connection_state()
        
        # Start scanning
        self._scanning = True
        self._ble.gap_scan(0, 30000, 30000)
        
        # Wait for connection
        start_time = time.time()
        while not self.connected and (time.time() - start_time < timeout):
            if not self._scanning and not self._connecting:
                # Restart scan if needed
                self._scanning = True
                self._ble.gap_scan(0, 30000, 30000)
            
            print(".", end="")
            time.sleep(0.5)
        
        # Stop scanning
        if self._scanning:
            self._ble.gap_scan(None)
            self._scanning = False
        
        if not self.connected:
            print(f"\nConnection timeout after {timeout}s")
            return False
        
        # Wait for service setup
        start_time = time.time()
        while (not self._tx_char_handle or not self._rx_char_handle) and (time.time() - start_time < 10):
            time.sleep(0.5)
        
        if not self._tx_char_handle or not self._rx_char_handle:
            print("\nService setup failed")
            self.disconnect()
            return False

        print("\nConnected successfully!")
        return True

    
    def disconnect(self):
        """Disconnect from device"""
        if self._conn_handle is not None:
            self._ble.gap_disconnect(self._conn_handle)
            self._conn_handle = None
            self.connected = False
            if self._verbose: print("Disconnected from Splat")
            self._ble.active(False)  # Then deactivate the radio
    
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
    
    
    def setLEDsON(self): #test
        packet = bytearray([0x01, 0x50, 0xFF, 0x3F , config.red, config.green, config.blue])
        return self._write_command(packet)

    #def setLEDs(self, leds, red, green, blue): # original
    def setLEDs(self, leds, red, green, blue):    #test
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
