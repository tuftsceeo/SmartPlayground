from machine import SoftI2C, Pin, ADC
import time, json
import micropython
import ubinascii
import asyncio
from collections import deque

import  utilities.now as now
import config 
tool = config.Controller_settings

ROW = 10

possible_games = [f'{i}: {game[0].__name__}' for i,game in enumerate(tool.games)]

class Control:
    def connect(self):
        def my_callback(msg, mac, rssi):
            try:
                self.queue.append((msg, mac, rssi))
            except Exception as e:
                print(f"Callback error: {e}")

        self.n = now.Now(tool.antenna, my_callback)
        self.n.connect()
        self.mac = self.n.wifi.config('mac')
        print('MAC: ',self.mac)
        
        self.queue = deque([],1000)
        self.topics = {}

    async def pop_queue(self):
        if not len(self.queue):
            return
        try:
            await asyncio.sleep(0)
            (msg, mac, rssi) = self.queue.popleft()
            if not ('/ping' in msg): print(mac, msg, rssi)
            payload = json.loads(msg)
            topic = payload['topic']
            value = payload['value']
            num = 1
            if topic in self.topics.keys():
                num = 1 + self.topics[topic][1]
            
            self.topics[topic] = (value,num)
            #print(self.topics[topic])
        except Exception as e:
            print('pop error ',e)
            
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
        print(setup)
        self.n.publish(setup)


class Display:
    def __init__(self):
        import ssd1306

        i2c = SoftI2C(scl = Pin(7), sda = Pin(6))
        self.display = ssd1306.SSD1306_I2C(128, 64,i2c)

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
        
    def box_on(self):
        self.display.rect(0,1,128,ROW-1,1)
        self.display.show()        
        
    def close(self):
        self.clear_screen()

class Button:
    def __init__(self, pin, callback = None):
        self.button = Pin(pin, Pin.IN, Pin.PULL_UP)
        self.button.irq(handler=self.update, trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING)
        self.state = self.button.value()
        self.callback = callback
        self.last_trigger = 0
        
    def update(self, p):
        micropython.schedule(self.run_callback, p)

    def run_callback(self, p):
        current = time.ticks_ms()
        if time.ticks_diff(current, self.last_trigger) > 50:
            self.last_trigger = current
            self.state = p.value()
            if self.callback: self.callback(self.state)
               
    def close(self):
        self.button.irq = None

class Controller(Control):
    def __init__(self):
        self.display = Display()
        self.display.clear_screen()
        self.display.add_text('1: Music')
        
        self.display.last_row = None
        self.game = 0

        def update(state, inc):
            if state: return
            self.display.clear_screen()
            self.game = (self.game + inc) % len(possible_games)
            self.display.add_text(possible_games[self.game])
            if inc == 0:
                self.choose(self.game)
                print(f'choose {self.game}')
                time.sleep(0.1)
                self.choose(self.game)
            
        def up(state):
            update(state, 1)
        self.button_up = Button(8, up)
        
        def select(state):
            self.display.box_on()
            update(state, 0)
        self.button_select = Button(9, select)
        
        def down(state):
            update(state, -1)
        self.button_down = Button(10, down)
        
        self.pot = ADC(Pin(3))
        self.pot.atten(ADC.ATTN_11DB) # the pin expects a voltage range up to 3.3V

async def main():
    controller = Controller()
    controller.connect()
    try:
        last_display_update = 0
        display_interval = 1.0
        
        while True:
            while len(controller.queue):
                await controller.pop_queue()
                await asyncio.sleep(0)  # Yield after each item
            
            # Display update on separate timer
            current_time = time.time()
            if current_time - last_display_update >= display_interval:
                controller.display.clear_screen()
                controller.display.add_text(possible_games[controller.game])
                for s in controller.topics.items():  # topic, value, number
                    controller.display.add_text(f'{s[1][1]} {s[0].replace('/battery','')}: {s[1][0]}')
                last_display_update = current_time
            await asyncio.sleep(0.1)
            controller.ping()

    except Exception as e:
        print('main error: ',e)
    finally:
        print('main shutting down')

asyncio.run(main())




