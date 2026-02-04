from machine import SoftI2C, Pin, ADC
import time, json
import ubinascii

import  utilities.now as now

ROW = 10

class Control:
    def connect(self, antenna):
        def my_callback(msg, mac, rssi):
            if not ('/ping' in msg):
                print(mac, msg, rssi)

        self.n = now.Now(antenna, my_callback)
        self.n.connect() # antenna is handled in the Now class (no parameter)
        self.mac = self.n.wifi.config('mac')
        print(self.mac)
        
    def shutdown(self):
        stop = json.dumps({'topic':'/game', 'value':-1})
        self.n.publish(stop)
        
    def ping(self):
        ping = json.dumps({'topic':'/ping', 'value':1})
        self.n.publish(ping)
        
    def notify(self):
        note = json.dumps({'topic':'/notify', 'value':1})
        self.n.publish(note)
        print('notified')
        
    def choose(self, game):
        encoded_bytes = ubinascii.b2a_base64(self.mac)
        encoded_string = encoded_bytes.decode('ascii')

        setup = json.dumps({'topic':'/game', 'value':(game,encoded_string)})
        self.n.publish(setup)


class Display:
    def __init__(self):
        import ssd1306
        import ledmatrix
        
        i2c = SoftI2C(scl = Pin(7), sda = Pin(6))
        self.display = ssd1306.SSD1306_I2C(128, 64,i2c)
        self.leds = ledmatrix.LEDMATRIX(i2c)
        ledmatrix.apple(self.leds)
        self.row = 1
        self.last_row = None
        
    def clear_screen(self):
        self.display.fill(0)
        self.display.show()
        self.row = 1
        
    def add_text(self, text):
        self.display.text(text, 2, self.row, 1)  # 1 means white text
        self.row += ROW
        self.display.show()

    def box_row(self, row):
        if self.last_row: self.display.rect(0,self.last_row,128,ROW-1,0)
        self.display.rect(0,row,128,ROW-1,1)
        self.last_row = row
        self.display.show()
        
    def close(self):
        self.clear_screen()

class Button:
    def __init__(self, pin):
        self.button = Pin(pin, Pin.IN, Pin.PULL_UP)
        self.button.irq(handler=self.update, trigger=Pin.IRQ_FALLING)
        self.state = 0
        
    def update(self, p):
        accept = False
        start = time.ticks_ms()
        #self.state = 0
        while self.button.value() == 0:
            if time.ticks_ms()-start > 50:
                accept = True
                print("button pressed")
                time.sleep(0.2)
                self.state = 1
               
    def close(self):
        self.button.irq = None

class Controller(Control):
    def __init__(self):
        self.display = Display()
        self.display.clear_screen()
        self.display.add_text('1: Music')
        self.display.add_text('2: Shake')
        self.display.add_text('3: Hot Cold')
        self.display.add_text('4: Jump')
        self.display.add_text('5: Clap')
        self.display.add_text('6: Rainbow')
        self.display.add_text('7: Shutdown')
        
        self.display.last_row = None
        self.row = 1

        self.button_up = Button(10)
        self.button_select = Button(9)
        self.button_down = Button(8)
        self.pot = ADC(Pin(3))
        self.pot.atten(ADC.ATTN_11DB) # the pin expects a voltage range up to 3.3V

if __name__ == '__main__':
    controller = Controller()

    def scroll():
        return 1+10*int(((controller.pot.read() + 1)/4095 * 6))

    old_scroll_val = scroll()
    controller.display.box_row(old_scroll_val)
    controller.connect(antenna=False)  # Set to True if external antenna connected

    i = 0
    while True:
        i += 1
        time.sleep(0.1)
        #if i%10 == 1: controller.ping()
        controller.ping()
        
        scroll_val = scroll()
        controller.display.box_row(scroll_val)
        select = int(scroll_val/10)
        if scroll_val != old_scroll_val:
            if controller.button_select.state == 1:
                controller.button_select.state = 0
                controller.display.leds.display_emoji(20+select,1,1)
                print('select ', select)
                controller.choose(select)
                controller.display.leds.display_color_bar(0,10)
                time.sleep(1)
                old_scroll_val = scroll_val
                
        else:
            if controller.button_select.state == 1:
                controller.button_select.state = 0
                controller.display.leds.display_emoji(29,1,1)
                print('select again ', select)
                controller.choose(select)
                controller.display.leds.display_color_bar(0,10)

# *    emoji: Set a number from 0 to 29 for different emoji.
# *        0    smile        10    heart           20    house
# *        1    laugh        11    small heart     21    tree
# *        2    sad          12    broken heart    22    flower
# *        3    mad          13    waterdrop       23    umbrella
# *        4    angry        14    flame           24    rain
# *        5    cry          15    creeper         25    monster
# *        6    greedy       16    mad creeper     26    crab
# *        7    cool         17    sword           27    duck
# *        8    shy          18    wooden sword    28    rabbit
# *        9    awkward      19    crystal sword   29    cat
# *        30   up           31    down            32    left
# *        33   right        34    smile face 3
