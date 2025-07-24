from machine import Pin, Timer, SoftI2C
import bluetooth
import time
import ubinascii
import neopixel

np = neopixel.NeoPixel(Pin(20), 12)
n = np.n

# micro:bit MAC
TARGET_MAC = bytes.fromhex('dcc2696a9c94') # Micro:bit V2

# micro:bit UART UUID
UART_SERVICE_UUID = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
UART_TX_UUID =      bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E")  # TX é o dado enviado do microbit

ble = bluetooth.BLE()
ble.active(True)

# Handles
conn_handle = None
tx_handle = None
cccd_handle = None

def bt_irq(event, data):
    global conn_handle, tx_handle, cccd_handle

    if event == 5:  # SCAN_RESULT
        addr_type, addr, adv_type, rssi, adv_data = data
        print("Scan:", ubinascii.hexlify(addr))
        if bytes(addr) == TARGET_MAC:
            print("found micro:bit. connecting...")
            ble.gap_scan(None)
            ble.gap_connect(addr_type, addr)

    elif event == 6:  # SCAN_DONE
        print("Scan finished.")

    elif event == 7:  # PERIPHERAL_CONNECT
        conn_handle, _, _ = data
        print("Connected! searching for services...")
        ble.gattc_discover_services(conn_handle)

    elif event == 9:  # GATTC_SERVICE_RESULT
        _, start_handle, end_handle, uuid = data
        if uuid == UART_SERVICE_UUID:
            print("Discover UART service:", uuid)
            ble.gattc_discover_characteristics(conn_handle, start_handle, end_handle)

    elif event == 11:  # GATTC_CHARACTERISTIC_RESULT
        _, def_handle, value_handle, properties, uuid = data
        if uuid == UART_TX_UUID:
            tx_handle = value_handle
            cccd_handle = tx_handle +1
            print("Characteristic TX:", tx_handle)

    elif event == 12:  # GATTC_CHARACTERISTIC_DONE
        if tx_handle and cccd_handle:
            print("Activating notifications through handle:", cccd_handle)
            result = ble.gattc_write(conn_handle, cccd_handle, b'\x02\x00', 1)
            print("Result from activation:", result)
            
    elif event == 15:  # GATTC_DESCRIPTOR_RESULT
        conn, dsc_handle, dsc_uuid = data
        print(f"Descriptor UUID: {dsc_uuid} Handle: {dsc_handle}")
        if dsc_uuid == bluetooth.UUID(0x2902):
            print("Subscribing  for notifications...")
            ble.gattc_write(conn_handle, cccd_handle, b'\x02\x00', 1)  # 0x02 para INDICATE

    elif event == 17:  # GATTC_WRITE_DONE
       conn, value_handle, status = data
       print(f"Write done on handle {value_handle} status: {status}")
       if status == 0:
           print("Notifications OK!")
       else:
           print("Fail to set notifications :-(")

    elif event == 19:  # GATTC_INDICATE
        conn, value_handle, notify_data = data
        if conn == conn_handle and value_handle == tx_handle:
            try:
                notify_bytes = bytes(notify_data)
                msg = notify_bytes.decode().strip()
                print("Received:",msg)
                
                for i in range(2 * n):
                    for j in range(n):
                        np[j] = (0, 0, 0)
                        if   msg == 'shake':
                            np[i % n] = (255, 0, 0)
                        elif msg =='point':
                            np[i % n] = (0, 255, 0)
                        elif msg =='round':
                            np[i % n] = (0, 0, 255)
                        np.write()
                        time.sleep_ms(2)
                    np[j] = (0, 0, 0)
                    np.write()                
                
            except Exception as e:
                print("Error decoding notification:", e)
                print("Raw data:", notify_data)

    elif event == 8:  # PERIPHERAL_DISCONNECT
        print("Disconnecting from micro:bit.")
        conn_handle = None
        tx_handle = None
        cccd_handle = None
        print("Reconnectiong in 2 seconds...")
        time.sleep(2)
        ble.gap_scan(10000, 30000, 30000)
        
    elif True:
        print ("event: ", event)

# Inicia o BLE com IRQ e começa a escanear
ble.irq(bt_irq)
print("Starting scan BLE...")
ble.gap_scan(10000, 30000, 30000)
