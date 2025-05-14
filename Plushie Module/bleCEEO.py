import bluetooth
import time
import struct
import micropython
micropython.alloc_emergency_exception_buf(128)

NAME_FLAG = 0x09
SCAN_RESULT = 5
SCAN_DONE = 6
NAME_FLAG = 0x09
ADV_TYPE_UUID128_COMPLETE = 0x07
ADV_IND = 0x00
ADV_DIRECT_IND = 0x01

IRQ_CENTRAL_CONNECT = 1
IRQ_CENTRAL_DISCONNECT = 2
IRQ_GATTS_WRITE = 3
IRQ_GATTS_READ_REQUEST = 4
IRQ_SCAN_RESULT = 5
IRQ_SCAN_DONE = 6
IRQ_PERIPHERAL_CONNECT = 7
IRQ_PERIPHERAL_DISCONNECT = 8
IRQ_GATTC_SERVICE_RESULT = 9
IRQ_GATTC_SERVICE_DONE = 10
IRQ_GATTC_CHARACTERISTIC_RESULT = 11
IRQ_GATTC_CHARACTERISTIC_DONE = 12
IRQ_GATTC_DESCRIPTOR_RESULT = 13
IRQ_GATTC_DESCRIPTOR_DONE = 14
IRQ_GATTC_READ_RESULT = 15
IRQ_GATTC_READ_DONE = 16
IRQ_GATTC_WRITE_DONE = 17
IRQ_GATTC_NOTIFY = 18
IRQ_GATTC_INDICATE = 19

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

MIDI_SERVICE_UUID = bluetooth.UUID("03B80E5A-EDE8-4B33-A751-6CE34EC4C700")
MIDI_CHAR_UUID = bluetooth.UUID("7772E5DB-3868-4112-A1A9-F2669D106BF3")

MIDI_UUID = MIDI_SERVICE_UUID
MIDI_TXRX = (MIDI_CHAR_UUID, FLAG_READ | FLAG_NOTIFY | FLAG_WRITE_NO_RESPONSE,)
MIDI_SERVICE = (MIDI_UUID,(MIDI_TXRX,),)

class Useful:
    def setup(self, name, verbose, callback):
        self._ble = bluetooth.BLE()
        self._ble.active(True)
        self._ble.irq(callback)
        self.name = name
        self.string = b''
        self.is_any = 0
        self.verbose = verbose
        self.is_connected = False
    
    def wait_for_connection(self, timeout = -1):
        start =  time.ticks_ms()
        done = False
        while not done:
            done = self.is_connected
            if not done and timeout >= 0:
                done = (time.ticks_ms()-start) >= timeout
            time.sleep(0.1)
            if self.verbose:
                print('.',end='')
        return self.is_connected
        
    def rx(self, data):
        #self.printIt("Received: " + str(bytes(data)))
        self.buffer(data)
        
    def buffer(self, value):
        self.string = self.string + bytes(value)
        self.is_any = len(self.string)

        
    def read(self):
        if self.is_any:
            try:
                temp = self.string.decode()
                self.string = b''
                self.is_any = 0
                #print("string and any", self.string, self.is_any)
                return temp
            except Exception as e:
                print('error', e)
                return ''
        else: 
            return ''
            
    def printIt(self, data):
        if self.verbose:
            print(data)
        
