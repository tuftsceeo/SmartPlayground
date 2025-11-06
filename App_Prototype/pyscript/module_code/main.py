# With Fix for Removing Hub Broadcast from Peers Table

from machine import Pin, Timer, SoftI2C
import machine
import time
import neopixel
import esp32
from accel import H3LIS331DL
import struct
import random
import config
import game
import network
import espnow
import sys
import threshold
#fuel gauge
import lc709203f

import collections
# A WLAN interface must be active to send()/recv()
sta = network.WLAN(network.WLAN.IF_STA)
sta.active(True)
sta.disconnect()

# CRITICAL: Set WiFi channel for ESP-NOW reliability
# Both hub and modules MUST be on the same channel
WIFI_CHANNEL = 1
sta.config(channel=WIFI_CHANNEL)
print("WiFi channel set to:", WIFI_CHANNEL) 


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
print("Adding broadcast peer...")
try:
    e.add_peer(peer)
    print("Broadcast peer added successfully")
    print("Total peers:", len(list(e.get_peers())))
except Exception as err:
    print("Failed to add broadcast peer:", err)


from ucollections import deque

msg_buffer = deque((), 50, 2)  # Max 50 messages


import json

class Plushie():
    def __init__(self):
        #Defining pins

        self.NUM_LED = 12
        self.np = neopixel.NeoPixel(Pin(20), self.NUM_LED)
        #button = Pin(0, Pin.IN)
        self.motor = Pin(21, Pin.OUT)

        self.button = Pin(0, Pin.IN, Pin.PULL_UP)
        esp32.wake_on_ext1(pins = (self.button,), level = esp32.WAKEUP_ALL_LOW)

        self.THRESHOLD_RSSI = threshold.THRESHOLD
     
        self.current_time = 0
        self.old_time = 0
        self.i = 1
        self.COLOR = {0:(200*self.i,0,0), 1:(200*self.i,50*self.i,0), 2:(200*self.i, 200*self.i, 0), 3:(0, 200*self.i, 0), 4:(0 , 0 , 200*self.i), 5:(0, 200*self.i, 200*self.i), 6:(100*self.i, 200*self.i, 200*self.i)}
        
        self.PONGED = False
        self.PINGED = False
        self.GAME_TIME = 0 
        self.GAME_TIME_TIMEOUT = 500 # when the plushie sends out the color
        self.PONG_TIME_TIMEOUT = 600
        self.PONG_TIME = 0
        self.FRIEND_LIST = []
        self.collected_color = 0
        self.MAX_FRIEND = 7
        
        self.name = config.name
        self.game = game.game
        #setting up accelerometer
        i2c = SoftI2C(scl = Pin(23), sda = Pin(22))
        
        #battery sensor
        self.battery_sensor = lc709203f.LC709203F(i2c)
              
        #accelerometer
        self.h3lis331dl = H3LIS331DL(i2c)
        self.h3lis331dl.select_datarate()
        self.h3lis331dl.select_data_config()
        
        #wake up condition  
        self.button_value = 1
        self.last_button_value = 1
        self.button_event = False
        self.button_pressed = False
        
        self.time_of_button_press = 0
        self.old_pressed_time = 0
        self.time_of_button_released = 0
        
        self.animate((0,50,0), timeout = 1.0)

        self.clearBuffer = False

        self.button.irq(handler=self.check_switch, trigger=Pin.IRQ_FALLING)
        
        self.mac_value = None
        self.argument = None
        self.functionName = None
        
        self.colorMode = False

        #tim0 = Timer(0)
        #tim0.init(period=10, mode=Timer.PERIODIC, callback=self.check_switch) #timer to check button press
        
        
        #tim1 = Timer(1)
        #tim1.init(period=200, mode=Timer.PERIODIC, callback=self.timedAction) #blink the LED with new color
        
        #led tracker
        self.lednumber = 0
        self.messageDetectedAt = 0 

        self.noColor = [0,0,0]
        self.defaultColor = [50,50,50]
        self.color = self.defaultColor
        
        self.log_collected_color("PINGED", "PONGED", "COLOR")
    
    def readAccel(self):
        accel = self.h3lis331dl.read_accl()
        
        return accel
    
    def readBattery(self):
        return self.battery_sensor.cell_percent
    
    def is_pressed(self):
        return self.button_pressed
    
    def check_switch(self,p):
        # debouce stuff ^^
        self.time_of_button_press = time.ticks_ms()
        if(self.time_of_button_press - self.old_pressed_time) < 350:
            return
        self.old_pressed_time = self.time_of_button_press
        
        #print("button pressed")
        # Haptic feedback
        self.buzz(0.08,1)
        
        #start by reseting
        self.reset()
        self.PINGED = True
        self.GAME_TIME = time.ticks_ms()
       
        #send a lead call claiming your status as a leader
        message = {"pingCall": {"RSSI": self.THRESHOLD_RSSI, "value": self.name}} #can be modified to send animal name number whatever you choose
        #print("Ping message", message)
        #print(json.dumps(message))
        e.send(peer, json.dumps(message))


            
        #to make sure the button is not pressed for too long
        #if self.button.value() == 0: #check this even when the button is not released
        #    self.buttonAction()        
    
    
    def resetLog(self, argument):
        f = open("log.txt","w")
        f.close()
        
        
    def log_collected_color(self, pinged, ponged, color):
        f = open("log.txt","a")
        f.write(f'[{str(self.game)}, {str(pinged)} , {str(ponged)} , {str(color)}, {str(time.ticks_ms())}]')
        f.close()
      
    def showBattery(self, battery_level):
        self.animate((20,0,20))
        self.animate((0,20,0), number = battery_level, timeout = 2)
         
    def findandShowBattery(self, argument = None):
        x = self.readBattery()
        LED_num = int(1 + (x - 1) * 11 / 99)
        #print("percentage", LED_num,x)
        self.showBattery(LED_num)
    
    def deepSleep(self, argument = None):
        self.animate((50,0,0),repeat = 1, timeout = 1) #deepsleep
        machine.deepsleep()
        
    def buzz(self, dur=0.2, num=1):
        for i in range(num):
            self.motor.on()
            time.sleep(dur)
            self.motor.off()
            time.sleep(dur)

    def reset(self):
        print("=== RESET CALLED ===")
        print("Peers before reset:", len(list(e.get_peers())))
        self.PINGED = False
        self.PONGED = False
        self.GAME_TIME = 0
        try:
            # Don't delete the broadcast peer - we need it to receive hub commands!
            BROADCAST_PEER = b'\xff\xff\xff\xff\xff\xff'
            for old_friend in e.get_peers():
                peer_mac = old_friend[0]
                if peer_mac != BROADCAST_PEER:
                    print("Deleting peer:", peer_mac.hex())
                    try:
                        e.del_peer(peer_mac)
                    except Exception as err:  # Use 'err' not 'e' to avoid shadowing global
                        print("Failed to delete peer:", err)
                else:
                    print("Keeping broadcast peer")
            
            # Ensure broadcast peer exists (re-add if needed)
            # add_peer() will fail gracefully if already exists
            try:
                e.add_peer(BROADCAST_PEER)
                print("Ensured broadcast peer exists")
            except:
                pass  # Already exists, that's fine
                
        except Exception as error:
            print("Reset error:", error)
        print("Peers after reset:", len(list(e.get_peers())))
        self.FRIEND_LIST = []
        self.clearBuffer = True
    
    
    def turnoff(self, argument = None):
        for i in range(12):
            self.np[i] = (0,0,0)
        self.np.write()
        
        
    def saveThreshold(self, argument):
        #print("update threshold")
        f = open("threshold.py", "w")
        f.write(f'THRESHOLD = {argument} ')
        f.close()

        if 'threshold' in sys.modules:
            del sys.modules['threshold']

            import threshold
            self.threshold = threshold.THRESHOLD
            
        s.animate((0,50,0), timeout = 0.01)
        

    def saveGame(self, argument):
        f = open("game.py", "w")
        f.write(f'game = {argument} ')
        f.close()

        if 'game' in sys.modules:
            del sys.modules['game']

            import game
            self.game = game.game
            
        s.animate((0,50,0), timeout = 0.01)

       
    def showRainbow(self, argument = None):
        def wheel(pos):
            if pos < 85:
                return (pos * 3, 255 - pos * 3, 0)
            elif pos < 170:
                pos -= 85
                return (255 - pos * 3, 0, pos * 3)
            else:
                pos -= 170
                return (0, pos * 3, 255 - pos * 3)
        
        for i in range(12):
            self.np[i] = wheel((i * 256 // 12) & 255)
        self.np.write()      

    def animate(self, color, number = 12, repeat= 1, timeout = 0.0, speed = 0.1):
        for j in range(repeat):
            for i in range(number):
                self.np[i%12] = color
                self.np[(i+1)%12] = (0,0,0)
                self.np.write()
                time.sleep(speed)
            self.np[0] = color
            self.np.write()
            
        if timeout > 0.0:
            #turn off all LEDs
            time.sleep(timeout)
            for i in range(12):
                self.np[i] = [0,0,0]
            self.np.write()
     
     
    def sendPong(self, argument = None):
        print("sendPong called with argument:", argument)
        
        if(argument == "app"):
            # Hub app is scanning for devices - just respond, don't reset game state
            message = {"deviceScan": {"RSSI": self.THRESHOLD_RSSI, "value": self.name}}
            print("Sending deviceScan:", message)
            result = e.send(peer, json.dumps(message))
            print("Send result:", result)
        else:
            # Another module is pinging - this is for gameplay
            message = {"pongCall": {"RSSI": self.THRESHOLD_RSSI, "value": self.name}}
            print("Sending pongCall:", message)
            result = e.send(peer, json.dumps(message))
            print("Send result:", result)
            
            # Only reset and set PONGED state for actual gameplay, not app scans
            self.reset()
            s.PONG_TIME = time.ticks_ms()
            s.PONGED = True
            
        print("Message sent (or attempted)")
        
    def react2Pong(self, argument):
        if self.PINGED == True:
            # Only add folks to the list who haven't already been added
            if not self.mac_value in self.FRIEND_LIST:
                #print("Leading - %s"% (argument))
                self.FRIEND_LIST.append(self.mac_value)  
            else:
                pass
    
    
    def normalMode(self, argument):
        self.animate((0,200,0), number = 12, repeat= 1, timeout = 0.2, speed = 0.02)
        self.colorMode = False
        
        
    def colorUpdate(self, argument):
        self.colorMode = True
        self.animate(argument, number = 12, repeat= 1, timeout = 0.0, speed = 0)
        
        
        
    def playGame(self, argument):
        if self.colorMode == False:
            if self.game == 1:
                self.animate(s.COLOR[argument], speed = 0)
                self.log_collected_color(s.PINGED, s.PONGED, argument)
                self.reset()
            elif self.game == 2:
                #print("game 2 ")
                self.reset()
                
            elif self.game == 3:
                #print("game 3")
                self.reset()
                
            elif self.game == 4:
                pass
                #print("game 4")
        
        self.reset()
   
   
    
    def gotosleep(self):
        machine.deepsleep()
        
    def __del__(self):
        pass
        #print("deleted")
        
    def bytearray_to_numbers(self, byte_arr):
        str_data = byte_arr.decode('utf-8')
        str_data = str_data.strip('[]')
        num_strings = str_data.split(',')
        numbers = [int(num) for num in num_strings]
        return numbers


try:
    del s
    
except:
    pass
    #print("doesn't exist")
      
s= Plushie()
values = (None, None)
new_msg = False
count = 0


def recv_cb(a):
    global msg_buffer
    while True:
        mac, msg = a.irecv(0)
        if mac is None:
            return
        try:
            receivedMessage = json.loads(msg)
            print("Received from", mac.hex(), ":", receivedMessage)
            msg_buffer.append((bytes(mac), receivedMessage))

        except Exception as error:
            print("recv_cb error:", error)
    
e.irq(recv_cb)

functionLUT = {"rainbow":s.showRainbow, "resetLog": s.resetLog, "lightOff": s.turnoff, "deepSleep":s.deepSleep, "batteryCheck":s.findandShowBattery, "normalMode": s.normalMode, "color": s.colorUpdate, "updateGame": s.saveGame, "updateThreshold": s.saveThreshold, "pingCall":s.sendPong, "pongCall":s.react2Pong, "finalCall":s.playGame}

while True:
    time.sleep(0.1)
    if len(msg_buffer) > 0:
        mac, receivedMessage = msg_buffer.popleft()  # FIFO: oldest first
        
        for key in receivedMessage:
            try:
                # For broadcast messages or missing peers, assume good RSSI
                try:
                    sender_rssi = e.peers_table[mac][0]
                except (KeyError, IndexError):
                    # Broadcast or unknown sender, set rssi to -1 (an invalid RSSI value otherwise)
                    sender_rssi = -1                
                threshold = receivedMessage[key]["RSSI"]
                passes = sender_rssi > threshold
                print("Msg:", key, "| Sender RSSI:", sender_rssi, "| Threshold:", threshold, "| Pass:", passes)
                
                if sender_rssi > receivedMessage[key]["RSSI"]:
                    s.mac_value = bytes(mac)  
                    if functionLUT.get(key):
                        print("Calling", key, "function")
                        functionLUT[key](receivedMessage[key]["value"])
            except Exception as err:
                print(err)
   
   
    try: 
        # Enough time has passed between the first press of the button from LEADER to send out colors
        if(time.ticks_ms() - s.GAME_TIME > s.GAME_TIME_TIMEOUT):
            if (s.PINGED and (not s.PONGED)): 
                friends_count = len(s.FRIEND_LIST)%s.MAX_FRIEND
                message = {"finalCall":{"RSSI": s.THRESHOLD_RSSI, "value": friends_count}}
                for new_friend in s.FRIEND_LIST:
                    e.add_peer(new_friend)
                    e.send(new_friend, json.dumps(message))
                print("Sending %s"% friends_count )
                s.playGame(friends_count)

        if(s.PONGED):
            if(time.ticks_ms() - s.PONG_TIME) > s.PONG_TIME_TIMEOUT:
                s.reset()
    
    except Exception as err:
        print(err)







