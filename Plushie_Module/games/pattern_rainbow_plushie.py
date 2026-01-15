import random
import asyncio

from games.game import Game
from utilities.colors import *

# all lights etc declared in Game

# Frequencies for all 12 notes (in Hz)
NOTES = {
    'C4': 262, 'C#4': 277, 'D4': 294, 'D#4': 311,
    'E4': 330, 'F4': 349, 'F#4': 370, 'G4': 392,
    'G#4': 415, 'A4': 440, 'A#4': 466, 'B4': 494,
    'C5': 523,
}

class Notes(Game):
    def __init__(self, main):
        super().__init__(main, 'Notes Game')
        
    def start(self):
        self.note = random.choice(list(NOTES.keys()))
        self.frequency = NOTES[self.note]
        print(f"You were assigned {self.note} at a frequency of {self.frequency}")

    async def loop(self):
        """
        Async task to play a random note while button is pressed.
        Stops when self.running is set to False.
        """
        if self.main.button.pressed:  # Button pressed
            self.main.buzzer.play(self.frequency)
            self.main.lights.all_on(GREEN, 0.1)
        else:  # Button released
            self.main.buzzer.stop()  # Silence
            self.main.lights.all_off()

    def close(self):
        self.main.lights.all_off() 
        self.main.buzzer.stop()


