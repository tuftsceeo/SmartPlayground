import asyncio

import utilities.utilities as utilities
import utilities.lights as lights
import utilities.now as now
import utilities.i2c_bus as i2c_bus
from utilities.colors import *

from games.sound import Notes
from games.color_press import Color_Press
from games.shake import Shake
from games.jump import Jump
from games.hotcold import Hot_cold
from games.rainbow import Rainbow
from games.hibernate import Hibernate
from games.pattern_rainbow_btn import Pattern_btn
from games.pattern_rainbow_plushie import Pattern_plush

class SimplePlushie:
    def __init__(self):
        self.running = True
        self.lights = lights.Lights()
        self.lights.default_color = GREEN
        self.lights.default_intensity = 0.1
        self.lights.all_off()
        
        self.accel = i2c_bus.LIS2DW12()
        self.button = utilities.Button()
        self.buzzer = utilities.Buzzer()
        self.battery = i2c_bus.Battery()
        self.buzzer.stop()
        
        self.hibernate = utilities.Hibernate()
        
        self.hidden_gem = None
        self.rssi = None
        self.topic = None
        self.msg = None
        
plush = SimplePlushie()

async def main(code):
    plush.running = True
    task = asyncio.create_task(code.run())
    for i in range(400):
        print('@',end='')
        await asyncio.sleep(0.1)
    plush.running = False
    await task
    code.close()


milan = Color_Press(plush)
asyncio.run(main(milan))

fred = Notes(plush)
#asyncio.run(main(fred))

bill = Shake(plush)   
#asyncio.run(main(bill))

sally = Jump(plush)   
#asyncio.run(main(sally))

sam = Rainbow(plush)
#asyncio.run(main(sam))

cath = Hot_cold(plush)
#asyncio.run(main(cath))

quinn = Hibernate(plush)
#asyncio.run(main(quinn))


suzie = Pattern_plush(plush)
#asyncio.run(main(suzie))

