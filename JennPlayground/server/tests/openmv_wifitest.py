import network

# Initialize the Wi-Fi station interface
sta_if = network.WLAN(network.STA_IF)

# Ensure the Wi-Fi interface is active
if not sta_if.active():
    sta_if.active(True)

# Scan for available networks
networks = sta_if.scan()

# Print the list of available networks
print("Available Wi-Fi networks:")
for network in networks:
    ssid = network[0].decode('utf-8')
    bssid = ':'.join(['%02x' % b for b in network[1]])
    channel = network[2]
    RSSI = network[3]
    authmode = network[4]
    hidden = network[5]

    print(f"SSID: {ssid}, BSSID: {bssid}, Channel: {channel}, RSSI: {RSSI}, Authmode: {authmode}, Hidden: {hidden}")
