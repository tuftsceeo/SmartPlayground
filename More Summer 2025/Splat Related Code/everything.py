#everything.py
import ubluetooth
import time
import binascii


UUID_SERVICE = ubluetooth.UUID(0xfff0)
UUID_CHARACTERISTIC_RECV = ubluetooth.UUID(0xfff4)
UUID_CHARACTERISTIC_WRITE = ubluetooth.UUID(0xfff3)


class OpenSplat:
    def __init__(self, mac_address, verbose=False):
        self._ble = ubluetooth.BLE()
        self._ble.active(True)
        self._ble.irq(self._irq_handler)
        
        self.mac_address = mac_address.upper()
        self._verbose = verbose
        
        # Connection state
        self.connected = False
        self._conn_handle = None
        self._tx_char_handle = None
        self._rx_char_handle = None
        self._scanning = False
        self._connecting = False
        
        # Discovery state
        self._addr_type = None
        self.addr = None
        self.target_addr = None
        self._start_handle = None
        self._end_handle = None
        
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
        """Process notifications from device"""
        if self._verbose:
            print(f"Notification: {[hex(b) for b in buffer]}")
    
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
    
    def connect(self, timeout=30):
        """Connect to the Splat device"""
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
        if self._conn_handle:
            self._ble.gap_disconnect(self._conn_handle)
        if self._scanning:
            self._ble.gap_scan(None)
        self._reset_connection_state()
    
    def is_connected(self):
        """Check connection status"""
        return self.connected
    
    # Device Commands
    def keep_alive(self):
        """Keep device connection alive"""
        return self._write_command(bytearray([0x01, 0x00]))
    
    def sound_off(self):
        """Turn sound off"""
        return self._write_command(bytearray([0x02, 0x00]))
    
    def all_leds_off(self):
        """Turn all LEDs off"""
        return self._write_command(bytearray([0x03, 0x00]))
    
    def all_tasks_off(self):
        """Turn all tasks off"""
        return self._write_command(bytearray([0x04, 0x00]))
    
    def read_switches(self):
        """Read switch states"""
        return self._write_command(bytearray([0x05, 0x00]))
    
    def read_battery(self):
        """Read battery voltage"""
        return self._write_command(bytearray([0x06, 0x00]))
    
    def identify(self):
        """Make device identify itself"""
        return self._write_command(bytearray([0x00, 0x10]))
    
    def set_volume(self, volume):
        """Set volume (0-255)"""
        return self._write_command(bytearray([0x01, 0x10, volume]))
    
    def play_sound(self, sound_index, volume=255):
        """Play system sound"""
        return self._write_command(bytearray([0x00, 0x20, sound_index, volume]))
    
    def play_recorded_sound(self, sound_index, volume=255):
        """Play uploaded sound"""
        return self._write_command(bytearray([0x01, 0x20, sound_index, volume]))
    
    def set_leds(self, leds, red, green, blue):
        """Set LED colors
        Args:
            leds: List of LED indices [0, 1, 2, ...] or bitmask value
            red, green, blue: Color values (0-255)
        """
        if isinstance(leds, list):
            # Convert LED list to bitmask
            value = 0
            for led in leds:
                value |= (1 << led)
            low_byte = value & 0xFF
            high_byte = (value >> 8) & 0xFF
        else:
            # Assume it's already a bitmask
            low_byte = leds & 0xFF
            high_byte = (leds >> 8) & 0xFF
        
        return self._write_command(bytearray([0x01, 0x50, low_byte, high_byte, red, green, blue]))
    
    def leds_off(self, leds):
        """Turn specific LEDs off
        Args:
            leds: List of LED indices or bitmask value
        """
        if isinstance(leds, list):
            value = 0
            for led in leds:
                value |= (1 << led)
            low_byte = value & 0xFF
            high_byte = (value >> 8) & 0xFF
        else:
            low_byte = leds & 0xFF
            high_byte = (leds >> 8) & 0xFF
            
        return self._write_command(bytearray([0x04, 0x20, low_byte, high_byte]))
    
    def play_led_sequence(self, seq_index, red, green, blue, duration, loops):
        """Play LED sequence
        Args:
            duration: Duration in milliseconds
        """
        return self._write_command(bytearray([0x01, 0x60, seq_index, red, green, blue, duration, loops]))
    
    def flash_leds(self, leds, red, green, blue, duration, flashes):
        """Flash LEDs
        Args:
            leds: List of LED indices or bitmask value
        """
        if isinstance(leds, list):
            value = 0
            for led in leds:
                value |= (1 << led)
            low_byte = value & 0xFF
            high_byte = (value >> 8) & 0xFF
        else:
            low_byte = leds & 0xFF
            high_byte = (leds >> 8) & 0xFF
            
        return self._write_command(bytearray([0x01, 0x70, low_byte, high_byte, red, green, blue, duration, flashes]))


# Simple usage example
def main():
    splat = OpenSplat("AB:42:00:00:B2:16")
    splat.connect()
    try:
        for i in range(100):
            if splat.connect():
                # Basic demo
                #splat.identify()
                time.sleep(1)
                
                splat.set_leds([0, 1], i*255, (i*50)*255%255, 0)  # Red LEDs
                time.sleep(2)
                
                splat.play_sound(i, 255)
                time.sleep(1)
                
                splat.all_leds_off()
        else:
            print("Connection failed")
    finally:
        splat.disconnect()


if __name__ == "__main__":
    main()
    