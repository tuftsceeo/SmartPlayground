# test script that Milan was using to test the modules post-deepsleep

from machine import Pin, deepsleep, PWM
import esp32
import neopixel
import time
import random

BUTTON_PIN = 0
BUZZER_PIN = 19
MOTOR_PIN = 21
LED_PIN = 20


np = neopixel.NeoPixel(Pin(LED_PIN), 25)

# TODO: Test button press and maybe try button reinitialization
button = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_UP)
esp32.wake_on_ext1(pins = (button,), level = esp32.WAKEUP_ALL_LOW)

buzzer = PWM(Pin(BUZZER_PIN))
buzzer.freq(356)
buzzer.duty(1000)
time.sleep(1)
buzzer.duty(0)


motor = Pin(MOTOR_PIN, Pin.OUT)

motor.on()
time.sleep(1)
motor.off()

for i in range(10):
    r = random.randrange(0, 100,1)
    g = random.randrange(0, 100,1)
    b = random.randrange(0, 100,1)
    for j in range(25):
        np[j] = [r,g,b]
    np.write()
    time.sleep(0.3)
        
deepsleep() 