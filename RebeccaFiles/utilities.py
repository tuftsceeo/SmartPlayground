# utilities.py for the plushie module (I didn't change this code from the original, 
# but since I'm having problem with the buttons, I might have to change something in the Button class)

from machine import Pin, PWM, deepsleep
import machine
import micropython
import esp32
import time
import asyncio

BUTTON_PIN = 0
BUZZER_PIN = 19
MOTOR_PIN = 21

class Button:
    def __init__(self, module_type = 'plushie', callback = None):
        self.module_type = module_type
        self.motor = Motor(self.module_type)
        self.pressed = False
        self.time_of_button_press = 0
        self.old_pressed_time = 0
        self.time_of_button_released = 0
        self.flag = False
        

        self.button = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
        self.button.irq(handler=self.update, trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING)       
        esp32.wake_on_ext1(pins = (self.button,), level = esp32.WAKEUP_ALL_LOW)
        self.callback = callback
        
    def update(self, p):
        try:
            micropython.schedule(self.run_callback, p)
        except:
            pass
    
    def run_callback(self, p):
        if self.button.value():
            self.motor.stop()
        else:
            self.motor.start()
        self.pressed = self.button.value() == 0
        if self.callback: self.callback

        
class Motor:
    def __init__(self, module_type = 'plushie'):
        self.module_type = module_type
        self.motor = Pin(MOTOR_PIN, Pin.OUT)
        self.btn = self.module_type == "button"

    def start(self):
        if self.btn:
            return
        self.motor.on()

    def stop(self):
        if self.btn:
            return
        self.motor.off()

class Buzzer:
    def __init__(self, volume = 1):
        self.volume = volume
        self.buzzer = PWM(Pin(BUZZER_PIN))
        self.freq = 0
        self.buzzer.duty(0)
        
    def play(self, frequency):
        if frequency == self.freq: return
        self.freq = frequency
        self.buzzer.freq(self.freq)
        self.buzzer.duty(int(self.volume *1000))  # 50% duty cycle

    def stop(self):
        self.freq = 0
        self.buzzer.duty(0)

    def close(self):
        self.buzzer.deinit()

class Hibernate:
    def __init__(self):
        pass
    
    def hibernate(self):
        deepsleep()



