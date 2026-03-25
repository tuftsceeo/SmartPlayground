# lib/hardware.py
import time
from machine import Pin

def setup_antenna():
    WIFI_ENABLE = Pin(3, Pin.OUT)
    WIFI_ANT_CONFIG = Pin(14, Pin.OUT)
    WIFI_ENABLE.value(0)
    time.sleep_ms(100)
    WIFI_ANT_CONFIG.value(1)  # External antenna