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
        
        
        #GAME 1 Variables
        # 1 - Teal
        # 2 - Yellow
        # 3 - Blue
        # 4 - Red
        # 5 - Purple
        # 6 - Green
        self.COLOR = {0:(50,50,50), 1:(0,50,25), 2:(50,50,0),3:(0,0,50),4:(50,0,0),5:(15,0,25), 6:(5,50,0),7:(10,60,50),8:(50,10,50),9:(30,50,25), 10:(50,50,10),11:(10,0,50),12:(50,0,10), 13:(2,50,15), 14:(10,20,30),15:(10,5,50),16:(5,10,50)}
        self.PONGED = False
        self.PINGED = False
        self.GAME_TIME = 0
        self.PONG_TIME = 0
        self.FRIEND_LIST = []
        self.collected_color = 0
        
        
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

        self.animate((0,50,0), timeout = 1.0)

        tim0 = Timer(0)
        tim0.init(period=10, mode=Timer.PERIODIC, callback=self.check_switch) #timer to check button press
        
        
        tim1 = Timer(1)
        tim1.init(period=200, mode=Timer.PERIODIC, callback=self.timedAction) #blink the LED with new color
        
        #led tracker
        self.lednumber = 0
        self.messageDetectedAt = 0 

        self.noColor = [0,0,0]
        self.defaultColor = [50,50,50]
        self.color = self.defaultColor
    
    def readAccel(self):
        accel = self.h3lis331dl.read_accl()
        
        return accel
    
    def readBattery(self):
        return self.battery_sensor.cell_percent
    
    
    def is_pressed(self):
        return self.button_pressed
    
    def check_switch(self,p):
        self.button_value = self.button.value() # check button value
        if self.button_value != self.last_button_value: # see if the button value changed
            self.button_event = True
 
        if self.button_event == True:
            if self.button.value() == 0:
                self.button_pressed = True
                self.time_of_button_press = time.time()
            else:
                self.button_pressed = False
                self.buttonAction()
                           
            self.button_event = False
        self.last_button_value = self.button_value
        
        #to make sure the button is not pressed for too long
        #if self.button.value() == 0: #check this even when the button is not released
        #    self.buttonAction()        
       
    def buttonAction(self):
        #cases of holding the button
        
        ## For 2 seconds - show battery 
        if(4>=(abs(time.time() - self.time_of_button_press)) >= 2): #show battery
            self.buzz(0.1,2)
            self.findandShowBattery()
        
        ## For 6 seconds - deepsleep
        elif(abs(time.time() - self.time_of_button_press) >= 6): #deep sleep if held for 6 seconds
            self.buzz(0.08,4)
            self.animate((50,0,0),repeat = 1, timeout = 1)
            machine.deepsleep()
           
           
        ## 1 or less seconds - actual button press
        elif(abs(time.time() - self.time_of_button_press) <= 1): #button is pressed
            # Haptic feedback
            self.buzz(0.08,1)
            
            #start by reseting
            self.reset()
            self.PINGED = True
            self.GAME_TIME = time.ticks_ms()
           
            #send a lead call claiming your status as a leader
            message = {"pingCall": {"RSSI": self.THRESHOLD_RSSI, "id": self.name}} #can be modified to send animal name number whatever you choose
            #print("Ping message", message)
            e.send(peer, str(message))
            time.sleep(0.15)
            e.send(peer, str(message)) # double to make sure

        else:
            pass
            
            '''
            if(not self.color is self.defaultColor):
                self.np[self.lednumber] = self.color #lock the LED color from the button
                self.np.write()
                if (self.lednumber < 11):
                    self.lednumber += 1 #button pressed so go to next led
                    self.color = self.defaultColor #reset the color

            '''
            
    def timedAction(self,p):


        timeDiff = time.ticks_ms() - self.GAME_TIME
        
        # Enough time has passed between the first press of the button from LEADER to send out colors
        if(timeDiff > 1000):
            if (self.PINGED and (not self.PONGED)):
                
                friends_count = len(s.FRIEND_LIST)
                message = {"finalCall":{"RSSI": self.THRESHOLD_RSSI, "index": friends_count}}
                #print("finalCall message", message)
                for new_friend in self.FRIEND_LIST:
                    e.add_peer(new_friend)
                    e.send(new_friend, str(message))
                #print("Sending %s"% friends_count )
                self.playGame(friends_count)
  
        
            
        # time out for PONGED at 2 seconds
        if(self.PONGED):
            if(time.ticks_ms() - self.PONG_TIME) > 2000:
                self.reset()

    def log_collected_color(self, pinged, ponged, color):
        f = open("log.txt","a")
        f.write(f'[{str(self.game)}, {str(pinged)} , {str(ponged)} , {str(color)}]')
        f.close()
      
    def showBattery(self, battery_level):
        self.animate((20,0,20))
        self.animate((0,20,0), number = battery_level, timeout = 2)
         
    def findandShowBattery(self):
        x = self.readBattery()
        LED_num = int(1 + (x - 1) * 11 / 99)
        #print("percentage", LED_num,x)
        self.showBattery(LED_num)
        
        
    def buzz(self, dur=0.2, num=1):
        for i in range(num):
            self.motor.on()
            time.sleep(dur)
            self.motor.off()
            time.sleep(dur)


    def reset(self):
        self.PINGED = False
        self.PONGED = False
        self.GAME_TIME = 0
        for old_friend in e.get_peers():
            e.del_peer(old_friend[0])
        self.FRIEND_LIST = []
    
    
    def turnoff(self):
        for i in range(12):
            self.np[i] = (0,0,0)
        self.np.write()
        
        
    def showRainbow(self):
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

    def animate(self, color, number = 12, repeat= 1, timeout = 0.0):
        for j in range(repeat):
            for i in range(number):
                self.np[i%12] = color
                self.np[(i+1)%12] = (0,0,0)
                self.np.write()
                time.sleep(0.1)
            self.np[0] = color
            self.np.write()
            
        if timeout > 0.0:
            #turn off all LEDs
            time.sleep(timeout)
            for i in range(12):
                self.np[i] = [0,0,0]
            self.np.write()
            
        
    def playGame(self, index):
        if self.game == 1:
            self.animate(s.COLOR[index])
            self.log_collected_color(s.PINGED, s.PONGED, index)
            self.reset()
        elif self.game == 2:
            #print("game 2 ")
            self.reset()
            
        elif self.game == 3:
            #print("game 3")
            self.reset()
            
        elif self.game == 4:
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
    
