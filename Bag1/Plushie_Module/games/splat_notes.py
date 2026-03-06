# random music note and color assignment 

import random
import asyncio

from games.game import Game
from utilities.ble_splat import OpenSplat
from utilities.colors import *

# all lights etc declared in Game

# Frequencies for all 12 notes (in Hz)

INSTRUMENT = 16

OCTAVE = 4
VOLUME = 200

NOTES = {
    'C': 1, 'D': 3,
    'E': 6, 'F': 7, 'G': 10,
    'A': 13, 'B': 15,

}

NOTE_COLORS = {
    'C': RED,
    'D': ORANGE,
    'E': YELLOW,
    'F': GREEN,
    'G': BLUE,
    'A': INDIGO,
    'B': VIOLET,

}

class Splat_Notes(Game):
    def __init__(self, main):
        super().__init__(main, 'Splats Notes Game')
        self.splat = OpenSplat()
        self.pressed = False
        self.released = False

        self.splat.on_splat_pressed = self.handle_splat_pressed
        self.splat.on_splat_released = self.handle_splat_released
    
    def handle_splat_pressed(self):
        self.pressed = True


    def handle_splat_released(self):
        self.released = True

    
    
    def connect_ble(self):
        mac = self.splat.scanSplat()
        print(mac)
        if not mac is None:
            self.splat.connect()
            return True
        else:
            print("No Splat found")
            return False

  
    def start(self):
        self.note = random.choice(list(NOTES.keys()))
        color = NOTE_COLORS[self.note]
        self.frequency = NOTES[self.note]
        if self.connect_ble():
            self.splat.setLEDsON(color)
            self.main.lights.all_on(color, self.main.tool.intensity)
        
        self.main.log_message(f"You were assigned {self.note} at a frequency of {self.frequency}.")

    async def loop(self):
        """
        Async task to play a random note on splat when the splat is pressed
        """

        if self.pressed:  # Button pressed
            print("play music")
            self.splat.noteOn(self.frequency, VOLUME, OCTAVE, INSTRUMENT)
            self.pressed = False
        elif self.released:  # Button released
            print("stop music")
            self.splat.noteOff(self.frequency, VOLUME, OCTAVE, INSTRUMENT)
            self.released = False


    def close(self):
        self.splat.disconnect()
        self.main.lights.all_off() 
        self.main.buzzer.stop()


