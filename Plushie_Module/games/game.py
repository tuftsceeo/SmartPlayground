import asyncio
import json

from utilities.colors import *
from config import config

class Game:
    def __init__(self, main, name = 'test'):
        self.name = name
        self.main = main
    
    async def loop(self):
        if self.main.button.pressed:  # Button pressed
            self.main.lights.all_on(GREEN, 0.1)
        else:  # Button released
            self.main.lights.all_off()

    def close(self):
        self.main.lights.all_off()
        self.main.buzzer.stop()
            
    async def run(self, response = 0.1):
        """
        Async task that continually runs
        """
        try:
            print(f'starting game {self.name}')
            hub_name = config['name']
            self.start()
            i=0 
            while self.main.running:
                if not i:
                    msg = {'topic':f'/battery/{hub_name}', 'value':self.main.battery.read()}
                    self.main.publish(msg)
                    print(f'sent battery level {msg}')
                i = i+1 if i < 60/response else 0
                await self.loop()
                await asyncio.sleep(response)
        finally:
            self.close()
            print(f"ending game {self.name}")

