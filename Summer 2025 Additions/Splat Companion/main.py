# Splat companion - main.py
## Plushie_connect.py

## Change the MAC address to correspond with the Splat

from machine import Pin, Timer, SoftI2C
import machine
import time
import neopixel
import esp32
from accel import H3LIS331DL
import struct
import config
from ble_splat import OpenSplat

import network
import espnow

sta = network.WLAN(network.WLAN.IF_STA)
sta.active(True)
sta.disconnect()   # Because ESP8266 auto-connects to last Access Point

e = espnow.ESPNow()
e.active(True)
peer = b'\xff\xff\xff\xff\xff\xff'   # MAC address of peer's wifi interface
e.add_peer(peer)



#Splat constants
splatRed = config.red
splatGreen =config.green
splatBlue = config.blue



class Plushie():
    def __init__(self):
        #Defining pins
        self.np = neopixel.NeoPixel(Pin(20), 12)
        #button = Pin(0, Pin.IN)
        self.motor = Pin(21, Pin.OUT)

        self.button = Pin(0, Pin.IN, Pin.PULL_UP)
        esp32.wake_on_ext1(pins = (self.button,), level = esp32.WAKEUP_ALL_LOW)

        self.RSSIthreshold = -80
        #connecting
        
        
        self.lred = config.L_red
        self.lgreen = config.L_green
        self.lblue = config.L_blue
        self.lpattern = config.L_pattern
        #self.Tcolor = config.color
        self.image = config.image
        self.trafficLamp = config.traffic_color
        
        self.robot = config.robot
        self.splat_num = config.splat_num
        
        self.Cactus = config.cactus_state
        self.CactusTime = config.cactus_time
        self.CactusSpeed = config.cactus_speed
        
        self.showConnecting()
        
        ##Splat MAC
        #self.splat = OpenSplat("AB:42:00:00:B2:16")
        self.splat = OpenSplat("AB:42:00:00:A7:A6")
        #self.splat = OpenSplat("AB:42:00:00:1E:7B")
        #self.splat = OpenSplat("AB:42:00:00:1A:C4")
        
        self.splat.connect()
        self.showConnected()
        self.splat.readSwitches()
        self.splat.playSound(1,155)
        self.splat.setLEDsON()

        self.toSend = True
        
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

        #self.loading() #show animating LED
        self.ledOn= True
        tim0 = Timer(0)
        tim0.init(period=200, mode=Timer.PERIODIC, callback=self.check_switch) #timer to check button press
        
        
        tim1 = Timer(1)
        tim1.init(period=60000, mode=Timer.PERIODIC, callback=self.keepAwake) #blink the LED with new color
        
        #led tracker
        self.lednumber = 0
        self.messageDetectedAt = 0 

