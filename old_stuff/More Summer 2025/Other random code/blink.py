## Code to turn the esp light on

from machine import Pin
import time


led = Pin(15, Pin.OUT)  # Assuming the LED is connected to GPIO 8

#led.off() #off turns the light on
#led.value(0)


while True:
  led.off()       # Turn on the LED
  time.sleep(1)     # Wait for 0.5 seconds
  led.on()      # Turn off the LED
  time.sleep(1)     # Wait for another 0.5 seconds

