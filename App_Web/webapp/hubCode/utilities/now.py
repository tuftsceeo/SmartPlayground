from machine import Pin
import network
import espnow
import time

class Now():
    def __init__(self, callback = None):
        self.connected= False
        self.everyone = b'\xff\xff\xff\xff\xff\xff'    # talk to all mac addresses
        self.callback = callback if callback else self.default
        self.peers = []
    
    def default(self, msg, mac, rssi):
        mac_str = ':'.join(f'{b:02x}' for b in mac)
        print(msg.decode(),' - ',mac_str, 'rssi = ',rssi)
        
    def antenna(self):
        ##Changing from internal to external antenna
        # Only add this if physical antenna is connected

        WIFI_ENABLE = Pin(3, Pin.OUT)
        WIFI_ANT_CONFIG = Pin(14, Pin.OUT)

        WIFI_ENABLE.value(0) #Low
        time.sleep_ms(100)

        # Use external antenna
        WIFI_ANT_CONFIG.value(1) #High

    def irq_receive(self, remote_network):
        try:
            mac, msg = remote_network.irecv()
            rssi = remote_network.peers_table
            #if mac != None and mac not in self.peers: #check if the peer has already been added
            #    self.peers.append(mac)
            #    self.now_network.add_peer(mac)
            self.callback(msg, mac, rssi)
        except Exception as e:
            print(f"Receive Error: {e}")

    def connect(self, antenna = True):
        # Set up the network and ESPNow
        self.wifi = network.WLAN(network.STA_IF) # ESP network type
        self.wifi.active(True)
        self.now_network = espnow.ESPNow()
        self.now_network.active(True)
        self.now_network.add_peer(self.everyone)
        self.now_network.irq(self.irq_receive)
        if antenna: self.antenna()
        
        self.connected = True

    def publish(self, msg, mac = None):
        if not mac:
            mac = self.everyone
        if self.connected:
            self.now_network.send(mac, msg)

    def close(self):
        self.now_network.irq(None)
        self.now_network.active(False)
        self.wifi.active(False)
        self.connected = False
        print("Cleanup complete.")
