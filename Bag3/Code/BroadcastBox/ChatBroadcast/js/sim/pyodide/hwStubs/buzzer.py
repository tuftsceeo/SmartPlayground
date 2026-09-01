"""Browser stub for buzzer — forwards tones to Web Audio via JS."""

import machine
from js import _js_beep

NOTE_FREQ = {
    "notec": 262,
    "noted": 294,
    "notee": 330,
    "notef": 349,
    "noteg": 392,
    "notea": 440,
    "noteb": 494,
    "notechigh": 523,
}


class Buzzer:
    def __init__(self, pin):
        self.pin = pin

    def beep(self, freq=1000, ms=100):
        _js_beep(int(freq), int(ms))

    def play_note(self, freq, ms=400):
        _js_beep(int(freq), int(ms))

    def melody(self):
        for freq, dur in [(523, 150), (659, 150), (784, 200), (1047, 300)]:
            _js_beep(freq, dur)

    def confirm(self):
        _js_beep(880, 60)
        _js_beep(1200, 80)

    def start(self):
        _js_beep(660, 80)
        _js_beep(880, 80)
        _js_beep(1100, 120)

    def stop(self):
        _js_beep(800, 80)
        _js_beep(400, 200)

    def reject(self):
        _js_beep(200, 150)
        _js_beep(200, 150)

    def warn(self):
        _js_beep(300, 200)
