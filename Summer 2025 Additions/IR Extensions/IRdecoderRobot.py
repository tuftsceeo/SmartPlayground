#Robot IR decoder
#Run/save in the IR decoder/receiver esp

from machine import Pin
import time
from machine import Pin, SoftI2C
import ssd1306

#screen communication setup
i2c = SoftI2C(sda=Pin(23), scl=Pin(22))
display = ssd1306.SSD1306_I2C(128, 64, i2c)

IR = Pin(0, Pin.IN)


def test():
    count = 0
    sequence = []
    start_time = time.ticks_ms()
    if(IR.value() == 0): # when the pin gets the signal
        while IR.value() == 0: #stall while the pin is still low
            pass
        end_time = time.ticks_ms() #get time when the signal is high marking start of signal
        #print(start_time, end_time, end_time - start_time)
        if(end_time -start_time == 4): #the low signal was more than 4ms indicates beginning of the signal
            #print("Signal detected")
            while True:
                start_time = time.ticks_us()
                if IR.value() == 0:
                    while IR.value() == 0:
                        pass
                    end_time = time.ticks_us()
                    diff = end_time - start_time
                    sequence.append(diff)
                    count+=1
                if count ==16:
                    break
            #print("the sequence is", sequence)
            
            signal = []
            for s in sequence:
                if(s > 2000):
                    data = 1
                else:
                    data = 0
                signal.append(data)
            binary_string = "".join(str(bit) for bit in signal)
            decimal_value = int(binary_string, 2)

            # 2. Convert integer to a hexadecimal string
            hex_string = hex(decimal_value)
            return hex_string
        else:
            return None


printy = ""
while True:
    if IR.value() == 0:
        value = test()
        if value:
            display.text("IR hex bytes:",15,20,1)
            display.text(printy,20,35,0)
            display.text(str(' '.join(value)),20,35,1)
            printy = str(' '.join(value));
            display.show()
            print(value)

