# random music note and color assignment 

import random
import asyncio

from games.game import Game
from utilities.colors import *

# all lights etc declared in Game

# Frequencies for all 12 notes (in Hz)
NOTES = {
    'C4': 262, 'D4': 294,
    'E4': 330, 'F4': 349, 'G4': 392,
    'A4': 440, 'B4': 494,
    'C5': 523,
}

NOTE_COLORS = {
    'C4': RED,
    'D4': ORANGE,
    'E4': YELLOW,
    'F4': GREEN,
    'G4': BLUE,
    'A4': INDIGO,
    'B4': VIOLET,
    'C5': WHITE,
}

class Notes(Game):
    def __init__(self, main):
        super().__init__(main, 'Notes Game')
        
    def start(self):
        self.note = random.choice(list(NOTES.keys()))
        self.frequency = NOTES[self.note]
        self.main.log_message(f"You were assigned {self.note} at a frequency of {self.frequency}.")

    async def loop(self):
        """
        Async task to play a random note while button is pressed.
        Stops when self.running is set to False.
        """
        if self.main.topic == '/reset':
            self.start()
            self.main.topic = '/notify'
        if self.main.button.pressed:  # Button pressed
            self.main.buzzer.play(self.frequency)
            color = NOTE_COLORS[self.note]
            self.main.lights.all_on(color, self.main.tool.intensity)
        else:  # Button released
            self.main.buzzer.stop()  # Silence
            self.main.lights.all_off()

    def close(self):
        self.main.lights.all_off() 
        self.main.buzzer.stop()

