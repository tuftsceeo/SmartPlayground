import asyncio
from machine import Pin, ADC
import time
import machine
import neopixel

numberofLED = 13
np = neopixel.NeoPixel(machine.Pin(18), numberofLED)

import network
import espnow

# A WLAN interface must be active to send()/recv()
sta = network.WLAN(network.WLAN.IF_STA)
sta.active(True)
sta.disconnect()   # Because ESP8266 auto-connects to last Access Point

e = espnow.ESPNow()
e.active(True)


RSSIthreshold = -80
        
peer = b'\xff\xff\xff\xff\xff\xff'   # MAC address of peer's wifi interface
e.add_peer(peer)   
def recv_cb(e):
    while True:  # Read out all messages waiting in the buffer
        mac, msg = e.irecv(0)  # Don't wait if no messages left
        if mac is None:
            return
        print(mac, msg)
        if(e.peers_table[mac][0] > RSSIthreshold): #make sure the RSSI value you are comparing is from the button you got the message from
            receivedMessage = eval(msg.decode('utf-8'))
            for key in receivedMessage:
                print("Threshold met")
                if key == "boardMessage":
                    print(" and message from companion received")
                    print(receivedMessage[key])
                    np[11] = receivedMessage[key]
                    np[12] = receivedMessage[key]
                    np.write()
            
           
e.irq(recv_cb)

sound_knob = 0
color_knob = 1
picture_knob = 2

sound = ADC(Pin(sound_knob))
color = ADC(Pin(color_knob))
picture = ADC(Pin(picture_knob))

sound.atten(ADC.ATTN_11DB)
color.atten(ADC.ATTN_11DB)
picture.atten(ADC.ATTN_11DB)

pattern_button_state = True
send_button_state = False
pattern_choice = 1

# Define button pins
pattern_pin = Pin(19, Pin.IN, Pin.PULL_UP)
send_pin = Pin(20, Pin.IN, Pin.PULL_UP)

# Global flags for button states
pattern_pressed = False
send_pressed = False

def pattern_button_handler(pin):
    global pattern_pressed
    pattern_pressed = True

def send_button_handler(pin):
    global send_pressed
    send_pressed = True

# Attach interrupts
pattern_pin.irq(trigger=Pin.IRQ_FALLING, handler=pattern_button_handler)
send_pin.irq(trigger=Pin.IRQ_RISING, handler=send_button_handler)

color_LUT = {
    "red": [255, 0, 0],
    "orange": [255, 165, 0], 
    "yellow": [255, 255, 0],
    "Nochange": [0, 0, 0],
    "green": [0, 255, 0],
    "blue": [0, 0, 255],
    "purple": [128, 0, 128]
}

sound_LUT = {
    "Cat": 19,
    "Chicken": 20, 
    "Dog": 22,
    "Silence": 0,
    "Elephant": 25,
    "Horse": 26,
    "Sheep": 28
}

def read_value(pot):
    """Read ADC value with averaging"""
    value = []
    num = 10
    for i in range(num):
        value.append(pot.read())
    return sum(value) / num

def setColor(pot):
    value = read_value(pot)
    if value < 471:
        return color_LUT["red"]
    elif value < 943:
        return color_LUT["orange"]
    elif value < 1414:
        return color_LUT["yellow"]
    elif value < 1886:
        return color_LUT["Nochange"]
    elif value < 2357:
        return color_LUT["green"]
    elif value < 3000:
        return color_LUT["blue"]
    else:
        return color_LUT["purple"]

def setSound(pot):
    value = read_value(pot)
    if value < 471:
        return sound_LUT["Cat"]
    elif value < 943:
        return sound_LUT["Chicken"]
    elif value < 1414:
        return sound_LUT["Dog"]
    elif value < 1886:
        return sound_LUT["Silence"]
    elif value < 2357:
        return sound_LUT["Elephant"]
    elif value < 3000:
        return sound_LUT["Horse"]
    else:
        return sound_LUT["Sheep"]

def setPicture(pot):
    value = read_value(pot)
    if value < 471:
        return "red"
    elif value < 943:
        return "yellow"
    elif value < 1414:
        return "green"
    elif value < 1886:
        return "Nochange"
    elif value < 2357:
        return "rocket"
    elif value < 3000:
        return "crab"
    else:
        return "cactus"

async def pattern_task():
    """Async task to handle LED patterns"""
    global pattern_choice, pattern_button_state
    
    while True:
        R, G, B = setColor(color)
        n = 5
        
        if pattern_choice == 0:
            # Chase pattern
            for i in range(4 * n):
                for j in range(n):
                    np[j] = (0, 0, 0)
                np[i % n] = (R, G, B)
                np.write()
                await asyncio.sleep_ms(25)
                
        elif pattern_choice == 1:
            # Alternating chase
            for i in range(4 * n):
                for j in range(n):
                    np[j] = (R, G, B)
                if (i // n) % 2 == 0:
                    np[i % n] = (0, 0, 0)
                else:
                    np[n - 1 - (i % n)] = (0, 0, 0)
                np.write()
                await asyncio.sleep_ms(60)
                
        elif pattern_choice == 2:
            # Fade in/out
            for i in range(0, 2 * 256, numberofLED):
                for j in range(n):
                    if (i // 256) % 2 == 0:
                        val = i & 0xff
                    else:
                        val = 255 - (i & 0xff)
                    
                    # Scale RGB values properly
                    scaled_r = (R * val) // 255
                    scaled_g = (G * val) // 255
                    scaled_b = (B * val) // 255
                    np[j] = (scaled_r, scaled_g, scaled_b)
                np.write()
                await asyncio.sleep_ms(10)
                

        
        # Small delay between pattern cycles
        await asyncio.sleep_ms(50)

async def button_handler():
    """Async task to handle button presses"""
    global pattern_pressed, send_pressed, pattern_choice, pattern_button_state
    
    while True:
        if pattern_pressed:
            pattern_pressed = False
            print("Pattern button pressed")
            pattern_choice = (pattern_choice + 1) % 3
            print(f"Pattern choice: {pattern_choice}")
            await asyncio.sleep_ms(200)  # Debounce
            
        if send_pressed:
            send_pressed = False
            print("Send button pressed")
            config = {
                "SetConfig": {
                    "sound": setSound(sound),
                    "light": setColor(color),
                    "pattern": pattern_choice,
                    "TrafficL": setPicture(picture) # this is currently for the light panel (pre traffic light)
                }
            }
            e.send(peer, str(config))
            print(str(config))
            await asyncio.sleep_ms(200)  # Debounce
            
        await asyncio.sleep_ms(10)

async def sensor_monitor():
    """Async task to monitor sensor values"""
    while True:
        # You can add sensor monitoring logic here if needed
        # For now, just a placeholder that yields control
        await asyncio.sleep_ms(100)

async def main():
    """Main async function to run all tasks concurrently"""
    print("Starting asyncio NeoPixel controller...")
    
    # Create tasks for concurrent execution
    tasks = [
        asyncio.create_task(pattern_task()),
        asyncio.create_task(button_handler()),
        asyncio.create_task(sensor_monitor())
    ]
    
    # Run all tasks concurrently
    await asyncio.gather(*tasks)

# Start the asyncio event loop
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program interrupted")
    finally:
        # Turn off all LEDs on exit
        for i in range(numberofLED):
            np[i] = (0, 0, 0)
        np.write()