def recv_cb(e):
    while True:  # Read out all messages waiting in the buffer
        mac, msg = e.irecv(0)  # Don't wait if no messages left
        if mac is None:
            return
        ##print(e.peers_table)
        
        receivedMessage = eval(msg.decode('utf-8'))

        #print(receivedMessage)
           
        for key in receivedMessage: 
            #print(receivedMessage[key]["RSSI"])
            #print(type(receivedMessage[key]["RSSI"]))
            
            
            #print(e.peers_table[mac][0], receivedMessage[key])
            if (key == "rainbow"): # Rainbow
                if(e.peers_table[mac][0] > receivedMessage[key]["RSSI"]):
                    s.showRainbow()
            elif(key == "lightOff"): # Light off
                if(e.peers_table[mac][0] > receivedMessage[key]["RSSI"]):
                    s.turnoff()
            elif(key == "deepSleep"):
                if(e.peers_table[mac][0] > receivedMessage[key]["RSSI"]):
                    #print("deepsleep")
                    s.animate((50,0,0),repeat = 1, timeout = 1) #deepsleep
                    machine.deepsleep()
            elif (key == "batteryCheck"): # batteryCheck
                if(e.peers_table[mac][0] > receivedMessage[key]["RSSI"]):
                    s.findandShowBattery()

                  
                    
         #make sure the RSSI value you are comparing is from the button you got the message from         


            elif (key == "updateGame"): # updateGame
                if(e.peers_table[mac][0] > receivedMessage[key]["RSSI"]):
                    ##print("updating game", receivedMessage[key]["game"])
                    f = open("game.py","w")
                    f.write(f'game = {receivedMessage[key]["value"]}')
                    f.close()

                    ##print("received")
                    if 'game' in sys.modules:
                        del sys.modules['game']

                        import game
                        s.game = game.game
                        
                    s.animate((0,50,0), timeout = 0.2)
        
            elif (key == "updateThreshold"): # updateThreshold
                if(e.peers_table[mac][0] > receivedMessage[key]["RSSI"]):
                    ##print("updating game", receivedMessage[key]["game"])
                    f = open("threshold.py","w")
                    f.write(f'THRESHOLD = {receivedMessage[key]["value"]}')
                    f.close()

                    ##print("received")
                    if 'threshold' in sys.modules:
                        del sys.modules['threshold']

                        import threshold
                        s.THRESHOLD_RSSI = threshold.THRESHOLD
                        
                    s.animate((0,50,0), timeout = 0.2)
                        
                        
                        
            elif (key == "batteryCheck"): # batteryCheck
                if(e.peers_table[mac][0] > receivedMessage[key]["RSSI"]):
                    s.findandShowBattery()



            # RECEIVERS - FOR PLUSHIES RECEIVING the first call 
            elif (key == "pingCall"):
                #print("Received ping")
                if(e.peers_table[mac][0] > receivedMessage[key]["RSSI"]):
                    #start by reseting everything (leaders can be overridden by receivers if they press the button
                    s.reset()
                     
                    #print("Ping is - %s"% (receivedMessage[key]["id"]))
                    #send out PONG message
                    message = {"pongCall": {"RSSI": s.THRESHOLD_RSSI, "id": s.name}} # this could be animal name etc.
                    #print("Ponged call", message)
                    e.send(peer, str(message))
                    
                
                    #set PONGED = True to indicate you are a receiver
                    s.PONG_TIME = time.ticks_ms() #for timeout
                    s.PONGED = True
                   
            
            #  LEADERS - FOR PLUSHIES WHO INITIATED PING PONG
            elif (key == "pongCall"):
                if(e.peers_table[mac][0] > receivedMessage[key]["RSSI"]):
                    #print("received Pong")
                    # Only if you have pinged and your Leadership status has not been revoked
                    if s.PINGED == True:
                        # Only add folks to the list who haven't already been added
                        if not mac in s.FRIEND_LIST:
                            #print("Leading - %s"% (receivedMessage[key]["id"]))
                            s.FRIEND_LIST.append(mac)  
                        else:
                            pass
       
            # RECEIVERS - This is the last message from LEADERs to set the color
            elif (key == "finalCall"):
                if(e.peers_table[mac][0] > receivedMessage[key]["RSSI"]):
                    # Only if you are a receiver
                    if(s.PONGED == True):
                        #print("Final call for %s"%(receivedMessage[key]["index"]))
                        # parse the color value from the message
                        index = receivedMessage[key]["index"]
                        s.playGame(index)

 

e.irq(recv_cb)

#GAME 1
# There will be one leader who initaes the communication with a ping
# Everyone in the close proximity responds with a pong message and will be called receiver
# After 1 seconds of sending the initiation ping, the leader counts receivers and sends the corresponding color





