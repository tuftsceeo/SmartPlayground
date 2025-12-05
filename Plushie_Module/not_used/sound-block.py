from machine import Pin, PWM
import time
import random

# Frequencies for all 12 notes (in Hz)
NOTES = {
    'C4': 262, 'C#4': 277, 'D4': 294, 'D#4': 311,
    'E4': 330, 'F4': 349, 'F#4': 370, 'G4': 392,
    'G#4': 415, 'A4': 440, 'A#4': 466, 'B4': 494,
    'C5': 523,
}

def play(button_pin, buzzer_pin):
    """
    Play a random note while button is pressed.
    Note is picked randomly at the start of the function.
    """
    # Pick a random note
    note = random.choice(list(NOTES.keys()))
    frequency = NOTES[note]
    
    button = Pin(button_pin, Pin.IN, Pin.PULL_UP)
    buzzer = PWM(Pin(buzzer_pin))
    
    try:
        while True:
            if button.value() == 0:  # Button pressed
                buzzer.freq(frequency)
                buzzer.duty(512)  # 50% duty cycle
            else:  # Button released
                buzzer.duty(0)  # Silence
            time.sleep(0.01)
    except KeyboardInterrupt:
        buzzer.deinit()

# Usage:
# play(0, 19)