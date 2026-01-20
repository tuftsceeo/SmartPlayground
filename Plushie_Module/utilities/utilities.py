from machine import Pin, PWM, deepsleep
import machine 
import esp32
import time

from config import config

BUTTON_PIN = 0
BUZZER_PIN = 19
MOTOR_PIN = 21


class Button:
    def __init__(self, callback = None):
        self.motor = Motor()
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
        if self.flag: return  #keeps multiple calls at bay
        self.flag = True
        press = self.button.value() == 0
        if press == self.pressed:
            self.flag = False
            return
        if press:  #if pressed
            self.time_of_button_press = time.ticks_ms()
            self.motor.run(0.08)
        else:  #if released
            if(time.ticks_ms() - self.time_of_button_press) > 10000:
                print('reset')
                machine.reset()
                
        self.pressed = press
        if self.callback: self.callback
        self.flag = False

class Motor:
    def __init__(self):
        self.motor = Pin(MOTOR_PIN, Pin.OUT)
        self.btn = config['module_type'] == "button"

    def run(self, duration = 0.08):
        if self.btn:
            return
        self.motor.on()
        time.sleep(duration)
        self.motor.off()

class Buzzer:
    def __init__(self):
        self.buzzer = PWM(Pin(BUZZER_PIN))
        self.freq = 0
        self.buzzer.duty(0)
        
    def play(self, frequency):
        if frequency == self.freq: return
        self.freq = frequency
        self.buzzer.freq(self.freq)
        self.buzzer.duty(int(config['default_volume']*1000))  # 50% duty cycle

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

