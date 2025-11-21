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
import threshold
import json
import game
import network
import espnow

sta = network.WLAN(network.WLAN.IF_STA)
sta.active(True)
sta.disconnect()   # Because ESP8266 auto-connects to last Access Point

e = espnow.ESPNow()
e.active(True)
peer = b'\xff\xff\xff\xff\xff\xff'   # MAC address of peer's wifi interface
e.add_peer(peer)



# Define pins
WIFI_ENABLE = Pin(3, Pin.OUT)
WIFI_ANT_CONFIG = Pin(14, Pin.OUT)

# Activate RF switch control
WIFI_ENABLE.value(0) #Low

# Wait for 100 milliseconds
time.sleep_ms(100)

# Use external antenna
WIFI_ANT_CONFIG.value(1) #High


from ucollections import deque
msg_buffer = deque((), 100, 2)  # Max 50 messages

#Splat constants
splatRed = config.red
splatGreen =config.green
splatBlue = config.blue



class SplatButton():
    def __init__(self):
        #Defining pins
        self.np = neopixel.NeoPixel(Pin(20), 12)
        #button = Pin(0, Pin.IN)
        self.motor = Pin(21, Pin.OUT)
        self.button = Pin(0, Pin.IN, Pin.PULL_UP)
        esp32.wake_on_ext1(pins = (self.button,), level = esp32.WAKEUP_ALL_LOW)

        self.RSSIthreshold = threshold.THRESHOLD
        #connecting
        
        self.current_time = 0
        self.old_time = 0
        self.i = 1
        self.COLOR = {0:(200*self.i,0,0), 1:(200*self.i,50*self.i,0), 2:(200*self.i, 200*self.i, 0), 3:(0, 200*self.i, 0), 4:(0 , 0 , 200*self.i), 5:(0, 200*self.i, 200*self.i), 6:(100*self.i, 200*self.i, 200*self.i)}
        
        self.PINGED = False
        self.PONGED = False
        self.GAME_TIME = 0 
        self.GAME_TIME_TIMEOUT = 1000 # when the plushie sends out the color

        self.FRIEND_LIST = []
        self.collected_color = 0
        self.MAX_FRIEND = 7
        self.colorMode = False
        self.splat_num = config.splat_num
    
        self.showConnecting()
        
        self.name = config.name
        self.game = game.game
        #setting up accelerometer
        i2c = SoftI2C(scl = Pin(23), sda = Pin(22))
        
        ##Splat MAC
        #self.splat = OpenSplat("AB:42:00:00:B2:16")
        #self.splat = OpenSplat("AB:42:00:00:A7:A6")
        self.splat = OpenSplat("AB:42:00:00:1E:7B")
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
        
        self.THRESHOLD_RSSI = threshold.THRESHOLD
                #led tracker
        self.lednumber = 0
        self.messageDetectedAt = 0 

        self.noColor = [0,0,0]
        self.defaultColor = [50,50,50]
        self.color = self.defaultColor
        
        self.log_collected_color("PINGED", "PONGED", "COLOR")
    
        self.last_update = 0 
        self.current_pixel = 0 
        self.update_interval = 100


    def readAccel(self):
        accel = self.h3lis331dl.read_accl()
        
        return accel
    
    def keepAwake(self,p):
        self.splat.setLEDsON()
        
        
    def is_pressed(self):
        return self.button_pressed
    
    def check_switch(self,p):
        # debouce stuff ^^
        self.time_of_button_press = time.ticks_ms()
        if(self.time_of_button_press - self.old_pressed_time) < 350:
            return
        self.old_pressed_time = self.time_of_button_press
        

       

        
    def deepSleep(self, argument = None):
        self.animate((50,0,0),repeat = 1, timeout = 1) #deepsleep
        machine.deepsleep()


    def reset(self):
        self.PINGED = False
        self.PONGED = False
        self.GAME_TIME = 0
        try:
            for old_friend in e.get_peers():
                e.del_peer(old_friend[0])
        except Exception as error:
            print(error)
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
     
    def resetLog(self, argument):
        f = open("log.txt","w")
        f.close()
        
        
    def log_collected_color(self, pinged, ponged, color):
        f = open("log.txt","a")
        f.write(f'[{str(self.game)}, {str(pinged)} , {str(ponged)} , {str(color)}, {str(time.ticks_ms())}]')
        f.close()
      
        
    def react2Pong(self, argument):
        if self.PINGED == True:
            # Only add folks to the list who haven't already been added
            if not self.mac_value in self.FRIEND_LIST:
                #print("Leading - %s"% (argument))
                self.FRIEND_LIST.append(self.mac_value)  
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

    def shuttingdown(self,argument = None):
        for i in range(12):
            self.np[i] = (50,0,0)
            self.np.write()
            time.sleep(0.1)

        self.turn_off()
    
    def findandShowBattery(self, argument = None):
        print("not implemented yet")
        
        
    def playGame(self, argument):
        if self.colorMode == False:
            if self.game == 1:
                self.animate(s.COLOR[argument], speed = 0)
                self.log_collected_color(s.PINGED, s.PONGED, argument)
                print("resseting")
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
    
    def update_loading_animation(self):
        global last_update, current_pixel
        
        current_time = time.ticks_ms()
        
        if time.ticks_diff(current_time, self.last_update) >= self.update_interval:
            self.last_update = current_time
            
            # Clear all pixels
            for i in range(12):
                self.np[i] = (0, 0, 0)
            
            # Light up current pixel (spinning dot)
            self.np[self.current_pixel] = (0, 150, 255)
            self.np.write()
            
            # Move to next pixel
            self.current_pixel = (self.current_pixel + 1) % 12


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
    
    
    
try:
    del s
    
except:
    pass
    #print("doesn't exist")

s= SplatButton()
# A WLAN interface must be active to send()/recv()


values = (None, None)
new_msg = False
count = 0



def recv_cb(a):
    global msg_buffer
    while True:
        mac, msg = a.irecv(0)
        if mac is None:
            return
        print("Received", msg)
        try:
            receivedMessage = json.loads(msg)
            msg_buffer.append((bytes(mac), receivedMessage))

        except Exception as error:
            print(error)
    
e.irq(recv_cb)

functionLUT = {"rainbow":s.showRainbow, "resetLog": s.resetLog, "lightOff": s.turnoff, "deepSleep":s.deepSleep, "batteryCheck":s.findandShowBattery,  "updateGame": s.saveGame, "updateThreshold": s.saveThreshold, "pongCall":s.react2Pong, "finalCall":s.playGame}


button_flag = False
def handle_splat_press():
    global button_flag
    button_flag = True 
    print("nutton pressed")
    
s.splat.on_splat_pressed = handle_splat_press


while True:
    if s.PINGED:
        s.update_loading_animation()
    if button_flag:
        s.splat.disconnect()
        time.sleep(0.1)
        e.active(True)
        s.buzz(0.08,1)
        s.reset()
        
        s.PINGED = True
        s.GAME_TIME = time.ticks_ms()
        
        message = {"pingCall": {"RSSI": s.THRESHOLD_RSSI, "value": s.name}}

        e.send(peer, json.dumps(message))
        button_flag = False
        
        
    if len(msg_buffer) > 0:
        mac, receivedMessage = msg_buffer.popleft()  # FIFO: oldest first
        
        for key in receivedMessage:
            try:
                if(e.peers_table[mac][0] > receivedMessage[key]["RSSI"]):
                    s.mac_value = bytes(mac)  
                    if functionLUT.get(key):
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
                
                time.sleep(0.1)
                s.splat.connect()
                s.splat.readSwitches()




    
    except Exception as err:
        print(err)

    





   


