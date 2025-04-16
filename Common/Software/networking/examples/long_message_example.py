gc.collect()
print(gc.mem_free())

import time
from machine import Pin
from networking import Networking

import urandom
import os

#Network
networking = Networking()
peer_mac = b'\xff\xff\xff\xff\xff\xff'

message_str = "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."
print(message_str)
message_int = int(''.join(str(urandom.getrandbits(4)) for _ in range(300)))
print(message_int)
message_float = float(str(message_int) + ".0123456789")
print(message_float)
message_dict = {f"key_{i}": urandom.getrandbits(16) for i in range(50)}
print(message_dict)
message_list = [urandom.getrandbits(16) for _ in range(75)]
print(message_list)
message_bytes = os.urandom(1000)
#print(message_bytes)
message_bytearray = bytearray(os.urandom(1000))
#print(message_bytearray)

lastPressed = 0
start_time = time.ticks_ms()

message=message_str

def boop(pin):
    global lastPressed
    if(time.ticks_ms()-lastPressed>1000):
        lastPressed = time.ticks_ms()
        networking.aen.send(peer_mac, message)
#         print(f"Sent {random_bytes} to {peer_mac}")

switch_select = Pin(9, Pin.IN, Pin.PULL_UP)

#def receive():
#    for mac, message, rtime in messages:
#        print(mac, message, rtime)
        
#aen.irq(irq_receive)

#Buttons
switch_select = Pin(9, Pin.IN, Pin.PULL_UP)
switch_select.irq(trigger=Pin.IRQ_FALLING, handler=boop)

while True:
    print(f"{int(time.ticks_ms()-start_time)/1000}: {gc.mem_free()}")
    #networking.aen.ping(peer_mac)
    #print(f"Sent ping to {peer_mac}")
    time.sleep(0.1)
    if networking.aen.check_messages():
        print("Received the following messages:")
        n = 1
        for mac, message, rtime in networking.aen.return_messages():
            print(f"{n}. At: {rtime} From: {mac} Length: {len(message)} Message: {message}")
            n += 1
    gc.collect()