#----------------Central---------------------------------
class Listen(Useful):   # central
    def __init__(self, name = None, verbose = True): 
        self.setup(name, verbose, self._irq)
        self._reset()

    def _reset(self):
        # Cached name and address from a successful scan.
        self._name = None
        self._addr_type = None
        self._addr = None
        self.addresses = set()
        self._conn_callback = self.connected
        # self._read_callback = None
        self._notify_callback = self.rx
        self._conn_handle = None
        self._start_handle = None
        self._end_handle = None
        self._tx_handle = None
        self._rx_handle = None
        self.is_connected = False 
        self.scanning = False 
        self.found = False    

    def _irq(self, event, data):
        if event == IRQ_SCAN_RESULT: #check to see if it is a serial peripheral
            if self.uart_check(data):
                self._ble.gap_scan(None)#stop scanning

        elif event == IRQ_SCAN_DONE:  # close everything
            self.scanning = False

        elif event == IRQ_PERIPHERAL_CONNECT:  # ask for services
            self.printIt('\nConnect successful.')
            conn_handle, addr_type, addr = data
            if addr_type == self._addr_type and addr == self._addr:
                self._conn_handle                 = conn_handle
                self._ble.gattc_discover_services(self._conn_handle)
                self.printIt('Got a connection handle: ' + str(conn_handle))
    
        elif event == IRQ_PERIPHERAL_DISCONNECT:
            # Disconnect (either initiated by us or the remote end).
            conn_handle, _, _ = data
            self.printIt('Disconnected: '+str(conn_handle))
            if conn_handle == self._conn_handle:
                # If it was initiated by us, it'll already be reset.
                self._reset()
    
        elif event == IRQ_GATTC_SERVICE_RESULT:  # read the service
            self.printIt('Connected device returned a service.')
            conn_handle, start_handle, end_handle, uuid = data
            if conn_handle == self._conn_handle and uuid == UART_SERVICE_UUID:
                self._start_handle, self._end_handle = start_handle, end_handle
                self.printIt('Got start and end handles: ' + str(start_handle) + ' ' + str(end_handle))
            
        elif event == IRQ_GATTC_SERVICE_DONE:  #ask for characteristics
            self.printIt('Service query complete.')
            if self._start_handle and self._end_handle:
                self._ble.gattc_discover_characteristics(self._conn_handle, self._start_handle, self._end_handle)
            else:
                self.printIt("Failed to find uart service.")
            
        elif event == IRQ_GATTC_CHARACTERISTIC_RESULT:  #check that it has Rx and Tx
            self.printIt('Connected device returned a characteristic.')
            conn_handle, def_handle, value_handle, properties, uuid = data
            if conn_handle == self._conn_handle and uuid == UART_RX_CHAR_UUID:
                self._rx_handle = value_handle
                self.printIt('rx handle: '+str(value_handle))
            if conn_handle == self._conn_handle and uuid == UART_TX_CHAR_UUID:
                self._tx_handle = value_handle
                self.printIt('tx handle: '+str(value_handle))
        
        elif event == IRQ_GATTC_CHARACTERISTIC_DONE:  #got the info - run the connection callback
            self.printIt('Characteristic query complete.')
            if self._tx_handle is not None and self._rx_handle is not None:
                # We've finished connecting and discovering device, fire the connect callback.
                if self._conn_callback:
                    self._conn_callback()
                else:
                    self.printIt("Failed to find uart rx characteristic.")
        
        elif event == IRQ_GATTC_WRITE_DONE:
            conn_handle, value_handle, status = data
            self.printIt("TX complete")
    
        elif event == IRQ_GATTC_NOTIFY:
            conn_handle, value_handle, notify_data = data
            if conn_handle == self._conn_handle and value_handle == self._tx_handle:
                if self._notify_callback:
                    self._notify_callback(notify_data)
                        
    def uart_check(self, data):
        addr_type, addr, adv_type, rssi, adv_data = data
        if adv_type in (ADV_IND, ADV_DIRECT_IND) and UART_SERVICE_UUID in self.decode_services(adv_data):
            # Found a potential device, remember it and stop scanning if the name is right
            self._addr_type = addr_type
            self._addr = bytes(addr)  # Note: addr buffer is owned by caller so need to copy it.
            name = self.decode_name(adv_data)
            if bytes(addr) not in self.addresses:
                self.addresses.add(bytes(addr))
            if self.name == '':
                self._name = "?"
                self.printIt("type: %s, addr: %s, name: %s, rssi: %d"%(addr_type, str(bytes(addr)), self.name, rssi))
            else:
                if self.name == name:  # we found the right one and are done so stop scanning
                    self._name = name
                    self.found = True
                    return True
                else:
                    self._name = name or "?"
                    return False
                    
    def decode_field(self, payload, adv_type):
        i = 0
        result = []
        while i + 1 < len(payload):
            if payload[i + 1] == adv_type:
                result.append(payload[i + 2 : i + payload[i] + 1])
            i += 1 + payload[i]
        return result

    def decode_name(self,payload):
        n = self.decode_field(payload, NAME_FLAG)
        return str(n[0], "utf-8") if n else ""

    def decode_services(self, payload):
        services = []
        ADV_TYPE_UUID16_COMPLETE = (0x3)
        ADV_TYPE_UUID32_COMPLETE = (0x5)
        ADV_TYPE_UUID128_COMPLETE = (0x7)
        try:
            for u in self.decode_field(payload, ADV_TYPE_UUID16_COMPLETE):
                services.append(bluetooth.UUID(struct.unpack("<h", u)[0]))
            for u in self.decode_field(payload, ADV_TYPE_UUID32_COMPLETE):
                services.append(bluetooth.UUID(struct.unpack("<d", u)[0]))
            for u in self.decode_field(payload, ADV_TYPE_UUID128_COMPLETE):
                services.append(bluetooth.UUID(u))
        except:
            pass
        return services

    # Find a device advertising the service.
    def scan(self, duration = 2000):
        self._addr_type = None
        self._addr = None
        self.addresses = set()
        self.scanning = True
        #run for duration sec, with checking every 30 ms for 30 ms
        duration = 0 if duration < 0 else duration
        return self._ble.gap_scan(duration, 30000, 30000)

    def wait_for_scan(self):
        while self.scanning:
            if self.verbose:
                print('.',end='')
            time.sleep(0.1)

    def stop_scan(self):
        self._addr_type = None
        self._addr = None
        self._scan_callback = None
        self._ble.gap_scan(None)
        self.scanning = False

    # Connect to the specified device (otherwise use cached address from a scan).
    def connect(self):
        if self._addr_type is None or self._addr is None:
            print('error in assigning addresses')
            return False
        self._ble.gap_connect(self._addr_type, self._addr)
        return True

    # Disconnect from current device.
    def disconnect(self):
        if not self._conn_handle:
            return
        self._ble.gap_disconnect(self._conn_handle)
        self._reset()       

    def connected(self):
        self.is_connected = True

    def connect_up(self, timeout = -1):
        self.scan(timeout)
        self.wait_for_scan()
        if self.found:
            self.connect()
            return self.wait_for_connection(timeout)
        else:
            return False

    def send(self, value, response=False):
        if not self.is_connected:
            return
        self.printIt("sending " + value)
        return self._ble.gattc_write(self._conn_handle, self._rx_handle, value, 1 if response else 0)