#         self.noColor = [0,0,0]
#         self.defaultColor = [50,50,50]
#         self.color = self.defaultColor
        self.color =  config.color
        #self.splat = ble_splat.OpenSplat("AB:42:00:00:1E:7B") #Test to see if this fixes the connection issue
        #self.splat_BLE()
        #flags
        
        
        
        
    def readAccel(self):
        accel = self.h3lis331dl.read_accl()
        
        return accel
    
    def keepAwake(self,p):
        self.splat.setLEDsON()
        
        
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
                
                
            self.button_event = False
        self.last_button_value = self.button_value
        
        #to make sure the button is not pressed for too long
        if self.button.value() == 0:
             self.run_time_related_action()
        
        
        
        #Possible location for the if statements
        if self.splat.splat_pressed ==True :
            self.toSend = True
        else:
            self.toSend = False
        
        if(self.toSend == True):
        #if(self.toSend == True):
            #e.send(peer, str(self.color), True)
            toSend ={'ledstrip': [self.lpattern , self.lred, self.lgreen, self.lblue] , 'ledmatix': self.image, 'trafficLamp': self.trafficLamp ,'Cactus':[self.Cactus , self.CactusTime, self.CactusSpeed] , 'robot': self.robot, 'splat_num' : self.splat_num}
        
            e.send(peer, str(toSend), True)
            
            print("splat pressed")
            self.toSend = False
        else:
            pass
            
    def run_time_related_action(self):
        # Create Splat instance
        #self.splat = OpenSplat("AB:42:00:00:1E:7B") #test to see how to fix stuff
        if(abs(time.time() - self.time_of_button_press)>2):
            self.shuttingdown()
            print("shut off")
            self.splat.playSound(3,155)
            print("off sound")
            self.splat.allLEDsOff()
            time.sleep(4)
            self.splat.disconnect()
            machine.deepsleep()
        
        else:
            print("sending signal to board")
            e.send(peer, str({"boardMessage": [config.red, config.green, config.blue]}), True)
            '''
            e.send(peer, "Starting...")
            
            #Possible location for the if statements
            if self.splat.splat_pressed =True
                self.toSend = True
            else:
                self.toSend = False
            
            if(self.toSend == True):
            #if(self.toSend == True):
                e.send(peer, str(self.color), True)
                self.toSend = False
            else:
                pass
            '''
    
 
        
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
    
    def showConnected(self):
        for i in range(12):
            self.np[i] = [config.red, config.green, config.blue]
        
        self.np.write()
     
     
    def showConnecting(self):
        for i in range(12):
            self.np[i] = [20,20,60]
        
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
    
    
    def gotConfigFile(self):
        for i in range(12):
            self.np[i] = (50,50,0)
            self.np.write()
            time.sleep(0.1)
        for i in range(12):
            self.np[i] = (0,50,0)
            self.np.write()
            time.sleep(0.1)
        self.showConnected()
        
    def loading(self):
        for j in range(1):
            for i in range(12):
                self.np[i%12] = (50,0,0)
                self.np[(i+1)%12] = (0,50,0)
                self.np.write()
                time.sleep(0.1)
        self.turn_off()
                
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


import sys

def updateConfig(sound, color, pattern, L_red, L_green, L_blue):
    # Write the new config file
    f = open('config.py', 'w')
    print("changing config")
    f.write(f"""sound = {sound}
volume = 255
color = '{color}'
L_red = {L_red}
L_green = {L_green}
L_blue = {L_blue}
L_pattern = {pattern}
red = {splatRed}
green = {splatGreen}
blue = {splatBlue}
all_leds = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14]
leds = all_leds
""")
    f.close()
    
    if 'config' in sys.modules:
        del sys.modules['config']

    import config
    
    
s= Plushie()
# A WLAN interface must be active to send()/recv()

import network
import espnow


e = espnow.ESPNow()
e.active(True)

sta = network.WLAN(network.WLAN.IF_STA)
sta.active(True)
sta.disconnect()   # Because ESP8266 auto-connects to last Access Point
    
def recv_cb(e):

    while True:  # Read out all messages waiting in the buffer
        mac, msg = e.irecv(0)  # Don't wait if no messages left
        if mac is None:
            return
        print(e.peers_table)
        
        if(e.peers_table[mac][0] > s.RSSIthreshold): #make sure the RSSI value you are comparing is from the button you got the message from
            #s.buzz()
            receivedMessage = eval(msg.decode('utf-8'))
            for key in receivedMessage:
                if key == 'SetConfig':
                    s.buzz()
                    s.gotConfigFile()
                    print(receivedMessage)
                    msg = receivedMessage[key]
            #s.color = s.bytearray_to_numbers(msg)
                    updateConfig(msg["sound"],msg["TrafficL"], msg["pattern"], msg["light"][0], msg["light"][1], msg["light"][2])
                    s.splat.sound = msg["sound"]
                    s.lred = msg["light"][0]
                    s.lgreen = msg["light"][1]
                    s.lblue = msg["light"][2]
                    s.lpattern = msg["pattern"]
                    s.Tcolor = msg["TrafficL"]
                    
            s.messageDetectedAt = time.ticks_ms()
                              
e.irq(recv_cb)







