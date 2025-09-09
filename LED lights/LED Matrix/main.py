#main.py for the traffic light
#now with json messages
import time
#from machine import Pin, ADC
#import machine
#import neopixel
import math
import Images_Library as pics
import random


#import statements from plushie
from machine import Pin, Timer, SoftI2C
import machine
import time
import neopixel
import esp32
#from accel import H3LIS331DL
import struct

#import config

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
#stripS = neopixel.NeoPixel(pin2, num_leds2) #slide light strip

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
    #for i in range(1):
    for index in indices:
            stripS[index] = color
            stripS.write()
            stripS[index] = (0,0,0)
            stripS.write()
            time.sleep(.01)
            stripS[index] = color
            stripS.write()
    '''    
        for index in indices:
            stripS[index] = color
            stripS.write()
            stripS[index] = (0,0,0)
            stripS.write()
            time.sleep(.01)
            stripS[index] = color
            stripS.write()
    '''    
intensity = 0.05

a = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149,]
b = [ 150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175, 176, 177, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221, 222, 223, 224, 225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239, 240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252, 253, 254, 255, 256, 257, 258, 259, 260, 261, 262, 263, 264, 265, 266, 267, 268, 269, 270, 271, 272, 273, 274, 275, 276, 277, 278, 279, 280, 281, 282, 283, 284, 285, 286, 287, 288, 289, 290, 291, 292, 293, 294, 295, 296, 297, 298, 299]
    
#slideS(a,(int(intensity*255), 0 , int(intensity*255)))

#clearS()
##example
'''
        Eyes = [212,213,214,217,218,219,196,197,197,198,201,202,203,180,181,182,185,186,187,164,165,166,169,170,171,148,149,150,153,154,155,132,133,134,137,138,139]
        Happy = [96,97,94,65,66,50,51,52,53,54,55,56,57,58,59,60,61,35,36,37,38,39,40,41,42,43,44,77,78,81,110,111,95,80]
        Images_16x16.set_leds(Eyes, (int(Images_16x16.intensity*255), 0 , int(Images_16x16.intensity*255)))
        strip.write()
        Images_16x16.set_leds(Happy, (int(Images_16x16.intensity*255), 0 , int(Images_16x16.intensity*255)))
        strip.write()
'''


#intensity = 1000 #.05  ### Change this value for brighter lights
#available_images = [ 'Heart', 'Crab', 'Star', 'Crown', 'Rocket', 'X', 'O_Mark', 'Cactus', 'Happy', 'Sad', 'QuestionMark']

    



'''
pics.Images_16x16.clear()
time.sleep(.1)
AAA = [0,299]
set_ledsS(AAA,(int(intensity*255), 0 , int(intensity*255)))



pics.Images_16x16.TF_Red()
pics.Images_16x16.TF_Yellow()
pics.Images_16x16.TF_Green()
#pics.Images_16x16.Cactus()
'''

a = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149,]
b = [ 150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175, 176, 177, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221, 222, 223, 224, 225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239, 240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252, 253, 254, 255, 256, 257, 258, 259, 260, 261, 262, 263, 264, 265, 266, 267, 268, 269, 270, 271, 272, 273, 274, 275, 276, 277, 278, 279, 280, 281, 282, 283, 284, 285, 286, 287, 288, 289, 290, 291, 292, 293, 294, 295, 296, 297, 298, 299]
    






def animation(np, animation_number, r,g,b): #micropython documentation on neopix.
    n = np.n #n is the total number of lights
    #n = int(n/2)
    #print(n)
    # cycle
    if (animation_number ==1):
        print("here")
        #for i in range(4 * n):
        for i in range(1 * n):            
            for j in range(n):
                np[j] = (0, 0, 0)
            np[i % n] = (r,g,b)
            np.write()
            time.sleep(.01)
    elif(animation_number ==2):
        # bounce - all on, one off through the strip, goes in both directions
        #for i in range(4 * n):
        for i in range(1 * n):
            for j in range(n):
                np[j] = (r,g,b)
               
            if (i // n) % 2 == 0: # will do the flashing in one direction
                np[i % n] = (0, 0, 0)
            
            else: #will return the flasing in the opposite direction
                np[n - 1 - (i % n)] = (0, 0, 0)
            
            np.write()
            
            time.sleep(.01)
    
    elif(animation_number ==3):
    # fade in/out
        #for i in range(0, 4 * 256, 8):
        for i in range(0, 1 * 256, 8):
            for j in range(n):
                if (i // 256) % 2 == 0:
                    val = i & 0xff
                else:
                    val = 255 - (i & 0xff)
                np[j] = (val, 0, 0)
            np.write()
            
    elif(animation_number == 4):
    # clear
        for i in range(n):
            np[i] = (0, 0, 0)
        np.write()
        
    elif(animation_number == 5):
    # solid color
        for i in range(n):
            np[i] = (r, g, b)
        np.write()
    

#animation(np)


  # Because ESP8266 auto-connects to last Access Point

e = espnow.ESPNow()
e.active(True)

import json
while True:
    host, msg = e.recv()
    if msg:             # msg == None if timeout in recv()
        print("I am here", host, msg)
        msg_json = eval(msg.decode('utf-8'))
        #clearS()
        try:
            print(msg_json['trafficL'])
            if(msg_json['trafficL'] == 'red'):
                print("reddddd")
                pics.Images_16x16.clear()
                pics.Images_16x16.TF_Red()
                #clearS()
                #set_ledsS(a,(0, 0 , int(intensity*255)))
                
                
            elif(msg_json['trafficL'] == 'yellow'):
                pics.Images_16x16.clear()
                pics.Images_16x16.TF_Yellow()
                #clearS()
                
                #set_ledsS(b,(int(intensity*255), 0 , int(intensity*255)))
                #slideS(a,(0, 0 , int(intensity*255))) #splat color 2
            elif(msg_json['trafficL'] == 'green'):
                pics.Images_16x16.clear()
                pics.Images_16x16.TF_Green()
                #clearS()
            
            #####
                
            elif(msg_json['trafficL'] == 'crab'):
                pics.Images_16x16.clear()
                pics.Images_16x16.Crab()
            
            elif(msg_json['trafficL'] == 'rocket'): # change eventually
                pics.Images_16x16.clear()
                pics.Images_16x16.Star()
            
            elif(msg_json['trafficL']== 'cactus'):
                pics.Images_16x16.clear()
                pics.Images_16x16.Cactus()
            
            
            
            #msg_json=msg_json["ledstrip"]
            
            #animation(np, msg_json[0],msg_json[1],msg_json[2],msg_json[3])
            #set_ledsS(a, (msg_json[1],msg_json[2],msg_json[3]))
        except:
            print("something is wrong with the json string")
        
        
