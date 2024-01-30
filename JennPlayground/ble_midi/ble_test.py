# grabbed from https://github.com/hbldh/bleak/blob/develop/examples/uart_service.py
import asyncio
import sys

import math
import datetime as dt


from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic

UART_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
UART_RX_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
UART_TX_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

MIDI_SERVICE_UUID = "03b80e5a-ede8-4b33-a751-6ce34ec4c700"
MIDI_CHAR_UUID = "7772e5db-3868-4112-a1a9-f2669d106bf3"

SERVICE_TEMP = "00001801-0000-1000-8000-00805F9B34FB"
CHAR_TEMP = "00002A05-0000-1000-8000-00805F9B34FB"

states = [b'state1',b'state2',b'state3', b'state4', b'state5']

async def uart(name = 'jenn'):
    """This sends info back and forth"""
    names = []
    def match_name(device, adv):
        if not adv.local_name in names:
            names.append(adv.local_name) #make a list of all BLE devices seen
            print(adv.local_name)
        return adv.local_name == name #is this the right one?
    
    print("Searching for: ", name, "==========")
    device = await BleakScanner.find_device_by_filter(match_name)
    print("Searching complete")
    
    if device is None:
        print("No matching device found, check the name.")
        sys.exit(1)

    def handle_disconnect(_: BleakClient):
        print("Device was disconnected, goodbye.")
        # cancelling all tasks effectively ends the program
        for task in asyncio.all_tasks():
            task.cancel()

    def handle_rx(_: BleakGATTCharacteristic, data: bytearray):
        print("Received:", data)
    
    async def callback(sender: int, data: bytearray):
        print("Received:", data)
    
    
    def blemidi_handler(_: BleakGATTCharacteristic, data):
        
        now = dt.datetime.now()
        
        intstream = [int(byte) for byte in data]
        i = 1
        tokens = []
        while i < len(intstream):
            time_low = intstream[i] % 128
            status = intstream[i+1]

            print(status)
            i += 2

    
    async def print_services(client):
        if (not client.is_connected):
            raise "client not connected"

        for service in client.services:
                print(f"[Svc] {service.uuid}: {service.description}")
                for char in service.characteristics:
                    value = (await client.read_gatt_char(char.uuid)) if "read" in char.properties else None
                    print(f"  [Chr] {char.uuid} ({char.handle}): {value} ")
                    for desc in char.descriptors:
                        value = await client.read_gatt_descriptor(desc.handle)
                        print(f"    [Dsc] {desc.uuid} ({desc.handle}): {value}")

                    
    #disconnected_callback=handle_disconnect
                    
    async with BleakClient(device) as client:
        if (not client.is_connected):
            raise "client not connected"
        
        await print_services(client)
        
#         print("Start.")
#         task = asyncio.create_task(client.start_notify(MIDI_CHAR_UUID, blemidi_handler))   
#         await asyncio.sleep(60)
#         task.cancel()
#         await task
#         await client.stop_notify(MIDI_CHAR_UUID)
        
        
        await client.start_notify(MIDI_CHAR_UUID, callback)
        await asyncio.sleep(60)  # Adjust the sleep time as needed
        await client.stop_notify(MIDI_CHAR_UUID)
        
        print("Stopped.")
        
        
        # read_bytes = await client.read_gatt_char(MIDI_CHAR_UUID)
        # rx = bytearray.decode(read_bytes)
        # print('RX', rx)
        

        
        #service = client.services.get_service(SERVICE_TEMP)
        #rx_char = service.get_characteristic(CHAR_TEMP)
        #await client.start_notify(MIDI_CHAR_UUID, handle_rx)
        await asyncio.sleep(15)
        #await client.stop_notify(MIDI_CHAR_UUID)
        
        
        # while True:            
        #     #await print_services(client)
        #     read_bytes = await client.read_gatt_char(CHAR_TEMP)
        #     rx = bytearray.decode(read_bytes)
        #     print('RX', rx)


if __name__ == "__main__":
    try:
        asyncio.run(uart('jenn'))

    except asyncio.CancelledError:
        # task is cancelled on disconnect, so we ignore this error
        pass
    
    finally:
        print("Clean Up")
        for task in asyncio.all_tasks():
            task.cancel()