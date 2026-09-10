/* Content lifted from ChatBroadcast/js/examples.js — real names, descriptions and tag notes. */
window.WSC_EXAMPLES = [
  { id:'melody', name:'Melody', icon:'music', category:'sound', description:'Tap each note-tag to play a tune.', tagNote:'8 NFC tags',
    hint:'Tap the note tags to build a tune, then press the button to play it back.',
    tags:['note_c','note_d','note_e','note_f','note_g','note_a','note_b','note_c_high'] },
  { id:'freezedance', name:'Freeze Dance', icon:'snowflake', category:'color', description:'Move, then freeze when the music stops.', tagNote:null,
    hint:'Shake while the lights dance — freeze when they turn white!', tags:['freezedance'] },
  { id:'rainbow', name:'Rainbow', icon:'rainbow', category:'color', description:'Shake for color.', tagNote:null,
    hint:'Shake for a new color. Press the button to reset to white.', tags:['rainbow'] },
  { id:'shakerainbow', name:'Shake Rainbow', icon:'rainbow', category:'color', description:'Shake harder to climb through rainbow colors.', tagNote:null,
    hint:'Shake harder to climb to the next color — your best shake sticks. Press the button to reset.', tags:['shakerainbow'] },
  { id:'jump', name:'Jump', icon:'arrow-up', category:'color', description:'Jump (freefall) to light more LEDs on the matrix.', tagNote:null,
    hint:'Jump to light one more LED. Press the button to reset.', tags:['jump'] },
  { id:'cooking', name:'Cooking', icon:'chef-hat', category:'multi', description:'Recipe steps with ingredient tags.', tagNote:'Multi-tag',
    hint:'Tap the ingredient tags in recipe order. Press the button to start over.', tags:['flour','egg','milk','butter','sugar'] },
  { id:'jumpin', name:'Jump In', icon:'brain-circuit', category:'color', description:'Simple jump game — great first project.', tagNote:null,
    hint:'Shake to fill the lights. Press the button to reset.', tags:['jumpin'] },
];
window.WSC_CATEGORIES = [
  { id:'all', label:'All', icon:null },
  { id:'sound', label:'Sound', icon:'music' },
  { id:'color', label:'Color', icon:'palette' },
  { id:'multi', label:'Multi-tag', icon:'tag' },
];
window.WSC_SAMPLE_CODE = `"""
Jump In — shake to light the wand
=================================
Shake the wand to fill the LED matrix with color. Press the button to reset.
"""

import time, math
from machine import Pin
from leds import RED, GREEN, BLUE, YELLOW, PURPLE, PINK

SHAKE_THRESHOLD = 1.4
PICK = [RED, GREEN, BLUE, YELLOW, PURPLE, PINK]


def play(nfc, leds, buz, accel, i2c, enow):
    buz.beep(523, 80)
    level = 0
    while True:
        x, y, z = accel.read()
        if math.sqrt(x*x + y*y + z*z) > SHAKE_THRESHOLD:
            level = min(25, level + 1)
            leds.fill(PICK[level % len(PICK)])
            buz.beep(600, 40)
        time.sleep_ms(50)`;
