############## Designs Library, 16 x 16 LED Light Matrix ##############################
##### Images_Library.py
import ubluetooth
import time
import struct
import neopixel

import machine
from machine import Pin

# Configure the LED strip
pin = machine.Pin(18)
num_leds = 256  # for a 16 by 16 matrix
strip = neopixel.NeoPixel(pin, num_leds)

class Images_16x16:
    strip = neopixel.NeoPixel(pin, num_leds)
    def clear():
        Images_16x16.strip.fill((0, 0, 0))
        Images_16x16.strip.write()

    def set_led(index, color):
        Images_16x16.strip[index] = color
        Images_16x16.strip.write()

    def set_leds(indices, color):
        for index in indices:
            Images_16x16.strip[index] = color
        Images_16x16.strip.write()

    intensity = .25 # or 0.05 for inside
    #intensity = 1 #for outside

    # Possible Images: Happy, Sad, Heart, Crab, Star, Crown, Rocket, X_Mark, O_Mark, Cactus, QuestionMark

    def Happy():
        Eyes = [212,213,214,217,218,219,196,197,197,198,201,202,203,180,181,182,185,186,187,164,165,166,169,170,171,148,149,150,153,154,155,132,133,134,137,138,139]
        Happy = [96,97,94,65,66,50,51,52,53,54,55,56,57,58,59,60,61,35,36,37,38,39,40,41,42,43,44,77,78,81,110,111,95,80]
        Images_16x16.set_leds(Eyes, (int(Images_16x16.intensity*255), 0 , int(Images_16x16.intensity*255)))
        strip.write()
        Images_16x16.set_leds(Happy, (int(Images_16x16.intensity*255), 0 , int(Images_16x16.intensity*255)))
        strip.write()

    def Sad():
        Eyes = [212,213,214,217,218,219,196,197,197,198,201,202,203,180,181,182,185,186,187,164,165,166,169,170,171,148,149,150,153,154,155,132,133,134,137,138,139]
        Sad = [31,30,33,34,61,60,67,68,69,70,71,72,73,74,75,76,85,86,87,88,89,90,51,50,45,46,17,16]
        Images_16x16.set_leds(Eyes, (int(Images_16x16.intensity*255), 0 , int(Images_16x16.intensity*255)))
        strip.write()
        Images_16x16.set_leds(Sad, (int(Images_16x16.intensity*255), 0 , int(Images_16x16.intensity*255)))
        strip.write()

    def Heart():
        Heart = [167,185,195,196,197,189,161,159,128,127,97,93,67,59,37,25,7,23,41,53,75,83,109,113,142,145,173,179,203,202,201,183]
        Images_16x16.set_leds(Heart, (int(Images_16x16.intensity*255), 0, 0))
        strip.write()

    def Crab():
        
        Eyes = [134, 137]
        Body = [118,121,100,101,102,103,104,105,106,107, 84,85,86,87,88,89,90,91,68,69,70,71,72,73,74,75,53,54,55,56,57,58]
        Legs = [65,93,92,83,82,78,60,34,36,27,43,20,51,45]
        Claws = [192,191,188,160,163,158,157,130,124,115,141,146,145,179,172,175,176,207]

        Images_16x16.set_leds(Eyes, (int(Images_16x16.intensity*255), int(Images_16x16.intensity*255), int(Images_16x16.intensity*255)))
        Images_16x16.strip.write()
        Images_16x16.set_leds(Body, (int(Images_16x16.intensity*255), 0 , 0))
        Images_16x16.strip.write()
        Images_16x16.set_leds(Claws, (int(Images_16x16.intensity*255), 0 , 0))
        Images_16x16.strip.write()
        Images_16x16.set_leds(Legs, (int(Images_16x16.intensity*255), 0 , 0))
        Images_16x16.strip.write()
      
    def Star():
        top = [199,183,184,185,162,163,164,165,166,167,168,169,170,171,172,148,149,150,151,152,153,154,155,156,132,133,134,135,136,137,138]
        bottom = [118,119,120,121,122,100,101,102,103,104,105,106,84,85,86,87,89,90,91,92,66,67,68,74,75,76,51,61]
        Images_16x16.set_leds(top, (int(Images_16x16.intensity*255), int(Images_16x16.intensity*100), 0))
        strip.write()
        Images_16x16.set_leds(bottom, (int(Images_16x16.intensity*255), int(Images_16x16.intensity*100), 0))
        Images_16x16.strip.write()
       
    def Crown():
        base = [132,133,134,135,136,137,138,115,116,117,118,119,120,121,122,123,124,125,99,100,101,102,103,104,105,106,107]
        spikes = [149,150,151,152,153,154,155, 159,129,130,145,140,141,188,163,164,166,167,168,184,170,171,180,199]
        extra = [85,86,87,88,89,90,91]
        Images_16x16.set_leds(base, (int(Images_16x16.intensity*200), int(Images_16x16.intensity*100), 0))
        Images_16x16.strip.write()
        Images_16x16.set_leds(spikes, (int(Images_16x16.intensity*200), int(Images_16x16.intensity*100), 0))
        Images_16x16.strip.write()
        Images_16x16.set_leds(extra, (int(Images_16x16.intensity*200), int(Images_16x16.intensity*100), 0))
        Images_16x16.strip.write()

    def Rocket(): 
        Top = [231,217,216,215,197,198,199,200,201]
        Body = [165,166,167,168,169,154,150,133,134,136,137,118,119,120,121,122,101,102,103,104,105,90,89,88,87,86,69,70,71,72,73,55,56,57,182,183,184,185,186]
        Window_Sides = [167,151,152,153,135,85,74,75,52,91,68,67,60]
        Fire = [39,23,24,25,7]
        Images_16x16.set_leds(Top, (int(Images_16x16.intensity*200), 0, 0))
        Images_16x16.strip.write()
        Images_16x16.set_leds(Body, (int(Images_16x16.intensity/2*255), int(Images_16x16.intensity/2*255), int(Images_16x16.intensity/2*255)))
        Images_16x16.strip.write()
        Images_16x16.set_leds(Window_Sides, (0, int(Images_16x16.intensity*5), int(Images_16x16.intensity*255)))
        Images_16x16.strip.write()
        Images_16x16.set_leds(Fire, (int(Images_16x16.intensity*255), int(Images_16x16.intensity*60), 0))
        Images_16x16.strip.write()

    def QuestionMark():
        Mark = [23,24,39,40,71,72,87,88,103,104,119,120,136,137,149,150,170,171,180,181,202,203,213,214,215,216,217,218,230,231,232,233,196,197,187,186,164,165,198,201]
        Images_16x16.set_leds(Mark, (0, int(Images_16x16.intensity*5), int(Images_16x16.intensity*255)))
        Images_16x16.strip.write()

    def X(): #X_Mark
        X = [222,221,194,195,188,187,164,165,154,153,134,135,120,119,104,105,86,85,74,75,51,52,44,45,18,17,210,209,204,205,180,179,170,171,150,149,136,137,102,103,90,89,68,69,60,59,34,35,30,29]
        Images_16x16.set_leds(X, (int(Images_16x16.intensity*255), 0 , 0))
        strip.write()

    def O_Mark():
        sides = [189,188,162,163,156,157,130,131,124,125,98,99,92,93,66,67,178,179,172,173,146,147,140,141,114,115,108,109,83,82,76,77]
        edges = [210,211,212,213,214,215,216,217,218,219,220,221,194,195,196,197,198,199,200,201,202,203,204,205,50,51,52,53,54,55,56,57,58,59,60,61,34,35,36,37,38,39,40,41,42,43,44,45]
        Images_16x16.set_leds(sides, (0, int(Images_16x16.intensity*255) , 0))
        strip.write()
        Images_16x16.set_leds(edges, (0, int(Images_16x16.intensity*255) , 0))
        strip.write()

    def Cactus():
        arms = [190,189,161,162,163,154,155,156,157,158,130,131,132,133,122,123,124, 145,146,140,141,142,113,114,115,116,117,106,107,108,109,83,84,85]
        body = [38,39,40,41,54,55,56,57,70,71,72,73,86,87,88,89,102,103,104,105,118,119,120,121,134,135,136,137,150,151,152,153,166,167,168,169,182,183,184,185,198,199,200,201,214,215,216,217,231,232]
        Images_16x16.set_leds(arms, (int(Images_16x16.intensity*70), int(Images_16x16.intensity*146), 0))
        Images_16x16.strip.write()
        Images_16x16.set_leds(body, (int(Images_16x16.intensity*70), int(Images_16x16.intensity*146), 0))
        Images_16x16.strip.write()
    
    def G_Border():
        ends = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15, 240,241,242,243,244,245,246,247,248,249,250,251,252,253,254,255]
        sides = [16,47,48,79,80,111,112,143,144,175,176,207,208,239, 31,32,63,64,95,96,127,128,159,160,191,192,223,224]
        Images_16x16.set_leds(ends, (0, int(Images_16x16.intensity*255), 0))
        Images_16x16.strip.write()
        Images_16x16.set_leds(sides, (0, int(Images_16x16.intensity*255), 0))
        Images_16x16.strip.write()
        
    def R_Border():
        ends = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15, 240,241,242,243,244,245,246,247,248,249,250,251,252,253,254,255]
        sides = [16,47,48,79,80,111,112,143,144,175,176,207,208,239, 31,32,63,64,95,96,127,128,159,160,191,192,223,224]
        Images_16x16.set_leds(ends, (int(Images_16x16.intensity*255), 0, 0))
        Images_16x16.strip.write()
        Images_16x16.set_leds(sides, (int(Images_16x16.intensity*255), 0, 0))
        Images_16x16.strip.write()
    
    def TF_Red():
        light = [229,230,231,232,233, 218,217,216,215,214, 197,198,199,200,201, 182,183,184,185,186, 165,166,167,168,169]
        Images_16x16.set_leds(light, (int(Images_16x16.intensity*255), 0, 0))
        Images_16x16.strip.write()
        
    def TF_Yellow():
        light = [150,151,152,153,154, 133,134,135,136,137, 118,119,120,121,122, 101,102,103,104,105, 86,87,88,89,90]
        Images_16x16.set_leds(light, (int(Images_16x16.intensity*255), int(Images_16x16.intensity*100), 0))
        Images_16x16.strip.write()
    
    def TF_Green():
        light = [69,70,71,72,73, 54,55,56,57,58, 37,38,39,40,41, 22,23,24,25,26, 5,6,7,8,9]
        Images_16x16.set_leds(light, (0, int(Images_16x16.intensity*255), 0))
        Images_16x16.strip.write()
        
