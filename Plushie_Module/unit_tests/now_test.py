import time, json

import utilities.now as now
import ubinascii


def now_callback(msg, mac, rssi):
    print(mac, msg.decode('utf-8') , rssi)
    try:
        payload = json.loads(msg.decode('utf-8'))
        topic = payload['topic']
        value = payload['value']
        print(payload)
        
        if topic == "/gem":  #do this here because you do not want to miss it
            bytes_from_string = value.encode('ascii')
            gem_mac = ubinascii.a2b_base64(bytes_from_string)
            print('hidden gem = ',gem_mac)
            hidden_gem = gem_mac
        
    except Exception as e:
        print(e)
            
espnow = now.Now(now_callback)
espnow.connect()
mac = espnow.wifi.config('mac')
print('my mac address is ',[hex(b) for b in mac])
#espnow.antenna()

print('ESPNow is running')

for i in range(10):
    #espnow.publish(json.dumps({'topic':'/test','value':3}))
    time.sleep(1)
    
espnow.close()