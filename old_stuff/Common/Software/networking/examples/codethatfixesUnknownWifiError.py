import network

print("Hello")

sta = network.WLAN(network.STA_IF)
ap = network.WLAN(network.AP_IF)
sta.active(True)
ap.active(True)
    
print(bytes(sta.config('mac')))
print(bytes(ap.config('mac')))

sta.active(False)
ap.active(False)

print("Done")
