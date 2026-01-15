from machine import I2S, Pin
import math
import time
import machine

import os
import ustruct


import neopixel

NUM_LEDS = 67

np = neopixel.NeoPixel(machine.Pin(21), NUM_LEDS)

np.fill((0,0,10)) # set to neopixels off, full brightness
np.write()

def hue(pos, brightness=10):
    """
    Generate RGB color across 0-255 positions.
    
    :param pos: Position in the color wheel (0-255)
    :return: Tuple (R, G, B) - the color corresponding to the position
    """
    bright_scale = brightness/10
    
    if pos < 85:
        return (int((255 - pos*3)*bright_scale), int((pos * 3)*bright_scale), 0)  # 0 is red
    elif pos < 170:
        pos -= 85
        return (0, int((255 - pos*3)*bright_scale), int((pos * 3)*bright_scale))  # 85 is green
    else:
        pos -= 170
        return (int((pos*3)*bright_scale), 0, int((255 - pos * 3)*bright_scale))  # 170 is blue


def rainbow_cycle(wait, count, brightness=10):
    """Display a rainbow cycle across the entire LED strip."""
    for j in range(256):  # Loop through 256 color positions
        print(j)
        for i in range(count):  # Loop through each LED
            pixel_index = (i * 256 // count) + j  # Calculate color position
            np[i] = hue(pixel_index & 255, brightness)  # Set the LED to the color
        np.write() 
        time.sleep(wait)  # Pause for a short time before the next update
        


'''
LRC (Left/Right Clock)  D8
BCLK (Bit Clock) - D9
DIN (Data In) -D10

'''


# I2S Setup Function with Variable Rate
def setup_i2s(sample_rate, bit_depth,BUFFER_SIZE = 1024):
    i2s = I2S(
        0,
        sck=Pin(20),   # Serial Clock BCLK D9
        ws=Pin(18),    # Word Select / LR Clock D10
        sd=Pin(19),    # Serial Data
        mode=I2S.TX,
        bits=bit_depth,
        format=I2S.MONO,
        rate=sample_rate,
        ibuf=BUFFER_SIZE
    )
    return i2s

# Helper function to parse the .wav header and extract audio parameters
def parse_wav_header(file):
    file.seek(0)  # Ensure we're at the start of the file
    header = file.read(44)  # Standard .wav header size
    sample_rate = ustruct.unpack('<I', header[24:28])[0]
    bit_depth = ustruct.unpack('<H', header[34:36])[0]
    return sample_rate, bit_depth



def play_sound(path):
        # Open the .wav file from the SD card
    with open(path, "rb") as wav_file:
        sample_rate, bit_depth = parse_wav_header(wav_file)
        print(sample_rate, bit_depth)
        i2s = setup_i2s(sample_rate, bit_depth)

        # Skip the header and begin reading audio data
        wav_file.seek(44)  # Start of PCM data after 44-byte header

        # Buffer to hold PCM data read from the file
        buffer = bytearray(1024)
        
        while True:
            try:
                num_read = wav_file.readinto(buffer)
                if num_read == 0:
                    break  # End of file
                i2s.write(buffer[:num_read])  # Write to I2S in chunks
            except KeyboardInterrupt:
                print("CTRL C pressed")


try:
    print("playing")
            
    rainbow_cycle(.001, 67, 8)


    #play_sound("hello.wav")
    #play_sound("notet1.wav")
    rainbow_cycle(.001, 67, 1)
    #play_sound("notet2.wav")
    rainbow_cycle(.001, 67, 1)
    rainbow_cycle(.001, 67, 1)
    rainbow_cycle(.001, 67, 1)
    rainbow_cycle(.001, 67, 1)
   # play_sound("notet3.wav")
#     time.sleep(0.5)
#     play_sound("notet4.wav")
#     time.sleep(0.5)
#     play_sound("notet5.wav")
#     time.sleep(0.5)
#     play_sound("notet6.wav")
#     time.sleep(0.5)
#     play_sound("notet7.wav")
#     time.sleep(0.5)
#     play_sound("notet8.wav")
#     time.sleep(0.5)

    time.sleep(5)
    print('sleeping')

    
except Exception as e:
    print("An error occurred:", e)
finally:
    pass