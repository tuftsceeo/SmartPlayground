from machine import Pin, Timer, SoftI2C
import machine
import time
import ssd1306
import esp32
import encoder
import struct
import random
import digits
import network
import espnow
import framebuf
import sys



# A WLAN interface must be active to send()/recv()
sta = network.WLAN(network.WLAN.IF_STA)
sta.active(True)
sta.disconnect() 


##Changing from internal to external antenna
# Only add this if physical antenna is connected

# Define pins
WIFI_ENABLE = Pin(3, Pin.OUT)
WIFI_ANT_CONFIG = Pin(14, Pin.OUT)

# Activate RF switch control
WIFI_ENABLE.value(0) #Low

# Wait for 100 milliseconds
time.sleep_ms(100)

# Use external antenna
WIFI_ANT_CONFIG.value(1) #High
e = espnow.ESPNow()
e.active(True)


peer = b'\xff\xff\xff\xff\xff\xff'   # MAC address of peer's wifi interface
e.add_peer(peer)

GAME_LUT = {0: "BATTERY CHECK", 1 : "NUMBER BASED COLOR", 2: "TYPE BASED COLOR", 3: "NUMBER BASED NUMBER",4: "THRESHOLD UPDATE",5: "RAINBOW TO NEAR", 6: "RAINBOW TO ALL", 7: "LIGHTS OFF NEAR", 8: "LIGHTS OFF ALL", 9: "SLEEP ALL"}

THRESHOLD = -45
class ControlBox():
    def __init__(self):

    
        self.button = Pin(0, Pin.IN, Pin.PULL_DOWN)
        self.RSSIthreshold = - 45
     
        self.current_time = 0
        self.old_time = 0

        i2c = SoftI2C(scl = Pin(23), sda = Pin(22))
        self.display = ssd1306.SSD1306_I2C(128,64,i2c)

        self.encoder = encoder.Count(17,16)
        self.encoder_value = 0
        self.old_encoder_value = 0
  
        self.button_value = 1
        self.last_button_value = 1
        self.button_event = False
        self.button_pressed = False
        
        self.time_of_button_press = 0
        self.old_time_of_button_press = 0

        self.button.irq(trigger = Pin.IRQ_RISING, handler=self.check_switch) #timer to check button press
        
        
        tim1 = Timer(1)
        tim1.init(period=200, mode=Timer.PERIODIC, callback=self.timedAction) #blink the LED with new color
        
        self.noColor = [0,0,0]
        self.defaultColor = [50,50,50]
        self.color = self.defaultColor
        print("started")
    
    def readAccel(self):
        accel = self.h3lis331dl.read_accl()
        
        return accel
    

    def is_pressed(self):
        return self.button_pressed
    
    def check_switch(self,p):
        print("pressed")
        self.time_of_button_press = time.ticks_ms()
        if self.time_of_button_press - self.old_time_of_button_press < 500: #for debounce
            return
        self.old_time_of_button_press = self.time_of_button_press
        self.buttonAction()
                           


    def buttonAction(self):
        if self.encoder_value == 0:
            message  = {"batteryCheck": {"RSSI": -40, "value": 0}}
        elif self.encoder_value == 5:
            message = {"rainbow": {"RSSI": -40, "value": 0}}
        elif self.encoder_value == 6:
            message = {"rainbow":  {"RSSI": -90, "value": 0} }
        elif self.encoder_value == 7:
            message = {"lightOff":  {"RSSI": -40, "value": 0} }
        elif self.encoder_value == 8:
            message = {"lightOff": {"RSSI": -90, "value": 0}}
        elif self.encoder_value == 9:
            message = {"deepSleep": {"RSSI": -90, "value": 0}}
        elif self.encoder_value == 4:
            message = {"updateThreshold": {"RSSI": -40, "value": THRESHOLD}}
        else:
            message = {"updateGame": {"RSSI": -40, "value": self.encoder_value}}
        print(message)
        
        e.send(peer, str(message)) # double to make sure


    def timedAction(self, p):
        self.encoder_value =  abs((self.encoder.value()//50)%10)
        if not self.encoder_value == self.old_encoder_value:
            self.old_encoder_value = self.encoder_value
            self.shownum(self.encoder_value, 10, 10)
            
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
        
 
 
app =   ControlBox()   
app.shownum(0,10,10)       
        
def recv_cb(e):
    while True:  # Read out all messages waiting in the buffer
        mac, msg = e.irecv(0)  # Don't wait if no messages left
        if mac is None:
            return
        #print(e.peers_table)
        
e.irq(recv_cb)






