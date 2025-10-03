from machine import Pin
import time

# Try GPIO 1 first (your yellow wire)
led = Pin(1, Pin.OUT)

# quick test
for _ in range(5):
    led.value(1)   # on
    time.sleep(0.5)
    led.value(0)   # off
    time.sleep(0.5)
