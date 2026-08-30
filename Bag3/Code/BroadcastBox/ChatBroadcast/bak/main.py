import RS232
myRS232 = RS232.CEEO_RS232(divName = 'all_things_rs232', suffix = '1', myCSS = False, default_code='sd')


myRS232.python.code = '''
from neopixel import NeoPixel
from machine import Pin

def demo():

    np = NeoPixel(Pin(20), 25)
    np[0] = (1,1,0)
    np.write()
        
demo()
'''