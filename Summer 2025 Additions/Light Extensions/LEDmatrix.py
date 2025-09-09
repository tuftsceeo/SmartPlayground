#LED Matrix
#save as main.py in the LED Matrix esp
#
import time
import math
import Images_Library as pics
from machine import Pin, Timer, SoftI2C
import machine
import neopixel
import esp32
import struct

import network
import espnow



# A WLAN interface must be active to send()/recv()

sta = network.WLAN(network.WLAN.IF_STA)
sta.active(True)
sta.disconnect()   # Because ESP8266 auto-connects to last Access Point

e = espnow.ESPNow()
e.active(True)

peer = b'\xff\xff\xff\xff\xff\xff'   # MAC address of peer's wifi interface
e.add_peer(peer)


###

NAME_FLAG = 0x09
IRQ_SCAN_RESULT = 5
IRQ_SCAN_DONE = 6

# Configure the LED strip
pin = machine.Pin(18) #D10 on esp32c6
num_leds = 256  # for a 16 by 16 matrix

#pin2 = machine.Pin(20) #D9 on esp32c6
#num_leds2 = 300  # in one roll

strip = neopixel.NeoPixel(pin, num_leds) #led matrix

#np=stripS

def clear():
    strip.fill((0, 0, 0))
    strip.write()

def set_led(index, color):
    strip[index] = color
    strip.write()

def set_leds(indices, color):
    for index in indices:
        strip[index] = color
    strip.write()

#for slide
def clearS():
    stripS.fill((0, 0, 0))
    stripS.write()

def set_ledS(index, color):
    stripS[index] = color
    stripS.write()

def set_ledsS(indices, color):
    for index in indices:
        stripS[index] = color
    stripS.write()

def slideS(indices, color):
    
    for index in indices:
            stripS[index] = color
            stripS.write()
            stripS[index] = (0,0,0)
            stripS.write()
            time.sleep(.01)
            stripS[index] = color
            stripS.write()
  
intensity = 0.05 # best for inside
#intensity = 1 # best for outside


e = espnow.ESPNow()
e.active(True)

import json
while True:
    host, msg = e.recv()
    if msg:             # msg == None if timeout in recv()
        print("I am here", host, msg)
        msg_json = eval(msg.decode('utf-8'))
        
        try:
            print(msg_json['ledmatix'])
            if(msg_json['ledmatix'] == 'red'):
                print("red")
                pics.Images_16x16.clear()
                pics.Images_16x16.TF_Red()
                                
            elif(msg_json['ledmatix'] == 'yellow'):
                pics.Images_16x16.clear()
                pics.Images_16x16.TF_Yellow()
                
            elif(msg_json['ledmatix'] == 'green'):
                pics.Images_16x16.clear()
                pics.Images_16x16.TF_Green()
                
            #####
                
            elif(msg_json['ledmatix'] == 'crab'):
                pics.Images_16x16.clear()
                pics.Images_16x16.Crab()
            
            elif(msg_json['ledmatix'] == 'rocket'): # change eventually
                pics.Images_16x16.clear()
                pics.Images_16x16.Rocket()
            
            elif(msg_json['ledmatix']== 'cactus'):
                pics.Images_16x16.clear()
                pics.Images_16x16.Cactus()

        except:
            print("something is wrong with the json string")
        