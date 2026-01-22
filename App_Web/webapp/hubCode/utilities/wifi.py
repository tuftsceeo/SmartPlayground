import network
import time

from utilities.secrets import SSID, PASS

class Wifi:
    def __init__(self):
        self.wlan = network.WLAN(network.WLAN.IF_STA)
        
    def connect(self):
        self.wlan.active(True)
        print(f'Trying to connect to {SSID}')
        self.wlan.connect(SSID, PASS)
        
        # Wait for connection
        while not self.wlan.isconnected():
            time.sleep(0.1)
            print('.', end='')
            
        print(f"\r\n Connected! IP: {self.wlan.ifconfig()[0]}")

    def disconnect(self):
        self.wlan.disconnect()
        self.wlan.active(False)
