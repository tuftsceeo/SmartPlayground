
# BLE_CEEO Library - Simplified BLE UART
from micropython import const
import bluetooth
import time

_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)

_FLAG_WRITE = const(0x0008)
_FLAG_NOTIFY = const(0x0010)

_UART_UUID = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
_UART_TX = (bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E"), _FLAG_NOTIFY,)
_UART_RX = (bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E"), _FLAG_WRITE,)
_UART_SERVICE = (_UART_UUID, (_UART_TX, _UART_RX,),)

class Yell:
    """BLE UART Peripheral (Server)"""
    def __init__(self, name="ESP32", interval_us=30000, verbose=False):
        self.name = name
        self.verbose = verbose
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.ble.irq(self._irq)
        
        ((self._tx_handle, self._rx_handle),) = self.ble.gatts_register_services((_UART_SERVICE,))
        
        self._connections = set()
        self.callback = None
        self._payload = b""
        
        # Start advertising
        self._advertise(interval_us)
    
    def _irq(self, event, data):
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            self._connections.add(conn_handle)
            if self.verbose:
                print(f"Connected: {conn_handle}")
        
        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            self._connections.discard(conn_handle)
            if self.verbose:
                print(f"Disconnected: {conn_handle}")
            # Start advertising again
            self._advertise()
        
        elif event == _IRQ_GATTS_WRITE:
            conn_handle, value_handle = data
            if conn_handle in self._connections and value_handle == self._rx_handle:
                value = self.ble.gatts_read(self._rx_handle)
                if self.callback:
                    self.callback(value)
    
    def _advertise(self, interval_us=30000):
        """Start BLE advertising"""
        self.ble.gap_advertise(interval_us, adv_data=self._advertising_payload())
    
    def _advertising_payload(self):
        """Create advertising payload with device name"""
        payload = bytearray()
        
        # Flags
        payload.extend(b'\x02\x01\x06')
        
        # Complete local name
        name_bytes = self.name.encode()
        payload.extend(bytes([len(name_bytes) + 1, 0x09]) + name_bytes)
        
        # Service UUID - 16 bytes for 128-bit UUID
        # Format: length (17), type (0x07 for complete 128-bit), then 16 UUID bytes
        uuid_bytes = bytes([
            0x11, 0x07,  # length=17, type=complete 128-bit UUID
            0x9E, 0xCA, 0xDC, 0x24, 0x0E, 0xE5, 0xA9, 0xE0,
            0x93, 0xF3, 0xA3, 0xB5, 0x01, 0x00, 0x40, 0x6E
        ])
        payload.extend(uuid_bytes)
        
        return bytes(payload)
    
    def send(self, data):
        """Send data to all connected clients"""
        if not isinstance(data, bytes):
            data = str(data).encode()
        
        for conn_handle in self._connections:
            try:
                self.ble.gatts_notify(conn_handle, self._tx_handle, data)
            except Exception as e:
                if self.verbose:
                    print(f"Send error to {conn_handle}: {e}")
    
    def connect_up(self, timeout=30):
        """Wait for a connection"""
        if self.verbose:
            print(f"Waiting for connection to '{self.name}'...")
        
        start = time.time()
        while not self._connections:
            if time.time() - start > timeout:
                if self.verbose:
                    print("Connection timeout")
                return False
            time.sleep(0.1)
        
        if self.verbose:
            print("Connected!")
        return True
    
    @property
    def is_connected(self):
        """Check if any device is connected"""
        return len(self._connections) > 0
    
    def disconnect(self):
        """Disconnect all clients and stop advertising"""
        for conn_handle in list(self._connections):
            try:
                self.ble.gap_disconnect(conn_handle)
            except:
                pass
        self._connections.clear()
        self.ble.gap_advertise(None)
        self.ble.active(False)

class Listen:
    """BLE UART Central (Client) - for scanning/connecting to peripherals"""
    # Placeholder for future implementation
    pass
