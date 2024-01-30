import bluetooth
import time
import struct

NAME_FLAG = 0x09
SCAN_RESULT = 5
SCAN_DONE = 6
NAME_FLAG = 0x09
ADV_TYPE_UUID128_COMPLETE = 0x07
IRQ_CENTRAL_CONNECT = 1
IRQ_CENTRAL_DISCONNECT = 2
IRQ_GATTS_WRITE = 3

UART_SERVICE_UUID = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
UART_RX_CHAR_UUID = bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E")
UART_TX_CHAR_UUID = bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E")

FLAG_READ = 0x0002
FLAG_WRITE_NO_RESPONSE = 0x0004
FLAG_WRITE = 0x0008
FLAG_NOTIFY = 0x0010

UART_UUID = UART_SERVICE_UUID
UART_TX = (UART_TX_CHAR_UUID, FLAG_READ | FLAG_NOTIFY,)
UART_RX = (UART_RX_CHAR_UUID, FLAG_WRITE | FLAG_WRITE_NO_RESPONSE,)
UART_SERVICE = (UART_UUID,(UART_TX, UART_RX),)


class Yell:  #peripheral
    def __init__(self):
        self._ble = bluetooth.BLE()
        self._ble.active(True)
        # register a UART service
        ((self._handle_tx, self._handle_rx),) = self._ble.gatts_register_services((UART_SERVICE,))
        services = [UART_UUID]
        print('setup as uart')
        self._connections = set()
        self._write_callback = None 
        self._ble.irq(self._irq)   
        self._write_callback = self.on_rx    
        
    def advertise(self, name = 'Pico', interval_us=10000):
        short = name[:8]
        payload = struct.pack("BB", len(short) + 1, NAME_FLAG) + short  # byte length, byte type, value
        value = bytes(UART_UUID)
        payload += struct.pack("BB", len(value) + 1,ADV_TYPE_UUID128_COMPLETE) + value

        self._ble.gap_advertise(interval_us, adv_data=payload)
        
    def stop_advertising(self):
        self._ble.gap_advertise(None)
        
    def _irq(self, event, data):  # Track connections so we can send notifications.
        if event == IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            print("New connection", conn_handle)
            self._connections.add(conn_handle)
            self.stop_advertising() #only hve one connection
            
        elif event == IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            print("Disconnected", conn_handle)
            self._connections.remove(conn_handle)
            self._write_callback = None
            # Start advertising again to allow a new connection.
            #self._advertise()
            
        elif event == IRQ_GATTS_WRITE:
            conn_handle, value_handle = data
            value = self._ble.gatts_read(value_handle)
            if value_handle == self._handle_rx and self._write_callback:
                self._write_callback(value)

    def on_rx(self,v):
        print("received ", v)
        print(self.send(v))  # echo back

    def send(self, data):
        for conn_handle in self._connections:
            self._ble.gatts_notify(conn_handle, self._handle_tx, data)

    def is_connected(self):
        return len(self._connections) > 0
        
    def disconnect(self):
        for conn_handle in self._connections:
            self._ble.gap_disconnect(conn_handle)

p = Yell()
p.advertise('!Fred')

while not p.is_connected():
    time.sleep(0.5)
    
p.stop_advertising()
time.sleep(2)
for i in range(10):
    p.send(str(i) + chr(i))
    time.sleep(1)

p.disconnect()

