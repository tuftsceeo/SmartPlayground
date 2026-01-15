from machine import Pin, Timer, SoftI2C
import machine
import time
import neopixel
import esp32
from accel import H3LIS331DL
import struct

import config



import network
import espnow

# A WLAN interface must be active to send()/recv()
sta = network.WLAN(network.WLAN.IF_STA)  # Or network.WLAN.IF_AP
sta.active(True)
sta.disconnect()      # For ESP8266

e = espnow.ESPNow()
e.active(True)
peer = b'\xff\xff\xff\xff\xff\xff'   # MAC address of peer's wifi interface
e.add_peer(peer)      # Must add_peer() before send()


class Button():
    def __init__(self):
        #Defining pins

        self.np = neopixel.NeoPixel(Pin(20), 12)
        #button = Pin(0, Pin.IN)
        self.record = Pin(21, Pin.OUT)
        self.record.on()

        self.button = Pin(0, Pin.IN, Pin.PULL_UP)
        esp32.wake_on_ext1(pins = (self.button,), level = esp32.WAKEUP_ALL_LOW)

        # Delete the pin object completely 
        print(self.button.value())
        self.color = config.config['color']
        
        
        #delaying
        a = self.button.value()
        while a == 0:
            a = self.button.value()
            time.sleep(2)
            #keep stalling while the button is pressed
        
        #setting up accelerometer
        i2c = SoftI2C(scl = Pin(23), sda = Pin(22))

        self.h3lis331dl = H3LIS331DL(i2c)
        self.h3lis331dl.select_datarate()
        self.h3lis331dl.select_data_config()
        
        #wake up condition
        
    
        self.button_value = 1
    
        self.last_button_value = 1
        self.button_event = False
        self.button_pressed = False
        
        self.toSend = True #flag to determine when to send the message
        
        self.time_of_button_press = 0

        self.loading() #show animating LED

        tim = Timer(0)
        tim.init(period=200, mode=Timer.PERIODIC, callback=self.check_switch) #timer to check button press
    
    def readAccel(self):
        accel = self.h3lis331dl.read_accl()
        
        return accel
    
    
    def is_pressed(self):
        
        return self.button_pressed
    
    def check_switch(self,p):
        self.button_value = self.button.value()
        if self.button_value != self.last_button_value:
            self.button_event = True
 
        if self.button_event == True:
            if self.button.value() == 0: #button pressed
                self.button_pressed = True
                self.time_of_button_press = time.time()
                          
            else: #button released
                self.button_pressed = False
                self.run_time_related_action()
                self.toSend = True

                
                
            self.button_event = False
        self.last_button_value = self.button_value
        
        #to make sure the button is not pressed for too long
        if self.button.value() == 0:
             self.run_time_related_action()
            
            
    
    
    def run_time_related_action(self):
        if(abs(time.time() - self.time_of_button_press)>2):
            self.shuttingdown()
            machine.deepsleep()
        else:
            if(self.toSend == True):
                e.send(peer, str(self.color), True)
                self.toSend = False
            else:
                pass
            
        
        
    def buzz(self, dur=0.2, num=1):
        for i in range(num):
            self.motor.on()
            time.sleep(dur)
            self.motor.off()
        
    
    def shuttingdown(self):
        for i in range(12):
            self.np[i] = (50,0,0)
            self.np.write()
            time.sleep(0.1)

        self.turn_off()
        
        
    def loading(self):
        for j in range(1):
            for i in range(12):
                self.np[i%12] = self.color
                self.np[(i+1)%12] = (50,50,50)
                self.np.write()
                time.sleep(0.1)
                
    def turn_off(self):
        for i in range(12):
            self.np[i] = [0,0,0]
        self.np.write()
        

    def __del__(self):
        print("deleted")
        
        
        
try:
    del s
    
except:
    print("doesn't exist")
    
    
    
s= Button()







