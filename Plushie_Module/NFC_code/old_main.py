
from machine import Pin, SoftI2C, PWM, ADC
from files import *
import time
import machine
import prefs



#nav switches
switch_down = Pin(8, Pin.IN)
switch_select = Pin(9, Pin.IN)
switch_up= Pin(10, Pin.IN)


def setmode():
    #if up and down buttons are pressed on start up toggle the mode
    mode = prefs.mode
    if not switch_down.value() and not switch_up.value() and switch_select.value():
        import icons
        i2c = SoftI2C(scl = Pin(7), sda = Pin(6))
        display = icons.SSD1306_SMART(128, 64, i2c,switch_up)
        if mode == 0:
            display.showmessage("Web Connect")
            mode = 1
        else:
            display.showmessage("Standalone")
            mode = 0
        resetprefs(mode)  #resets preference file to False

    
    return mode
    

#detect mode on start up

mode = setmode()
       

if mode == 0:
    import standalone
else:
    import webconnect

