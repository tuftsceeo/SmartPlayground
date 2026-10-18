"""
Music Board Station: receives melodies from MockWands and plays them.

A wand in the melody game taps the "musicbox@<HOST_ID>" sticker on the
board and broadcasts
    {"type": "song", "to": "<HOST_ID>", "n": "<notes>", "seq": <int>}
The board acks by unicast with {"type": "song_ack", "seq": seq, "len": n},
stores the song (or appends it after a person+ press) and plays it once.

Song string: one token per note. Note char c d e f g a b C, or r for a
rest, optionally followed by "+" (half note) or "-" (eighth note); no
mark = quarter. MockWand currently sends bare note chars only.

Buttons: play (play / stop), voice (piano / guitar / violin), person+
(append the next song received instead of replacing).
"""

import time
import machine
from binascii import hexlify
from machine import Pin

from audio import Audio
from staff import Staff, timeline

HOST_ID = hexlify(machine.unique_id()[-2:]).decode()

NOTE_DIR = "notes"
NOTE_CHARS = "cdefgabC"           # index + 1 = note number; must match melody.py NOTE_CHAR
LENGTH_MARKS = {"+": 4, "-": 1}   # eighth-beats; quarter (no mark) = 2
QUARTER = 2
MAX_TOKENS = 64

PLAY_PIN = 2
VOICE_PIN = 0
ADD_PIN = 1
DEBOUNCE_MS = 200
ADD_TIMEOUT_MS = 30000
SEQ_TABLE_MAX = 20

# (name, WAV suffix, quarter-note ms, button LED colour)
VOICES = (
    ("piano", "", 600, (0, 255, 0)),
    ("guitar", "_fast", 320, (255, 0, 0)),
    ("violin", "_slow", 1000, (0, 0, 255)),
)

LED_OFF = (0, 0, 0)
LED_READY = (0, 255, 0)
LED_PLAYING = (255, 255, 0)
LED_ADDING = (0, 0, 255)


def parse_song(text):
    """'ce-g+r' -> [(1, 2), (3, 1), (5, 4), (0, 2)]. Raises ValueError on bad input."""
    if not isinstance(text, str) or not text:
        raise ValueError(f"song must be a non-empty string, got {text!r}")
    tokens = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "r":
            note = 0
        else:
            k = NOTE_CHARS.find(ch)
            if k < 0:
                raise ValueError(f"bad note {ch!r} at {i} in {text!r}")
            note = k + 1
        length = QUARTER
        if i + 1 < len(text) and text[i + 1] in LENGTH_MARKS:
            length = LENGTH_MARKS[text[i + 1]]
            i += 1
        tokens.append((note, length))
        i += 1
    return tokens


class Button:
    """Falling-edge IRQ sets a flag; the main loop consumes it."""

    def __init__(self, pin):
        self.pin = Pin(pin, Pin.IN, Pin.PULL_UP)
        self.pressed = False
        self._last = 0
        self.pin.irq(trigger=Pin.IRQ_FALLING, handler=self._irq)

    def _irq(self, p):
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last) > DEBOUNCE_MS:
            self._last = now
            self.pressed = True

    def take(self):
        if self.pressed:
            self.pressed = False
            return True
        return False


