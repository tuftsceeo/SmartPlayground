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
        2:(255,127,0), #orange
        3:(255,255,0), #yellow
        4:(0,255,0), #green
        5:(0,255,255), #cyan
        6:(0,0,255), #blue
        7:(100,0,190), #purple
        8:(255,70,200), #pink
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
        self.NUM_LEDS = 14

        self.sw1 = Pin(0, Pin.IN, Pin.PULL_UP)
        self.sw2 = Pin(1, Pin.IN, Pin.PULL_UP)
        self.sw3 = Pin(2, Pin.IN, Pin.PULL_UP)
        self.sw4 = Pin(21, Pin.IN, Pin.PULL_UP)

        self.LED = Pin(22, Pin.OUT)
        self.strip = neopixel.NeoPixel(self.LED, self.NUM_LEDS)

        self.power_PWM = machine.Pin(23)
        self.pwmV = machine.PWM(self.power_PWM)
        self.pwmV.freq(1000)
        self.pwmV.duty(1000)
        
        #self.calib_vals = self.calibrate()
        self.is_pressed = False
        
        #Initialize ESPNOW
        self.networking = Networking(True, False) #First bool is for network info messages, second for network debug messages
        self.networking.ap._ap.active(False)
        self.broadcast_mac = b'\xff\xff\xff\xff\xff\xff'
        self.networking.aen.add_peer(self.broadcast_mac, "All")
        self.networking.name = name
        
        #self.modules = ['Lion', 'Tiger', 'Elephant', 'Giraffe', 'Duck', 'Frog', 'Dog', 'Leopard', 'Zebra','Monkey']
        self.modules = ['Duck']
    
    def calibrate(self):
        return self.sw1.value() | self.sw2.value()<<1 | self.sw3.value()<<2 | self.sw4.value()<<3

    def read_buttons(self):
        return self.sw1.value() | self.sw2.value()<<1 | self.sw3.value()<<2 | self.sw4.value()<<3

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
            if self.networking.aen.peer_name(key) in self.modules and rssi > -100:
                self.networking.aen.send(key, self.name)
        
    def play_sound(self):
        path = self.n[int(self.name)]
        # Open the .wav file from the SD card
        with open(path, "rb") as wav_file:
            sample_rate, bit_depth = self.parse_wav_header(wav_file)
            print(sample_rate, bit_depth)
            i2s = self.setup_i2s(sample_rate, bit_depth)

            # Skip the header and begin reading audio data
            wav_file.seek(44)  # Start of PCM data after 44-byte header

            # Buffer to hold PCM data read from the file
            buffer = bytearray(1024)
            
            for i in range(0,40):
                try:
                    num_read = wav_file.readinto(buffer)
                    if num_read == 0:
                        break  # End of file
                    i2s.write(buffer[:num_read])  # Write to I2S in chunks
                except KeyboardInterrupt:
                    print("CTRL C pressed")
        
    # I2S Setup Function with Variable Rate
    def setup_i2s(self, sample_rate, bit_depth,BUFFER_SIZE = 1024):
        i2s = I2S(
            0,
            sck=Pin(20),   # Serial Clock BCLK 22
            ws=Pin(18),    # Word Select / LR Clock LRC 23
            sd=Pin(19),    # Serial Data 21
            #sck=Pin(22),   # Serial Clock BCLK 22
            #ws=Pin(23),    # Word Select / LR Clock LRC 23
            #sd=Pin(21),    # Serial Data 21
            mode=I2S.TX,
            bits=bit_depth,
            format=I2S.MONO,
            rate=sample_rate,
            ibuf=BUFFER_SIZE
        )
        return i2s

    # Helper function to parse the .wav header and extract audio parameters
    def parse_wav_header(self, file):
        file.seek(0)  # Ensure we're at the start of the file
        header = file.read(44)  # Standard .wav header size
        sample_rate = ustruct.unpack('<I', header[24:28])[0]
        bit_depth = ustruct.unpack('<H', header[34:36])[0]
        return sample_rate, bit_depth
