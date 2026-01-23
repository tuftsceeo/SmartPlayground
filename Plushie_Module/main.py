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
import config 

class Tool:
    def __init__(self):
        self.tool = config.Plushie_settings
        self.mac = None
        self.espnow = None
        self.start_time = time.ticks_ms()

        self.game = -1
        self.running = False
        self.topic = ''
        self.value = -1
        self.task = None
        self.hidden_gem = None
        self.queue = deque([], 20)
        self.log_message('Plushie', False) 

        self.lights = lights.Lights(self.tool.num_of_leds)
        self.lights.color = self.tool.color
        self.lights.intensity = self.tool.intensity
        self.lights.all_off()
        
        self.accel = i2c_bus.LIS2DW12()
        self.battery = i2c_bus.Battery()
        self.button = utilities.Button(self.tool.module_type)
        self.buzzer = utilities.Buzzer(self.tool.volume)
        self.buzzer.stop()
        self.hibernate = utilities.Hibernate()
        
        # this will initialize each game and pass in attributes of this class - (self) - 
        self.game_names = [g[0](self) for g in self.tool.games]
        self.response_times = [g[1] for g in self.tool.games]
        self.log_message('Initialized') 
        
    def log_message(self, message, append = True):
        try:
            method = "a" if append else "w"
            with open('log.txt', method) as file:
                timestamp = time.ticks_diff(time.ticks_ms(), self.start_time) / 1000
                log_entry = "{:.2f}: {}\n".format(timestamp, message)
                file.write(log_entry)
                print(log_entry[:-1])
        except OSError as e:
            print("Error writing to log file:", e)

    def startup(self):
        self.log_message('Starting up...')
        self.lights.on(0)
        self.espnow = now.Now(self.tool.antenna, self.now_callback)
        self.espnow.connect()
        self.lights.on(1)
        self.mac = self.espnow.wifi.config('mac')
        self.log_message(f'my mac address is {[hex(b) for b in self.mac]}')
        self.lights.on(2)
        self.topic = ''
        self.msg = ''
        self.log_message('Started up') 
        
    def publish(self, msg):
        self.espnow.publish(json.dumps(msg))
        
    def start_game(self, number):
        if number < 0 or number >= len(self.game_names):
            self.log_message('illegal game number')
            return
        if self.game == number:
            self.log_message(f'notify {number}')
            self.topic = '/notify'
            return
        self.log_message('starting game ', number)
        self.running = True
        self.game = number
        
        # now run the game -each game class should have a def run(response time) in it
        self.task = asyncio.create_task(self.game_names[number].run(self.response_times[number]))
        self.log_message(f'started {number}')
        
    async def stop_game(self, number):
        self.log_message(f'trying to stop {number}')
        self.running = False
        await self.task

    def close(self):
        if self.game >= 0:
            self.stop_game(self.game)
        if self.espnow: self.espnow.close()
        self.lights.all_off()
        self.buzzer.stop()
        self.log_message('Closed') 

    def now_callback(self, msg, mac, rssi):
        try:
            self.queue.append((msg, mac, rssi))
        except Exception as e:
            self.log_message(f"Callback error: {e}")
    
            
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
                self.lights.all_on(self.tool.color)
                await self.execute_queue(self.topic, self.value, self.game)
                self.lights.array_on(current)
                #self.lights.all_off()
            
        except Exception as e:
            self.log_message(f'pop error {e}')
                
    async def execute_queue(self, topic, reply, game):
        await asyncio.sleep(0)  #yield to WiFi
        #print(topic, value, game)
        try:
            self.log_message(f'received {topic} {reply}')
            if topic == '/game':
                try:
                    value, gem_mac = reply
                except:
                    self.log_message('received /game request for old firmware')
                    return
                gem_mac = ubinascii.a2b_base64(gem_mac.encode('ascii'))
                self.log_message(f'controller mac address = {gem_mac}')
                self.hidden_gem = gem_mac
                
                if value != game:
                    self.log_message(f'Game {value}')
                    if game >= 0:
                        await self.stop_game(game)
                        await self.lights.animate(RED,timeout = 0, speed = 0.03)
                    #self.game = self.value
                    if value >= 0:
                        self.log_message('starting game ',value)
                        await self.lights.animate(COLORS[value],timeout = 0, speed = 0.03)
                        self.start_time = time.ticks_ms()
                        self.start_game(value)
                else:
                    self.log_message('notifying')
                    topic = '/notify'
                    
            elif topic == '/color':
                self.color = value
                self.log_message(f"color  {self.color}")
                
            elif '/battery' in topic:
                self.log_message(f"{topic}  {value}")
            
            else:
                self.log_message(f'unrecognized topic:{topic}')

            self.topic =  topic
            self.value = value
        except Exception as e:
            self.log_message(f'execute queue {e}')
                    
    async def main(self):
        try:
            self.startup()
            time.sleep(1)
            first_game = self.tool.first_game
            self.start_game(first_game)
            while self.game >= 0:  # just sit here looking at the queue
                #print(len(self.queue),' ',end='')   
                while len(self.queue):
                    await self.pop_queue()
                await asyncio.sleep(0.1)
        except Exception as e:
            self.log_message(f'main error: {e}')
        finally:
            self.log_message('main shutting down')
            self.close()
    
    
me = Tool()
        
asyncio.run(me.main())

