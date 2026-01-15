import asyncio
import json

from utilities.colors import *

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
            self.start()
            i=0 
            while self.main.running:
                i = i+1 if i < 60/response else 0
                if not i: self.main.espnow.publish(json.dumps({'topic':'/battery', 'value':self.main.battery.read()}))
                await self.loop()
                await asyncio.sleep(response)
        finally:
            self.close()
            print(f"ending game {self.name}")
