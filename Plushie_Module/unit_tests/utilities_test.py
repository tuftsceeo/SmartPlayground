import time
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
        a.default_intensity = 0.1
        a.default_color = lights.RED
        await a.animate()
        await a.animate(color = lights.PURPLE, intensity = 0.2, number = 5, repeat= 2, timeout = 2.0, speed = 0.5)
    
    asyncio.run(main())

def accel_test():
    print('Testing the accelerometer 10 times')
    a = i2c_bus.LIS2DW12()
    time.sleep(0.1)
    for i in range(15):
        x,y,z = a.read_accel()
        magnitude = (x**2 + y**2 + z**2)**0.5
        print(f"Test: {i+1} - {magnitude}: {x}, {y}, {z}")
        time.sleep(1)
    
    print("Done testing")

def battery_test():
    print('Testing the battery')
    b = i2c_bus.Battery()
    print('percentage = ',b.read())

    
button_test()
motor_test()
buzzer_test()
light_test()
accel_test()
battery_test()
