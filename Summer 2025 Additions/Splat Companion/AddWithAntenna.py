##Changing from internal to external antenna
# Only add this to the rest of the code if physical antenna is connected
#from machine import Pin
#import time

# Define pins
WIFI_ENABLE = Pin(3, Pin.OUT)
WIFI_ANT_CONFIG = Pin(14, Pin.OUT)

# Activate RF switch control
WIFI_ENABLE.value(0) #Low

# Wait for 100 milliseconds
time.sleep_ms(100)

# Use external antenna
WIFI_ANT_CONFIG.value(1) #High