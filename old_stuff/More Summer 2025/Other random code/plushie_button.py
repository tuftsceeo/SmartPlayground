# plushie_button.py
#button transmitter code modified to work with the plushie
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
sta = network.WLAN(network.WLAN.IF_STA)
sta.active(True)
sta.disconnect()   # Because ESP8266 auto-connects to last Access Point

e = espnow.ESPNow()
e.active(True)

peer = b'\xff\xff\xff\xff\xff\xff'   # MAC address of peer's wifi interface
e.add_peer(peer) 

class Plushie():
    def __init__(self):
        #Defining pins
        self.np = neopixel.NeoPixel(Pin(20), 12)
        #button = Pin(0, Pin.IN)
        self.motor = Pin(21, Pin.OUT)

        self.button = Pin(0, Pin.IN, Pin.PULL_UP)
        esp32.wake_on_ext1(pins = (self.button,), level = esp32.WAKEUP_ALL_LOW)

        self.RSSIthreshold = -80
        #delaying
        a = self.button.value()
        
        print(self.button.value())
        self.color = config.config['color']

        while a == 0:
            
            a = self.button.value()
            #self.buzz()
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
        
        self.time_of_button_press = 0

        
        self.toSend = True #flag to determine when to send the message
        
        self.loading() #show animating LED

        tim0 = Timer(0)
        tim0.init(period=200, mode=Timer.PERIODIC, callback=self.check_switch) #timer to check button press
        
        
        tim1 = Timer(1)
        ##tim1.init(period=1000, mode=Timer.PERIODIC, callback=self.blinkLED) #blink the LED with new color
        
        #led tracker
        self.lednumber = 0
        self.messageDetectedAt = 0 

        self.noColor = [0,0,0]
        self.defaultColor = [50,50,50]
        ##self.color = self.defaultColor
        self.color = config.config['color']
    
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
            
            if self.button.value() == 0:
                self.button_pressed = True
                self.time_of_button_press = time.time()
                self.buzz()
                          
            else:
                self.button_pressed = False
                self.run_time_related_action()
                #machine.deepsleep()
                self.toSend = True ##from button.py code
                
                
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
            '''
            if(not self.color is self.defaultColor): 
                self.np[self.lednumber] = self.color #lock the LED color from the button
                self.np.write()
                if (self.lednumber < 11):
                    self.lednumber += 1 #button pressed so go to next led
                    self.color = self.defaultColor #reset the color
            '''
            # Changes made for 6/4 testing


            e.send(peer, "Starting...")
     
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
        
        
    def connectionStatus(self,state):
        if state:
            #buzz(0.5,1)
            for i in range(12):
                self.np[i] = (0,50,0)
                self.np.write()
        else:
            #buzz(0.5,2)
            for i in range(12):
                self.np[i] = (50,0,0)
                self.np.write()
        
    def blinkLED(self,p):
        self.np[self.lednumber] = self.color
        self.np.write()
        time.sleep(0.3)
        self.np[self.lednumber] = self.noColor
        self.np.write()
        
        if(time.ticks_ms() - self.messageDetectedAt >3000): #reset the color if button isn't pressed within 3 seconds
            self.color = self.defaultColor

    def shuttingdown(self):
        for i in range(12):
            self.np[i] = (50,0,0)
            self.np.write()
            time.sleep(0.1)

        self.turn_off()
        
    '''    
    def loading(self): #plushie loading
        for j in range(1):
            for i in range(12):
                self.np[i%12] = (50,0,0)
                self.np[(i+1)%12] = (0,50,0)
                self.np.write()
                time.sleep(0.1)
        self.turn_off()
    '''
    
    def loading(self): #button loading
        for j in range(1):
            for i in range(12):
                self.np[i%12] = self.color
                #self.np[(i+1)%12] = (50,50,50)
                self.np[(i+1)%12] = (1,1,1) ##attempt to lower the intensity a little bit
                self.np.write()
                time.sleep(0.1)
    
    def turn_off(self):
        for i in range(12):
            self.np[i] = [0,0,0]
        self.np.write()
           
    def gotosleep(self):
        machine.deepsleep()
        
    def bytearray_to_numbers(self, byte_arr):
        # Convert bytearray to string
        str_data = byte_arr.decode('utf-8')
        
        # Remove brackets and split by commas
        str_data = str_data.strip('[]')
        num_strings = str_data.split(',')
        
        # Convert each string to integer
        numbers = [int(num) for num in num_strings]
        
        return numbers

s= Plushie()
    
def recv_cb(e):
    while True:  # Read out all messages waiting in the buffer
        mac, msg = e.irecv(0)  # Don't wait if no messages left
        if mac is None:
            return
        print(e.peers_table)
        '''
        if(e.peers_table[mac][0] > s.RSSIthreshold): #make sure the RSSI value you are comparing is from the button you got the message from
            s.buzz()
            s.color = s.bytearray_to_numbers(msg)
            s.messageDetectedAt = time.ticks_ms()
        '''                      
e.irq(recv_cb)


