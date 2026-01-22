import time
import asyncio

import utilities.wifi as WIFI
import utilities.now as espnow

def wifi_test():
    print('Testing the wifi: Make sure you have a secrets.py file loaded')
    wifi = WIFI.Wifi()
    wifi.connect()

# https://chrisrogers.pyscriptapps.com/nick-esp-now/latest/

def now_test():
    def my_callback(msg, mac, rssi):
        print(msg, mac, rssi)
        n.publish(msg)

    n = espnow.Now(my_callback)
    n.connect()
    print(n.wifi.config('mac'))
    i = 0

    try:
        while True:
            i+= 1
            time.sleep(1)
            n.publish(f'Sent: {i}')
    
    except KeyboardInterrupt:
        print("Interrupted! Cleaning up...")
    
    finally:
        # Ensure interfaces are deactivated on exit
        n.close()
        
wifi_test()
now_test()

utilities.hibernate()