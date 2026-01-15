#main.py for the cactus
#Does not quite work as intended (as of 7/30)

import time
import math
import random
from machine import Pin, Timer, SoftI2C, PWM
import machine
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

pwm = PWM(19, freq=50, duty_u16=8192)  # create a PWM object on a pin
                                    
pwm.duty_u16(65535)  ## fast
#pwm.duty_u16(40500)  ##slow
#pwm.duty_u16(0) ## stop


motor1 = Pin(18, Pin.OUT)
motor2 = Pin(20, Pin.OUT)
stby = Pin(17, Pin.OUT)  #needs to be high for motor to move


def DanceCWfast(t=3):
    #pwm.duty_u16(65535)
    stby.on()
    motor1.on() #CW
    motor2.off()
    time.sleep(t)
    #pwm.duty_u16(0)
    stby.off()
    motor1.off() 
    motor2.off()
    
def DanceCCWfast(t=3):
    #pwm.duty_u16(65535)
    stby.on()
    motor1.off() 
    motor2.on() #CCW
    time.sleep(t)
    #pwm.duty_u16(0)
    stby.off()
    motor1.off() 
    motor2.off()
    

'''
def DanceCWslow(t = 3):
    #pwm.duty_u16(40500)
    stby.on()
    motor1.on() #CW
    motor2.off()
    time.sleep(t)
    #pwm.duty_u16(0)
    stby.off()
    motor1.off() 
    motor2.off()

def DanceCCWslow(t = 3):
    #pwm.duty_u16(40500)
    stby.on()
    motor1.off()
    motor2.on() #CCW
    time.sleep(t)
    #pwm.duty_u16(0)
    stby.off()
    motor1.off() 
    motor2.off()
'''    
def stopppp():
    stby.off()
    motor1.off() 
    motor2.off()
    
    
e = espnow.ESPNow()
e.active(True)

import json
def recv_cb(e):
    while True:  # Read out all messages waiting in the buffer
        host, msg = e.irecv(0)# Don't wait if no messages left
    
        if msg:             # msg == None if timeout in recv()
            print("I am here", host, msg)
            msg_json = eval(msg.decode('utf-8'))
            
            try:
                print(msg_json['Cactus'])
                msg_json=msg_json['Cactus']
                if(msg_json[0] == 'danceCW' and msg_json[2] == 'fast'):
                    print("dance CW fast")
                    DanceCWfast(msg_json[1]) 
                    
                elif(msg_json[0] == 'danceCCW' and msg_json[2] == 'fast'):
                    print("dance CCW fast")
                    DanceCCWfast(msg_json[1]) 
                    
                elif(msg_json[0] == 'danceCW' and msg_json[2] == 'slow'):
                    print("dance CW slow, but actually fast")
                    DanceCWfast(msg_json[1]) 
                    
                elif(msg_json[0] == 'danceCCW' and msg_json[2] == 'slow'):
                    print("dance CCW slow, but actually fast")
                    DanceCCWfast(msg_json[1]) 
                    
                elif(msg_json[0] == 'off'):
                    print("off")
                    stopppp()
                '''    
                else():
                    print("nothing")
                    stopppp()
                '''
            except:
                print("something is wrong with the json string")
                        
        elif host is None:
            return
        print(host, msg)

e.irq(recv_cb)


