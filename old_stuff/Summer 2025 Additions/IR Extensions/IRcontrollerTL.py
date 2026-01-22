##Traffic light IR transmitter
# save/run in the IR controller esp

print("IR Signal Transmitter")
from machine import Pin, PWM
import time
import network
import espnow

#Stuff for receiving? next 8 lines

# A WLAN interface must be active to send()/
sta = network.WLAN(network.WLAN.IF_STA)
sta.active(True)
sta.disconnect()   # Because ESP8266 auto-connects to last Access Point

e = espnow.ESPNow()
e.active(True)

# IR LED connected to Pin 2
ir_pin = Pin(2, Pin.OUT)
ir_pwm = PWM(ir_pin)
ir_pwm.freq(38000)  # 38kHz carrier frequency for IR

def send_pulse(duration_us, duty_cycle=512):
    """Send IR pulse for specified duration in microseconds"""
    ir_pwm.duty(duty_cycle)  # Turn on IR LED with PWM
    time.sleep_us(duration_us)
    ir_pwm.duty(0)  # Turn off IR LED

def send_gap(duration_us):
    """Send gap (no signal) for specified duration"""
    ir_pwm.duty(0)
    time.sleep_us(duration_us)

def send_nec_start():
    """Send NEC protocol start sequence"""
    send_pulse(9000)  # 9ms pulse
    send_gap(4500)    # 4.5ms gap

def send_bit(bit):
    """Send a single bit using NEC protocol timing"""
    send_pulse(560)   # 560us pulse for both 0 and 1
    if bit == '0':
        send_gap(560)  # 560us gap for 0
    else:
        send_gap(1690) # 1690us gap for 1

def send_nec_stop():
    """Send NEC protocol stop bit"""
    send_pulse(560)   # Final 560us pulse

def hex_to_binary(hex_string):
    """Convert hex string to 8-bit binary string"""
    try:
        # Remove any spaces and convert to integer
        hex_val = int(hex_string.replace(' ', ''), 16)
        # Convert to 8-bit binary string
        binary = bin(hex_val)[2:]  # Remove '0b' prefix
        # Pad to 8 bits
        while len(binary) < 8:
            binary = '0' + binary
        return binary
    except:
        return None

def parse_hex_codes(hex_input):
    """Parse hex codes from input string like '00 FF 4A B5'"""
    try:
        # Split by spaces and clean up
        hex_codes = hex_input.strip().split()
        
        # Validate each hex code
        for code in hex_codes:
            if len(code) != 2:
                print(f"Error: '{code}' is not a valid 2-digit hex code")
                return None
            try:
                int(code, 16)  # Test if it's valid hex
            except:
                print(f"Error: '{code}' is not valid hexadecimal")
                return None
        
        return hex_codes
    except:
        return None

def transmit_ir_signal(hex_codes_string):
    """Transmit IR signal from hex codes string like '00 FF 4A B5'"""
    
    print(f"Preparing to transmit: {hex_codes_string}")
    
    # Parse the hex codes
    hex_codes = parse_hex_codes(hex_codes_string)
    if not hex_codes:
        print("Error: Invalid hex code format")
        return False
    
    # Convert hex codes to binary
    binary_data = ""
    for hex_code in hex_codes:
        binary = hex_to_binary(hex_code)
        if binary is None:
            print(f"Error converting {hex_code} to binary")
            return False
        binary_data += binary
        print(f"Hex {hex_code} -> Binary {binary}")
    
    print(f"Complete binary data: {binary_data}")
    print(f"Total bits: {len(binary_data)}")
    
    # Transmit the signal
    print("Transmitting...")
    
    # Send NEC start sequence
    send_nec_start()
    
    # Send each bit
    for i, bit in enumerate(binary_data):
        send_bit(bit)
    
    # Send stop bit
    send_nec_stop()
    
    # Final gap
    send_gap(1000)
    
    print("Transmission complete!")
    return True

def repeat_signal(hex_codes_string, repeat_count=1, delay_ms=100):
    """Repeat the IR signal multiple times"""
    for i in range(repeat_count):
        print(f"Transmission {i+1}/{repeat_count}")
        transmit_ir_signal(hex_codes_string)
        if i < repeat_count - 1:  # Don't delay after last transmission
            time.sleep_ms(delay_ms)

# Example usage and interactive mode
print("IR Transmitter Ready!")
print("Example usage:")
print("transmit_ir_signal('00 FF 4A B5')")
print("repeat_signal('00 FF 4A B5', 3, 200)  # Send 3 times with 200ms delay")
print()

e = espnow.ESPNow()
e.active(True)

import json

def recv_cb(e):
    while True:  # Read out all messages waiting in the buffer
        host, msg = e.irecv(0)# Don't wait if no messages left
        if msg:             # msg == None if timeout in 
            print("I am here", host, msg)
            msg_json = eval(msg.decode('utf-8'))
            try:
                print(msg_json['trafficLamp'])
                if(msg_json['trafficLamp'] == 'red'):
                    print("reddddd")
                    transmit_ir_signal("00 FF 02 FD")   #turn on
                    transmit_ir_signal("00 FF 4A B5")
                    
                elif(msg_json['trafficLamp'] == 'yellow'):
                    print("yelowwwww")
                    transmit_ir_signal("00 FF 02 FD")   #turn on
                    transmit_ir_signal("00 FF 7A 85")
                    
                elif(msg_json['trafficLamp'] == 'green'):
                    print("greennnnn")
                    transmit_ir_signal("00 FF 02 FD")   #turn on
                    transmit_ir_signal("00 FF 52 AD")
                       
                elif(msg_json['trafficLamp'] == 'everything'):
                    print("everythingggggg")
                    transmit_ir_signal("00 FF 02 FD")   #turn on
                    transmit_ir_signal("00 FF A8 57")
                    
                elif(msg_json['trafficLamp'] == 'red_green'):
                    print("half & halfffffff")
                    transmit_ir_signal("00 FF 02 FD")   #turn on
                    transmit_ir_signal("00 FF B0 4F")
                    
                elif(msg_json['trafficLamp'] == 'rotate'):
                    print("rotateeeeee")
                    transmit_ir_signal("00 FF 02 FD")   #turn on
                    transmit_ir_signal("00 FF 5A A5")
                    
                elif(msg_json['trafficLamp'] == 'inverse_rotate'):
                    print("inverse rotateeeeee")
                    transmit_ir_signal("00 FF 02 FD")   #turn on
                    transmit_ir_signal("00 FF A2 5D")
                    
                elif(msg_json['trafficLamp'] == 'traffic_pattern'):
                    print("traffic patternnnnnnn")
                    transmit_ir_signal("00 FF 02 FD")   #turn on
                    transmit_ir_signal("00 FF E2 1D")
                       
            except:
                print("something is wrong with the json string")

        elif host is None:
            return
        print(host, msg)

e.irq(recv_cb)


##For the traffic light
#ON = 00 FF 02 FD
#OFF = 00 FF C2 3D
#Red = 00 FF 4A B5
#Yellow = 00 FF 7A 85
#Green = 00 FF 52 AD
#Everything on = 00 FF A8 57
#red and green = 00 FF B0 4F
#rotating red-yellow-green = 00 FF 5A A5
#rotating green-yellow-red = 00 FF A2 5D
#traffic light rotation =00 FF E2 1D



# You can now call these functions:
# transmit_ir_signal("00 FF 4A B5")
# repeat_signal("AA BB CC DD", 5, 150)