class MusicBoard:
    def __init__(self, enow):
        self.enow = enow
        self.audio = Audio()
        self.staff = Staff()
        self.btn_play = Button(PLAY_PIN)
        self.btn_voice = Button(VOICE_PIN)
        self.btn_add = Button(ADD_PIN)

        self.song = []          # [(note, eighths), ...]
        self.cols = []          # timeline(self.song)
        self.voice = 0
        self.adding_since = None
        self._seen = {}         # sender mac_str -> (last seq, notes taken)

        self.playing = False
        self._tok = 0           # token index being played
        self._col = 0           # timeline column of that token's head
        self._tok_start = 0
        self._eighth = 0        # column within the token currently drawn
        print(f"  Music Board ready: sticker text musicbox@{HOST_ID}")
        self._refresh()

    # ── display ───────────────────────────────

    def _refresh(self):
        self.staff.draw(self.cols)
        self._leds()

    def _leds(self):
        if self.adding_since is not None:
            add = LED_ADDING
        elif self.song:
            add = LED_READY
        else:
            add = LED_OFF
        if self.playing:
            play = LED_PLAYING
        elif self.song:
            play = LED_READY
        else:
            play = LED_OFF
        self.staff.buttons(VOICES[self.voice][3], play, add)

    # ── playback ──────────────────────────────

    def _eighth_ms(self):
        return VOICES[self.voice][2] // QUARTER

    def _start_token(self):
        note, _ = self.song[self._tok]
        self._tok_start = time.ticks_ms()
        self._eighth = 0
        if note:
            self.audio.start(f"{NOTE_DIR}/notet{note}{VOICES[self.voice][1]}.wav")
        else:
            self.audio.stop()
        self._draw_playing()

    def _draw_playing(self):
        t = self._col + self._eighth
        self.staff.draw(self.cols, self.staff.window_start(len(self.cols), t), playing=t)

    def play(self):
        if not self.song:
            return
        self.playing = True
        self._tok = 0
        self._col = 0
        self._leds()
        self._start_token()

    def stop(self):
        self.audio.stop()
        self.playing = False
        self._refresh()

    def _step_playback(self):
        note, length = self.song[self._tok]
        elapsed = time.ticks_diff(time.ticks_ms(), self._tok_start)
        eighth = self._eighth_ms()
        if elapsed >= length * eighth:
            self._col += length
            self._tok += 1
            if self._tok >= len(self.song):
                self.stop()
                return
            self._start_token()
            return
        e = elapsed // eighth
        if e != self._eighth:
            self._eighth = e
            self._draw_playing()
        self.audio.step()

    # ── radio ─────────────────────────────────

    def _ack(self, mac_str, seq, n):
        self.enow.add_peer(mac_str)
        self.enow.send_to(mac_str, {"type": "song_ack", "seq": seq, "len": n})
        self.enow.remove_peer(mac_str)

    def _on_song(self, data, mac_str):
        if data.get("to") != HOST_ID:
            return
        seq = data.get("seq")
        seen = self._seen.get(mac_str)
        if seen is not None and seen[0] == seq:
            self._ack(mac_str, seq, seen[1])   # wand retry: re-ack, do not replay
            return
        if len(self._seen) >= SEQ_TABLE_MAX:
            self._seen.clear()
        try:
            tokens = parse_song(data.get("n"))
        except ValueError as e:
            print(f"  Song rejected from {mac_str}: {e}")
            self._seen[mac_str] = (seq, 0)
            self._ack(mac_str, seq, 0)
            return
        if self.adding_since is not None:
            base = self.song
            self.adding_since = None
        else:
            base = []
        room = MAX_TOKENS - len(base)
        taken = tokens[:room]
        self._seen[mac_str] = (seq, len(taken))
        self._ack(mac_str, seq, len(taken))
        print(f"  Song from {mac_str}: {len(tokens)} notes, {len(taken)} taken, {len(base)} already on board")
        self.stop()
        self.song = base + taken
        self.cols = timeline(self.song)
        self.play()

    def _poll_radio(self):
        msg_type, data, mac_str = self.enow.poll(0)
        if msg_type == "song":
            self._on_song(data, mac_str)
        elif msg_type == "stop":
            self.song = []
            self.cols = []
            self.adding_since = None
            self.stop()

    # ── main loop ─────────────────────────────

    def _poll_buttons(self):
        if self.btn_play.take():
            if self.playing:
                self.stop()
            else:
                self.play()
        if self.btn_voice.take():
            self.voice = (self.voice + 1) % len(VOICES)
            print(f"  Voice: {VOICES[self.voice][0]}")
            self._leds()
        if self.btn_add.take():
            if self.adding_since is None:
                self.adding_since = time.ticks_ms()
                print("  Waiting to add the next song")
            else:
                self.adding_since = None
            self._leds()
        if self.adding_since is not None and \
                time.ticks_diff(time.ticks_ms(), self.adding_since) > ADD_TIMEOUT_MS:
            self.adding_since = None
            self._leds()

    def run(self):
        while True:
            self._poll_radio()
            self._poll_buttons()
            if self.playing:
                self._step_playback()
            time.sleep_ms(1)
