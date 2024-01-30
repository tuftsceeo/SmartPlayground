from BLE_CEEO import Listen
import time
import mqtt
import machine
#  https://www.mqtt-dashboard.com - uses their test broker

import network, ubinascii
from mySecrets import Tufts_Wireless as wifi

def connect_wifi(wifi):
    station = network.WLAN(network.STA_IF)
    station.active(True)
    mac = ubinascii.hexlify(network.WLAN().config('mac'), ':').decode()
    print("MAC " + mac)
    station.connect(wifi['ssid'], wifi['pass'])
    while not station.isconnected():
        time.sleep(1)
    print('Connection successful')
    print(station.ifconfig())

def whenCalled(topic, msg):
    print((topic.decode(), msg.decode()))
    L.send(msg.decode())

def main():
    try:
        print('L connected')
        fred = mqtt.MQTTClient('Pico', 'broker.hivemq.com', keepalive=1000)
        fred.connect()
        print('MQTT Connected')
        fred.set_callback(whenCalled)
    except OSError as e:
        print('Failed')
        return
    fred.subscribe('SPIKE')
    try:
        while L.is_connected:
            #msg = 'test'
            #fred.publish('chrisrogers', msg)
            time.sleep(0.5)
            fred.check_msg()  # check subscriptions - you might want to do this more often     
    except Exception as e:
        print(e)
    finally: 
        fred.disconnect()
        print('done')

connect_wifi(wifi)
led = machine.Pin('LED', machine.Pin.OUT)
L = Listen("Maria", verbose = True)
if L.connect_up():
    main()
