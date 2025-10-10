from machine import Pin, Timer, SoftI2C
import machine
import time
import ssd1306
import esp32

import struct
import random
import digits
import network
import espnow
import framebuf
import sys

import json
import sensors
sens=sensors.SENSORS()

# A WLAN interface must be active to send()/recv()
sta = network.WLAN(network.WLAN.IF_STA)
sta.active(True)
sta.disconnect() 


e = espnow.ESPNow()
e.active(True)


peer = b'\xff\xff\xff\xff\xff\xff'   # MAC address of peer's wifi interface
e.add_peer(peer)

GAME_LUT = {0: "BATTERY CHECK", 1 : "RESET LOG", 2: "UPDATE THRESHOLD", 3: "SEND GREEN",4: "SEND RED",5: "SEND BLUE", 6: "SEND RAINBOW", 7: "LIGHTS OFF NEAR", 8: "BACK TO NORMAL", 9: "SLEEP ALL"}

THRESHOLD = -45

#flags
class ControlBox():
    def __init__(self):

    
        self.button = Pin(0, Pin.IN, Pin.PULL_DOWN)
        self.RSSIthreshold = - 45
     
        self.current_time = 0
        self.old_time = 0

        i2c = SoftI2C(scl = Pin(7), sda = Pin(6))
        self.display = ssd1306.SSD1306_I2C(128,64,i2c)

        self.num_of_options = 10
        
        self.button_value = 1
        self.last_button_value = 1
        self.button_event = False
        self.button_pressed = False
        
        self.time_of_button_press = 0
        self.old_time_of_button_press = 0

        self.count = 0
        self.potValue = 0
        
        self.noColor = [0,0,0]
        self.defaultColor = [50,50,50]
        self.color = self.defaultColor
        print("started")
        
        self.lastPressed = 0

        #switch flags
        self.switch_state_up = False
        self.switch_state_down = False
        self.switch_state_select = False

        self.last_switch_state_up = False
        self.last_switch_state_down = False
        self.last_switch_state_select = False

        self.switched_up = False
        self.switched_down = False
        self.switched_select = False


        #nav switches
        self.switch_down = Pin(8, Pin.IN)
        self.switch_select = Pin(9, Pin.IN)
        self.switch_up= Pin(10, Pin.IN)

        tim = Timer(0)
        tim.init(period=50, mode=Timer.PERIODIC, callback=self.check_switch)
        #interrupt functions

    def downpressed(self, c=-1):
        time.sleep(0.05)
        if(time.ticks_ms()-self.lastPressed>200):
            self.displayNumber(c)



    def uppressed(self, c=1):
        time.sleep(0.05)
        if(time.ticks_ms()-self.lastPressed>200):
            self.displayNumber(c)



    def displayNumber(self, c):
        self.count += c
        self.count = abs(self.count%self.num_of_options)
        self.shownum(self.count, 10,10)
        self.lastPressed=time.ticks_ms()
        
    def selectpressed(self):
        time.sleep(0.05)
        self.buttonAction()
        self.lastPressed=time.ticks_ms()
        

        

        
    def check_switch(self, p):

        self.switch_state_up = self.switch_up.value()
        self.switch_state_down = self.switch_down.value()
        self.switch_state_select = self.switch_select.value()
             
        if self.switch_state_up != self.last_switch_state_up:
            self.switched_up = True
            
        elif self.switch_state_down != self.last_switch_state_down:
            self.switched_down = True
            
        elif self.switch_state_select != self.last_switch_state_select:
            self.switched_select = True
                    
        if self.switched_up:
            if self.switch_state_up == 0:
                self.uppressed()
            self.switched_up = False
        elif self.switched_down:
            if self.switch_state_down == 0:
                self.downpressed()
            self.switched_down = False
        elif self.switched_select:
            if self.switch_state_select == 0:
                self.selectpressed()
            self.switched_select = False
        
        self.last_switch_state_up = self.switch_state_up
        self.last_switch_state_down = self.switch_state_down
        self.last_switch_state_select = self.switch_state_select

      
        
        
        
        
    def readAccel(self):
        accel = self.h3lis331dl.read_accl()
        
        return accel
    

    def is_pressed(self):
        return self.button_pressed
    


    def buttonAction(self):
        
        if self.count == 0:
            message  = {"batteryCheck": {"RSSI": app.potValue, "value": 0}}
        elif self.count == 3:
            message = {"color": {"RSSI": app.potValue, "value": (0,255,0)}}
        elif self.count == 4:
            message = {"color":  {"RSSI": app.potValue, "value": (255,0,0)} }
        elif self.count == 5:
            message = {"color":  {"RSSI": app.potValue, "value": (0,0,255)} }
        elif self.count == 6:
            message = {"rainbow": {"RSSI": app.potValue, "value": 0}}
        elif self.count == 7:
            message = {"lightOff": {"RSSI": app.potValue, "value": 0}}
        elif self.count == 8:
            message = {"normalMode": {"RSSI": app.potValue, "value": 0}}
        elif self.count == 9:
            message = {"deepSleep": {"RSSI": app.potValue, "value": 0}}
        elif self.count == 10:
            message = {"deleteLog": {"RSSI": app.potValue, "value": 0}}
        elif self.count == 2:
            message = {"updateThreshold": {"RSSI": app.potValue, "value": -45}}
        elif self.count == 1:
            message = {"resetLog": {"RSSI": app.potValue, "value": 0}}
        else:
            message = {"updateGame": {"RSSI": app.potValue, "value": self.count}}
        print(message)
        
        e.send(peer, json.dumps(message)) # double to make sure



    def displaytext(self, text):
        
        texts = text.split()
        #splits multi word text into two rows
        for index, text in enumerate(texts):
            self.display.text(text, 50, 10 + index*20, 1)
        self.display.show()
        
            
    def shownum(self, num, x,y):   
        fbuf = framebuf.FrameBuffer(digits.digit[num], 32, 32, framebuf.MONO_VLSB)
        self.display.fill(0)
        self.display.show()
        self.display.blit(fbuf,x,y,0)
        self.display.show()
        self.displaytext(GAME_LUT[num]) if len(GAME_LUT) > num else self.displaytext("BLANK")
        
    def drawRect(self):
        self.display.fill_rect(120, 0, 10, 64, 1)
        self.display.fill_rect(120, 0, 10, app.potValue + 90, 0)
        self.display.show()
 
app =   ControlBox()   
app.shownum(0,10,10)
sens.final =  [-90, -30]
        
def recv_cb(e):
    while True:  # Read out all messages waiting in the buffer
        mac, msg = e.irecv(0)  # Don't wait if no messages left
        if mac is None:
            return
        #print(e.peers_table)
        
e.irq(recv_cb)

while True:
    time.sleep(0.1)
    app.potValue = sens.readpoint()[1]
    app.drawRect()
    


    









