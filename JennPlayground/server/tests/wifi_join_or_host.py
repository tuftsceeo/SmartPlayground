import network
import time

# Configuration of local Wifi
TARGET_SSID = "Pixel_4115"
WIFI_PASSWORD = "PASSWORD"


# Configuration of Access Point / Adhoc
ADHOC_SSID = "OpenCam11"
ADHOC_PASSWORD = "GoGoCam"
PREFERRED_IP = "10.0.0.1"  # Preferred IP address
SUBNET_MASK = "255.255.255.0"
GATEWAY = "10.0.0.1"
DNS = "10.0.0.1"


def connect_to_network(ssid, password):
    sta_if.active(True)
    sta_if.connect(ssid, password)

    for _ in range(10):  # Wait up to 10 seconds for connection
        if sta_if.isconnected():
            print("Connected to:", ssid)
            print("Network config:", sta_if.ifconfig())
            return True
        time.sleep(1)

    print("Failed to connect to:", ssid)
    return False

def create_adhoc_network(ssid, password):
    ap_if = network.WLAN(network.AP_IF)
    ap_if.active(True)
    ap_if.config(essid=ssid, password=password)
    ap_if.ifconfig((PREFERRED_IP, SUBNET_MASK, GATEWAY, DNS))
    print("Ad-hoc network created with SSID:", ssid)
    print("Network config:", ap_if.ifconfig())

def print_ip_address(interface):
    for _ in range(10):
        print("IP Address:", interface.ifconfig()[0])
        time.sleep(1)

# Initialize the Wi-Fi station interface
sta_if = network.WLAN(network.STA_IF)

def scan_networks():
    # Ensure the Wi-Fi interface is active
    if not sta_if.active():
        sta_if.active(True)

    for i in range(10): # Try to connect for 10 seconds
        # Scan for available networks
        networks = sta_if.scan()

        # Check for target network"
        network_found = False
        print("Networks Found:", end=" ")
        for netw in networks:
            ssid = netw[0].decode('utf-8')
            print(ssid, end="; ")
            if ssid == TARGET_SSID:
                network_found = True
                if connect_to_network(TARGET_SSID, WIFI_PASSWORD):
                    print_ip_address(sta_if)
                    return network_found

        print("\nConnection attempt: ", 10-i)
        time.sleep(1)
    return network_found

network_found = scan_networks()
# If target network is not found or connection failed, create ad-hoc network
if not network_found:
    create_adhoc_network(ADHOC_SSID, ADHOC_PASSWORD)
    ap_if = network.WLAN(network.AP_IF)
    print_ip_address(ap_if)
