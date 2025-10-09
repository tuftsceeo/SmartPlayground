from machine import Pin,I2C
from machine import Pin, SoftI2C, PWM, ADC
import adxl345
import time

i2c = SoftI2C(scl = Pin(7), sda = Pin(6))



class SENSORS:
    def __init__(self,connection=i2c):
        self.i2c=connection
        self.adx = adxl345.ADXL345(self.i2c)
        
        self.initial = [0, 4095]
        self.final =  [0, 180]
        self.pot = ADC(Pin(3))
        self.pot.atten(ADC.ATTN_11DB) # the pin expects a voltage range up to 3.3V
 
        
        self.attached = False
        self.selectsensor()
        
        time.sleep(1)
        if self.attached:
            self.light = ADC(Pin(5))
            self.light.atten(ADC.ATTN_11DB) # the pin expects a voltage range up to 3.3V


        self.battery = ADC(Pin(4))
        self.battery.atten(ADC.ATTN_11DB) # the pin expects a voltage range up to 3.3V
        
        self.x=None
        self.y=None
        self.z=None
        self.roll=None
        self.pitch=None
    
    def selectsensor(self):
        p_digital = Pin(5, Pin.OUT) #set pin as digital
        p_digital.value(0) #set pin low
        p_analog = ADC(Pin(5)) # set pin 5 to analog
        p_analog.atten(ADC.ATTN_11DB) # the pin expects a voltage range up to 3.3V
        low = p_analog.read() # read value


        p_digital = Pin(5, Pin.OUT) #set pin as digital
        p_digital.value(1) #set pin high
        p_analog = ADC(Pin(5)) #set pin to analog
        p_analog.atten(ADC.ATTN_11DB) # the pin expects a voltage range up to 3.3V
        high = p_analog.read() #read value
        
        if(low<200 and high>4000):
            self.attached = False

        else:
            self.attached = True
    
    def map_angle_to_range(self, angle):
        if 90 <= angle <= 180:
            # Normalize range 90 to 180 to 0 to 90
            normalized_angle = angle - 90
        elif -180 <= angle < -90:
            # Normalize range -180 to -90 to 90 to 180
            normalized_angle = angle + 270  # -180 + 270 = 90, -90 + 270 = 180
        elif -90 <= angle < 0:
            return 4095
        else:
            return 0       
        # Now normalized_angle is in the range [0, 180]
        # Map this range to [0, 4095]
        mapped_value = int((normalized_angle / 180.0) * 4095)

    
        return mapped_value    
    def readlight(self):
        return self.light.read()

    
    def readpot(self):
        return self.pot.read()
    
    def accel(self):
        self.x =self.adx.xValue
        self.y =self.adx.yValue
        self.z =self.adx.zValue
        

    def readaccel(self):
        self.accel()
        return self.x, self.y,self.z
    
    def readroll(self):
        self.accel()
        self.roll, self.pitch =  self.adx.RP_calculate(self.x,self.y,self.z)
        return self.roll,self.pitch
    
        
    def readpoint(self):
        l=[]
        p=[]
        
        for i in range(100):
            if self.attached:
                l.append(self.readlight())
            p.append(self.readpot())
            
        l.sort()
        p.sort()
        if self.attached:
            l=l[30:60]
            avlight=sum(l)/len(l)        
        else:
            avlight = self.map_angle_to_range(self.readroll()[0])
        
        p=p[30:60]
        avpos=sum(p)/len(p)
    
        point = avlight, self.mappot(avpos)
        return point
    
    def mappot(self, value):
        return int((self.final[1]-self.final[0]) / (self.initial[1]-self.initial[0]) * (value - self.initial[0]) + self.final[0])
  
    def readbattery(self):
        batterylevel=self.battery.read()

        if(batterylevel>2850): #charging
            return 'charging'
            
        elif(batterylevel>2700 and batterylevel <2875): #full charge
            return 'full'
        elif(batterylevel>2500 and batterylevel <2700): #medium charge
            return 'half'
        elif(batterylevel<2500): # low charge
            return 'low'
        else:
            pass
        
        return ""

