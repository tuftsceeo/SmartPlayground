#Before running this code, save splat_button in the esp
# demo code - plays all sounds 
from splat_button import OpenSplat
import time
splat = OpenSplat("AB:42:00:00:1A:C4") # Change the MAC address based on the splat
splat.connect(timeout = 5)


#Sound demo
'''
for i in range(50):
    splat.playSound(i,255)
    time.sleep(0.5)
'''

#Light demo

#splat.setLEDs([5,9,10],255,0,0) #for specific LEDs
#splat.allLEDsOff() #Turn all LEDs off
#