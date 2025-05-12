import time
import struct
from machine import Pin, SoftI2C, PWM, ADC
from button import Splat

s = Splat('3')
s.set_color()

def callback(pin):
    time.sleep(0.001)
    if not pin.value():
        s.is_pressed = True

s.sw1.irq(trigger=Pin.IRQ_RISING, handler=callback)
    
while True:
    if s.is_pressed:
        s.send_to_close_modules()
        s.is_pressed = False
    time.sleep(0.5)