#Code for battery reading and screen display
from machine import ADC, Pin
import time
led = Pin(15, Pin.OUT)


from machine import Pin, Timer, SoftI2C
import machine
import time
import neopixel
import esp32
#from accel import H3LIS331DL
import struct



from machine import Pin, SoftI2C
import ssd1306

i2c = SoftI2C(sda=Pin(23), scl=Pin(22))
display = ssd1306.SSD1306_I2C(128, 64, i2c)



NAME_FLAG = 0x09
IRQ_SCAN_RESULT = 5
IRQ_SCAN_DONE = 6


pin2 = machine.Pin(20) #D9 on esp32c6
num_leds2 = 12  # in one roll


stripS = neopixel.NeoPixel(pin2, num_leds2) #slide light strip


#for slide
def clear():
    stripS.fill((0, 0, 0))
    stripS.write()

def Whites():
    stripS.fill((255, 255, 255))
    stripS.write()



# Setup ADC on pin A0 (usually GPIO36 or GPIO0 depending on the board)
adc = ADC(Pin(1))  # Replace with actual pin if A0 is mapped differently

# Configure ADC attenuation if needed (11dB maps ~3.3V full scale)
adc.atten(ADC.ATTN_11DB)  # Allows up to ~3.6V input
adc.width(ADC.WIDTH_12BIT)  # 12-bit resolution (0–4095)
'''
while True:
    vbatt = 0
    for _ in range(16):
        raw = adc.read()
        print(raw)
        # Returns a value between 0 and 4095
        # Convert to millivolts
'''

start_time = time.time()
Whites()
#clear()

printy = "yay" 
while True:
    raw = adc.read()
    print(raw)
    
    display.text("Battery:",15,20,1)
    time.sleep(0.1)
    display.text(printy,20,35,0)
    printy = str(raw);
    display.text(printy,20,35,1)
    display.show()
    
    '''
    f = open("log2.txt","a")
    f.write(str(raw) + "," +str(time.time()-start_time) + "\r\n")
    f.close()
    '''
    led.off()
    time.sleep(1)
    led.on()
    time.sleep(0.5)
        # Returns a value between 0 and 4095
        # Convert to millivolts

#out of the box values - 1905 to 1940 ish
# fully charged - 2300+ or 2200+ 2270

#7/3 - after fully charged, 2113
#Testing
#Start 11:23, 1520
#end 11:46 , 16 


