print("IR Remote Control Reader")
from machine import Pin
import time

signal = Pin(1, Pin.IN)
signalHex = []

def read_ir_signal():
    """Read and decode IR signal from remote control"""
    
    # Wait for signal to go low (start of transmission)
    while signal.value() == 1:
        pass
    
    # Measure the low pulse duration
    start_time = time.ticks_us()  # Use microseconds for better precision
    while signal.value() == 0:
        pass
    low_duration = time.ticks_diff(time.ticks_us(), start_time)
    
    # Check if this is a valid start pulse (typically 9ms for NEC protocol)
    if low_duration < 8000 or low_duration > 10000:  # 8-10ms range
        return None
    
    # Wait for the high pulse after start
    start_time = time.ticks_us()
    while signal.value() == 1:
        pass
    high_duration = time.ticks_diff(time.ticks_us(), start_time)
    
    # Check if this is a valid start high pulse (typically 4.5ms for NEC)
    if high_duration < 4000 or high_duration > 5000:  # 4-5ms range
        return None
    
    print(f"Valid start sequence detected: Low={low_duration}us, High={high_duration}us")
    
    # Now read the data bits
    bits = []
    for bit_num in range(32):  # Standard IR remote sends 32 bits
        # Wait for low pulse
        start_time = time.ticks_us()
        while signal.value() == 0:
            if time.ticks_diff(time.ticks_us(), start_time) > 2000:  # Timeout
                return None
        
        # Measure high pulse duration
        start_time = time.ticks_us()
        while signal.value() == 1:
            if time.ticks_diff(time.ticks_us(), start_time) > 3000:  # Timeout
                return None
        pulse_duration = time.ticks_diff(time.ticks_us(), start_time)
        
        # Determine if it's a 0 or 1 based on pulse duration
        # Typically: 0 = ~560us, 1 = ~1690us
        if pulse_duration < 1000:
            bits.append('0')
        else:
            bits.append('1')
    
    return ''.join(bits)

def binary_to_hex_bytes(binary_string):
    """Convert binary string to hex bytes"""
    if len(binary_string) != 32:
        return None
    
    hex_bytes = []
    for i in range(0, 32, 8):
        byte = binary_string[i:i+8]
        hex_val = hex(int(byte, 2))[2:].upper()
        if len(hex_val) == 1:
            hex_val = '0' + hex_val
        hex_bytes.append(hex_val)
    
    return hex_bytes

# Main loop
print("Waiting for IR signals...")
while True:
    try:
        binary_data = read_ir_signal()
        
        if binary_data:
            hex_bytes = binary_to_hex_bytes(binary_data)
            if hex_bytes:
                print(f"Binary: {binary_data}")
                print(f"Hex bytes: {' '.join(hex_bytes)}")
                print(f"Full hex: 0x{''.join(hex_bytes)}")
                print("-" * 40)
        
        time.sleep_ms(100)  # Small delay to avoid overwhelming the system
        
    except KeyboardInterrupt:
        print("Stopping IR reader...")
        break
    except Exception as e:
        print(f"Error: {e}")
        time.sleep_ms(500)