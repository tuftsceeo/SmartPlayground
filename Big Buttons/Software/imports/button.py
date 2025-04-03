import time
import struct
import math
from networking import Networking
from machine import Pin, SoftI2C, PWM, ADC, I2S
import neopixel
import machine
import os
import ustruct

class Splat:
    def __init__(self, name = '1'): #change to splat number
        self.name = name
        
        #Color dictionary
        self.c = {
        1:(255,0,0), #red
        2:(255,100,0), #orange
        3:(255,255,0), #yellow
        4:(0,255,0), #green
        5:(0,255,255), #cyan
        6:(0,0,255), #blue
        7:(50,0,255), #purple
        8:(150,70,200), #pink
        }
        
        #Note dictionary
        self.n = {
        1:"notet1.wav",
        2:"notet2.wav",
        3:"notet3.wav",
        4:"notet4.wav",
        5:"notet5.wav",
        6:"notet6.wav",
        7:"notet7.wav",
        8:"notet8.wav",
        }
        
        # Define the number of LEDs
        self.NUM_LEDS = 4

        self.sw1 = Pin(0, Pin.IN, Pin.PULL_UP)
        
        self.LED = Pin(1, Pin.OUT)
        self.strip = neopixel.NeoPixel(self.LED, self.NUM_LEDS)

        self.power_PWM = machine.Pin(23)
        self.pwmV = machine.PWM(self.power_PWM)
        self.pwmV.freq(1000)
        self.pwmV.duty(1000)
        
        self.calib_vals = self.calibrate()
        
        self.is_pressed = False
        self.is_asleep = False
        
        #Initialize ESPNOW
        self.initialize_now()
        
        self.modules = ['Lion', 'Tiger', 'Elephant', 'Giraffe', 'Duck', 'Frog', 'Dog', 'Leopard', 'Zebra','Monkey']
    
    def calibrate(self):
        return self.sw1.value()

    def read_buttons(self):
        return self.sw1.value()
    
    def initialize_now(self):
        self.networking = Networking(True, False) #First bool is for network info messages, second for network debug messages
        self.networking.ap._ap.active(False)
        self.broadcast_mac = b'\xff\xff\xff\xff\xff\xff'
        self.networking.aen.add_peer(self.broadcast_mac, "All")
        self.networking.name = self.name
    
    def deinitialize_now(self):
        self.networking.sta._sta.active(False)
        self.networking.aen._aen.active(False)
    
    def button_sleep(self):
        self.deinitialize_now()
        
    def button_awaken(self):
        self.initialize_now()

    # Function to set all LEDs to a specific color
    def set_color(self, d = None):
        if d == None:
            d = int(self.name)
        color = self.c[d]
        for i in range(self.NUM_LEDS):
            self.strip[i] = color
        self.strip.write()

    # Function to turn off all LEDs
    def clear_strip(self):
        for i in range(self.NUM_LEDS):
            self.strip[i] = (0,0,0)
        self.strip.write()
        
    def animate(self):
        for i in range(50):
            self.strip[i%14] = (10, 255, 0)
            self.strip[(i+1)%14] = (255, 0, 200)
            self.strip[(i+2)%14] = (255, 0, 0)
            self.strip.write()
            time.sleep(0.05)
            self.strip[i%14] = (0, 0, 0)
            self.strip[(i+1)%14] = (0, 0, 0)
            self.strip[(i+2)%14] = (0, 0, 0)
                
    # Example of a simple animation: Fade between colors
    def fade_colors(self):
        for intensity in range(0, 255, 5):
            self.set_color(intensity, 0, 0)  # Red
            time.sleep(0.05)
        for intensity in range(255, 0, -5):
            self.set_color(intensity, 0, 0)  # Red
            time.sleep(0.05)
            
    def send_to_close_modules(self):
        rssi_buffer = []
        key_buffer = []
        self.networking.aen.ping(self.broadcast_mac)
        time.sleep(0.1)
        for key in self.networking.aen.rssi():
            rssi = self.networking.aen.rssi()[key][0]
            print(rssi)
            print(self.networking.aen.peer_name(key))
            if self.networking.aen.peer_name(key) in self.modules and rssi > -75:
                self.networking.aen.send(key, self.name)
        