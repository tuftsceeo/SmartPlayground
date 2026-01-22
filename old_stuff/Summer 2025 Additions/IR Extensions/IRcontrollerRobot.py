##Robot IR transmitter
# save/run in the IR controller esp

from machine import Pin, PWM
import time
import network
import espnow
import struct 

IR_LED = PWM(Pin(2), freq=38000, duty_u16=0) # pwm worked better to send the robot IR signal
#IR_LED = Pin(2, Pin.OUT)

hex_data = "1A3F"
IR_LED.duty_u16(0)
 

def send_signal(hex_value):
    bit_length = 8
    bit =[]
    for i in range(bit_length):
        print(hex_value)
                # Convert hex string to integer
        integer_value = int(hex_value, 16)

        # Convert integer to binary string and remove "0b" prefix
        binary_string = bin(integer_value)[2:]

        # Convert binary string characters to a list of integers (bits)
        bit = [int(bit) for bit in binary_string]
        
    print(bit)


    IR_LED.duty_u16(32768)
    time.sleep_ms(4)
    IR_LED.duty_u16(0)
    time.sleep_us(1500)
    for b in bit:
        IR_LED.duty_u16(32768)
        if(b):
            time.sleep_us(2500)
        else:
            time.sleep_us(1500)
        IR_LED.duty_u16(0)
        time.sleep_us(1500)
    
    IR_LED.duty_u16(0)

# assigning json robot messages to hex values
code_LUT = {'slideF':'0xfa05','slideL':'0xfe01','slideR':'0xf906','slideB':'0xfc03','modeS':'0xfd02','demo':'0xf609','program':'0xf50a','forward':'0xee11','turnL':'0xf20d','turnR':'0xed12','backward':'0xec13','volume+':'0xf807','volume-':'0xf00f','sciP':'0xfb04','goodH':'0xf708','music':'0xf30c','machL':'0xef10','song':'0xeb14'}
#All of the messages should replicate the action from their equivalent button on the original controller

import json
sta = network.WLAN(network.WLAN.IF_STA)
sta.active(True)
sta.disconnect()
e = espnow.ESPNow()
e.active(True)

def recv_cb(e):
    while True:  # Read out all messages waiting in the buffer
        host, msg = e.irecv(0)# Don't wait if no messages left

        if msg:             # msg == None if timeout in 
            print("I am here", host, msg)
            msg_json = eval(msg.decode('utf-8'))
            try:
                print(msg_json['robot'])
                send_signal(code_LUT[msg_json['robot']])#action code
                
            except:
                print("something is wrong with the json string")
            
        elif host is None:
            return
        print(host, msg)
        
e.irq(recv_cb)
