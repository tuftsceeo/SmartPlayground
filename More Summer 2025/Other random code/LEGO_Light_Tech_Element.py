#Code for LEGO demo LED matrix
#Custom tech elements
from machine import Pin, Timer, SoftI2C, PWM
import machine
import time
import neopixel
import esp32

import struct
from BLE_CEEO import Yell
import Images_Library as pics


class Convert():
    def u16(self, data):
        if len(data)> 1:
            return struct.unpack("<H", bytes(data))[0]
        return data[0]

    def i16(self, data):
        return struct.unpack("<h", bytes(data))[0]
    
    def i32(self, data): 
        return struct.unpack("<i", bytes(data))[0]
    
    



class Sensor(Convert):
    def __init__(self):
        #Defining pins
        
        self.pwm = PWM(Pin(19, Pin.OUT), freq=1000, duty=1000)  # Pin(5) in PWM mode here
        self.pwm.duty(0)
        
        self.np = neopixel.NeoPixel(Pin(20), 12)

        self.motor = Pin(21, Pin.OUT)


        self.button = Pin(0, Pin.IN, Pin.PULL_UP)
        esp32.wake_on_ext1(pins = (self.button,), level = esp32.WAKEUP_ALL_LOW)
        
        #delaying
        a = self.button.value()      
        while a == 0:
            a = self.button.value()
            time.sleep(2)
            #keep stalling while the button is pressed
        
        #setting up accelerometer
        
        
        
    
        self.button_value = 1
        self.last_button_value = 1
        self.button_event = False
        self.button_pressed = False
        
        self.time_of_button_press = 0

        self.loading() #show animating LED

        tim = Timer(0)
        tim.init(period=200, mode=Timer.PERIODIC, callback=self.check_switch) #timer to check button press
    
    
            
    
    def play(self, frequency , hold):
        self.pwm.duty(400)
        self.pwm.freq(int(frequency))
        time.sleep_ms(hold)
        self.pwm.duty(0)
        
        
    def readAccel(self):
        accel = self.h3lis331dl.read_accl()
        accel = accel + (self.button_pressed,)
        #print("accelerometer value", accel)
        return accel
    
    
    
    def animate_lights(self, pattern, r,g,b):
        for i in range(12):
            self.np[i] = (r,g,b)
            self.np.write()
        
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
            
            
    
    
    def run_time_related_action(self):
        if(abs(time.time() - self.time_of_button_press)>2):
            self.shuttingdown()
            machine.deepsleep()
        else:
            self.button_pressed = True

        
        
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
        
            

            
    def shuttingdown(self):
        for i in range(12):
            self.np[i] = (50,0,0)
            self.np.write()
            time.sleep(0.1)

        self.turn_off()
        
        
    def loading(self):
        for j in range(2):
            for i in range(12):
                self.np[i%12] = (50,0,0)
                self.np[(i+1)%12] = (0,50,0)
                self.np.write()
                time.sleep(0.1)
                
    def turn_off(self):
        for i in range(12):
            self.np[i] = [0,0,0]
        self.np.write()
        
    
    def gotosleep(self):
        machine.deepsleep()
        
    def __del__(self):
        print("deleted")
        
        
        
s= Sensor()


bleADV = Timer(1)
p = Yell('MPY ESP32', interval_us=600, verbose = False)


connectionStatus = False
data = 0
def setData():
    #return bytes([1, 1, 0, 49, 0, 1, 0, 44, 0, 0, 4, 4, 0, 247, 0, 244, 1])
    return bytes([1, 1, 0, 49, 0, 1, 0, 44, 0, 0, 4, 4, 0, 247, 0, 1, 2])
    
    
def sendData():
    return bytes([60, 56, 0, 1, 0, 0, 71, 250, 132, 3, 0, 0, 255, 251, 248, 255, 23, 0, 0, 0, 0, 0, 0, 0, 16, 255, 0, 100, 0, 10, 2, 0, 25, 1, 0, 0, 0, 177, 255, 255, 255, 10, 1, 0, 166, 0, 0, 0, 0, 166, 0, 0, 0, 17, 2, 255, 17, 1, 255])



def parse(data):
    
    if(data[0] == 0): #Infor Request
        pass
    if(data[0] == 112):
        print("Beep requested")
        print(s.i16(data[1:3]), s.i32(data[3:7]))
        s.play(s.i16(data[1:3]), s.i32(data[3:7]))
        
    elif(data[0] == 200):
        print("LED sequence requested")
        if data[1]== 0: # Targeted to plushie
            pattern = data[2]
            red = data[3]
            green = data[4]
            blue = data[5]
            s.animate_lights(pattern, red, green, blue)
            
            
       # Change here to add image display     
        if data[1] == 1:
            image = data [2]
            timeout = data[3]
            if image == 1:
                #display_image(star) # why display image? b/c of the pyscript page code??
                #print("happy")
                #print(timeout)
                pics.Images_16x16.clear()
                pics.Images_16x16.Happy()
            elif image == 2:
                pics.Images_16x16.clear()
                pics.Images_16x16.Heart()
            elif image == 3:
                pics.Images_16x16.clear()
                pics.Images_16x16.Crab()
            elif image == 4:
                pics.Images_16x16.clear()
                pics.Images_16x16.Star()
            elif image == 5:
                pics.Images_16x16.clear()
                pics.Images_16x16.Crown()
            elif image == 6:
                pics.Images_16x16.clear()
                pics.Images_16x16.Rocket()
            elif image == 7:
                pics.Images_16x16.clear()
                pics.Images_16x16.QuestionMark()
            elif image == 8:
                pics.Images_16x16.clear()
                pics.Images_16x16.Cactus()
            else:
                pics.Images_16x16.clear()
                
            
                
        #add this on pyscript page
        #import asyncio
        #await w.display_image(1, 1000)
            
        
        

def advertiseSensor(t):
    global data, connectionStatus
    
    #payload = struct.pack('>fffB',*s.readAccel()) #packing sensor value as payload
    payload = setData()
    s.button_pressed = False 
    #payload = b'abcdefghijklmnopqrst'
    p.send(bytes(payload))
    if p.is_any:
        connectionStatus = True
        data = p.read()
        print(data)
        parse(data)
    if not p.is_connected:
        
        print('lost connection')
        bleADV.deinit()
            

if p.connect_up():
    payload = setData()
    p.send(bytes(payload)) # to set it up first 
    
    bleADV.init(period=500, mode=Timer.PERIODIC, callback=advertiseSensor)
    

    
    
while True:    
    if connectionStatus == True:
        
        pass
        #connectionStatus(True)
        #display.showmessage("Connected")
    
    if not p.is_connected:
        bleADV.init(period=3000, mode=Timer.PERIODIC, callback=advertiseSensor)

    #s.write_angle(int(data))
    time.sleep(0.3)
    





