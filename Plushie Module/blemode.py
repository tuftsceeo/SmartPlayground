from bleCEEO import Yell
import time
import ubinascii
import machine
from machine import Timer, Pin


import servo
s = servo.Servo(Pin(2))



import sensors
sens=sensors.SENSORS()

#unique name

ID= ubinascii.hexlify(machine.unique_id()).decode()
import struct
bleADV = Timer(2)


p = Yell('SM', interval_us=600, verbose = False)

data = 0
def advertiseSensor(t):
    global data
    payload = struct.pack('>ff',*sens.readpoint()) #packing sensor value as payload
    p.send(bytes(payload))
    if p.is_any:
        data = p.read()
    if not p.is_connected:
        print('lost connection')
        bleADV.deinit()
            

if p.connect_up():
    bleADV.init(period=10, mode=Timer.PERIODIC, callback=advertiseSensor)
    print("Done setting up")
    
    
while True:
    if not p.is_connected:
        bleADV.init(period=3000, mode=Timer.PERIODIC, callback=advertiseSensor)

    s.write_angle(int(data))
    time.sleep(0.3)