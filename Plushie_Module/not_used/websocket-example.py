SSID = 'tufts_eecs'
PASS = 'foundedin1883'

import wifi
import wss
import time
import json

import asyncio

import utilities.utilities as utilities
import utilities.lights as lights
import utilities.i2c_bus as i2c_bus

def button_test():
    print('Testing the button - click it any time')
    button = utilities.Button()
    while not button.pressed:
        print('.', end='')
        time.sleep(0.1)
    print('')

def motor_test():
    print('Testing the motor - haptic feedback')
    motor = utilities.Motor()
    motor.run()
    
def buzzer_test():
    print('Testing the buzzer playing A4 for 2 sec')
    buzzer = utilities.Buzzer()
    buzzer.play(440)
    time.sleep(2)
    buzzer.stop()

def light_test():
    print('Testing the neopixels - animate red then only 5 leds in purple twice')
    async def main():
        a = lights.Lights()
        a.intensity = 0.1
        a.color = lights.RED
        await a.animate()
        await a.animate(color = lights.PURPLE, intensity = 0.2, number = 5, repeat= 2, timeout = 2.0, speed = 0.5)
    
    asyncio.run(main())
wifi.connect(SSID, PASS)
websocket = wss.WSS("wss://chrisrogers.pyscriptapps.com/talking-on-a-channel/api/channels/hackathon")

def callback(msg):
    msg = json.loads(msg)
    try:
        print('Payload: ',msg['payload'])
    except:
        print('No payload: ',msg)

def accel_loop():
    print('Testing the accelerometer some number (default 10) times')
    a = i2c_bus.LIS2DW12()
    time.sleep(0.1)
    upright=True
    try:
        while True:
            websocket.connect(callback, False)
            while upright:
                websocket.heartbeat()
                #response = websocket.read_buffer()
                print(f"Test: {a.read_accel()}")
                x,y,z = a.read_accel()
                if x > 0.5:
                    upright=True
                else:
                    upright=False
                time.sleep(0.5)
            websocket.send({'topic':'/Rebeccca','value':'Go Milan Go'})
    
            buzzer_test()
            websocket.close()
            light_test()    
            while not upright:
                #response = websocket.read_buffer()
                print(f"Test: {a.read_accel()}")
                x,y,z = a.read_accel()
                if x > 0.5:
                    upright=True
                else:
                    upright=False
                time.sleep(1)
    finally:
        websocket.close()
# waiting for hit
accel_loop()


