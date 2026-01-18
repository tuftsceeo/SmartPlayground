import time
import asyncio
import json
import ubinascii

from collections import deque

import utilities.utilities as utilities
import utilities.lights as lights
import utilities.now as now
import utilities.i2c_bus as i2c_bus
from utilities.colors import *

from games.sound import Notes
from games.shake import Shake
from games.jump import Jump
from games.hotcold import Hot_cold
from games.clap import Clap
from games.rainbow import Rainbow
from games.hibernate import Hibernate
from games.pattern_rainbow_btn import Pattern_btn
from games.pattern_rainbow_plushie import Pattern_plush

class Stuffie:
    def __init__(self):
        self.mac = None
        self.espnow = None

        self.game = -1
        self.running = False
        self.topic = ''
        self.value = -1
        self.task = None
        self.hidden_gem = None
        self.color = GREEN
        self.queue = deque([], 20)

        self.lights = lights.Lights()
        self.lights.default_color = GREEN
        self.lights.default_intensity = 0.1
        self.lights.all_off()
        
        self.accel = i2c_bus.LIS2DW12()
        self.battery = i2c_bus.Battery()
        self.button = utilities.Button()
        self.buzzer = utilities.Buzzer()
        self.buzzer.stop()
        self.hibernate = utilities.Hibernate()
        
        # this will initialize each game and pass in attributes of this class - (self) - 
        self.game_names = [Notes(self), Shake(self), Hot_cold(self), Jump(self),
                           Clap(self), Rainbow(self), Hibernate(self), Pattern_btn(self), 
                           Pattern_plush(self)]
        self.response_times = [0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.5]
        
    def startup(self):
        print('Starting up')
        self.lights.on(0)
        self.espnow = now.Now(self.now_callback)
        self.espnow.connect()
        self.lights.on(1)
        self.mac = self.espnow.wifi.config('mac')
        print('my mac address is ',[hex(b) for b in self.mac])
        self.lights.on(2)
        self.topic = ''
        self.msg = ''
        
    def publish(self, msg):
        self.espnow.publish(json.dumps(msg))
        
    def start_game(self, number):
        if number < 0 or number >= len(self.game_names):
            print('illegal game number')
            return
        if self.game == number:
            print(f'notify {number}')
            self.topic = '/notify'
            return
        print('starting game ', number)
        self.running = True
        self.game = number
        
        # now run the game -each game class should have a def run(response time) in it
        self.task = asyncio.create_task(self.game_names[number].run(self.response_times[number]))
        print(f'started {number}')
        
    async def stop_game(self, number):
        print(f'trying to stop {number}')
        self.running = False
        await self.task

    def close(self):
        if self.game >= 0:
            self.stop_game(self.game)
        if self.espnow: self.espnow.close()
        self.lights.all_off()
        self.buzzer.stop()

    def now_callback(self, msg, mac, rssi):
        try:
            self.queue.append((msg, mac, rssi))
        except Exception as e:
            print(f"Callback error: {e}")
    
            
    async def pop_queue(self):
        if not len(self.queue):
            return
        await asyncio.sleep(0)  # yield to wifi
        try:
            (msg, mac, rssi) = self.queue.pop()
            #print(msg, mac, rssi)
            payload = json.loads(msg)
            self.topic = payload['topic']
            self.value = payload['value']

            if self.topic == '/ping':
                self.rssi = rssi
                return
            else:
                #print(mac, msg, rssi)
                current = list(self.lights.last_pattern)
                self.lights.all_on(GREEN)
                await self.execute_queue(self.topic, self.value, self.game)
                self.lights.array_on(current)
                #self.lights.all_off()
            
        except Exception as e:
            print('pop error ',e)
                
    async def execute_queue(self, topic, value, game):
        await asyncio.sleep(0)  #yield to WiFi
        #print(topic, value, game)
        try:
            if topic == "/gem": 
                bytes_from_string = value.encode('ascii')
                gem_mac = ubinascii.a2b_base64(bytes_from_string)
                print('hidden gem = ',gem_mac)
                self.hidden_gem = gem_mac
            
            elif topic == '/game':
                if value != game:
                    print('Game ',value)
                    if game >= 0:
                        await self.stop_game(game)
                        await self.lights.animate(RED,timeout = 0, speed = 0.03)
                    #self.game = self.value
                    if value >= 0:
                        print('starting game ',value)
                        await self.lights.animate(COLORS[value],timeout = 0, speed = 0.03)
                        self.start_game(value)
                else:
                    print('notifying')
                    topic = '/notify'
                    
            elif topic == '/color':
                self.color = value
                print(self.color)
                
            elif '/battery' in topic:
                pass
            
            else:
                print('unrecognized topic:', topic)

            self.topic =  topic
            self.value = value
        except Exception as e:
            print(e)
                    
    async def main(self):
        try:
            self.startup()
            time.sleep(5)
            self.start_game(7)
            while self.game >= 0:  # just sit here looking at the queue
                #print(len(self.queue),' ',end='')   # here is your print statement
                while len(self.queue):
                    await self.pop_queue()
                await asyncio.sleep(0.1)
        except Exception as e:
            print('main error: ',e)
        finally:
            print('main shutting down')
            self.close()
    
    
me = Stuffie()
        
asyncio.run(me.main())