#-------------------Peripheral---------------------------------------------------------------------------------------------------------------                
class Yell(Useful): 
    def __init__(self, name = 'Pico', interval_us=10000, verbose = True, type = 'uart'):
        self.setup(name, verbose, self._irq)
        self.service = UART_UUID if type == 'uart' else MIDI_UUID
        services = [self.service]
        if type == 'uart':
            ((self._handle_tx, self._handle_rx),) = self._ble.gatts_register_services((UART_SERVICE,))
        elif type == 'midi':
            ((self._handle_tx, ),) = self._ble.gatts_register_services((MIDI_SERVICE,))
            self._handle_rx = self._handle_tx   # same handle for both directions
        else:
            print('unsupported type')
        self._connections = set()
        self._write_callback = self.rx  
        self.interval_us = interval_us
                
    def advertise(self):
        short = self.name[:8]
        payload = struct.pack("BB", len(short) + 1, NAME_FLAG) + short  # byte length, byte type, value
        value = bytes(self.service)
        payload += struct.pack("BB", len(value) + 1,ADV_TYPE_UUID128_COMPLETE) + value
        self._ble.gap_advertise(self.interval_us, adv_data=payload)
        print("gap advertise")
        self.printIt('Advertising...')
        
    def stop_advertising(self):
        self._ble.gap_advertise(None)
        self.printIt("Advertising stopped")
        
    def _irq(self, event, data):  # Track connections so we can send notifications.
        if event == IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            self._connections.add(conn_handle)
            self.is_connected = True
            self.printIt("Connected: "+str(conn_handle))
            
        elif event == IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            self._connections.remove(conn_handle)
            #self._write_callback = None
            self.is_connected = False  #assuming only one connection
            self.printIt("Disconnected: " + str(conn_handle))
            
        elif event == IRQ_GATTS_WRITE:
            conn_handle, value_handle = data
            value = self._ble.gatts_read(value_handle)
            if value_handle == self._handle_rx and self._write_callback:
                self._write_callback(value)
        
    def disconnect(self):
        for conn_handle in self._connections:
            self._ble.gap_disconnect(conn_handle)
        self.printIt("Disconnected from central")
        
    def connect_up(self, timeout = -1):

        self.advertise()

        success = self.wait_for_connection(timeout)
        if success:
            self.printIt("\nConnected to central")
        self.stop_advertising()
        return success
    
    def send(self, data):
        if not self.is_connected:
            return
        for conn_handle in self._connections:
            self._ble.gatts_notify(conn_handle, self._handle_tx, data)
        self.printIt("sent to %d central(s): %s" % (len(self._connections), data))
'''
def main(mode = 'P'): 
    if mode == 'P':
        try:
            p = Yell('Fred', verbose = False)
            if p.connect_up():
                print('P connected')
                time.sleep(2)
                payload = ''
                for i in range(100):
                    payload += str(i)
                    p.send(payload)#str(i) + chr(i))
                    if p.is_any:
                        print(p.read())
                    if not p.is_connected:
                        print('lost connection')
                        break
                    time.sleep(1)
        except Exception as e:
            print(e)
        finally:
            p.disconnect()
            print('closing up')
    else:    
        try:   
            L = Listen('Fred', verbose = False)
            if L.connect_up():
                print('L connected')
                while L.is_connected:
                    time.sleep(4)
                    if L.is_any:
                        reply = L.read()
                        print(len(reply))
                        L.send(reply[:20])
        except Exception as e:
            print(e)
        finally:
            L.disconnect()
            print('closing up')
main()
'''