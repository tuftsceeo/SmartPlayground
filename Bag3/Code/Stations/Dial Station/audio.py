"""
audio.py -- this station's hardware: track playback on the M5Dial's
AudioPlayer unit.

Verbs, over ESP-NOW "cap" messages addressed to hubtype dial_station:

    play           resume
    pause          pause
    stop           stop and release the player
    track {i}      play track i (1-based, as the unit numbers them)
    vol   {v}      set volume

The unit debounces commands 400 ms apart, so a burst of repeats from a wand
collapses into one action -- which is what makes the repeat-and-guard idiom on
the sending side safe here.

Runs under UIFlow2 on the M5Dial, so `unit` only imports on that board. Nothing
but the dial_station branch of devices.build() reaches this module. The LVGL
screen and the encoder stay in the dial's own tree: they are the teacher's
local control, not a capability.
"""

import time

from unit import AudioPlayerUnit

from hubtype import HUB_CONFIG

DEBOUNCE_MS = 400


class DialAudio:

    def __init__(self):
        self.player = AudioPlayerUnit(HUB_CONFIG["audio_uart"],
                                      port=HUB_CONFIG["audio_port"])
        self.max_volume = HUB_CONFIG["max_volume"]
        self.track = 1
        self._last_ms = 0

    # -- capability interface ----------------------------------------

    def handle(self, op, args):
        if op == "play":
            self._debounced(self.player.play_audio)
        elif op == "pause":
            self._debounced(self.player.pause_audio)
        elif op == "stop":
            self._debounced(self.player.stop_audio)
        elif op == "track":
            self.play_track(args["i"])
        elif op == "vol":
            self.set_volume(args["v"])
        else:
            raise ValueError("dial_station: unknown op %r" % op)

    def step(self):
        """Nothing here runs over time; the unit plays on its own."""

    def off(self):
        self.player.stop_audio()

    # -- verbs -------------------------------------------------------

    def play_track(self, index):
        total = self.player.get_total_audio_number()
        if not 1 <= index <= (total or 0):
            raise ValueError("dial_station: track %r of %r" % (index, total))
        self.track = index
        self._debounced(lambda: self.player.play_audio_by_index(index))

    def set_volume(self, level):
        if not 0 <= level <= self.max_volume:
            raise ValueError("dial_station: volume %r out of 0..%d"
                             % (level, self.max_volume))
        self.player.set_volume(level)

    def track_name(self, index):
        """Name of a track, for the evt a local encoder change broadcasts."""
        self.player.select_audio_num(index)
        raw = self.player.get_file_name()
        if isinstance(raw, (list, bytes, bytearray)):
            return bytes(raw).decode("utf-8").rstrip("\x00")
        return str(raw)

    # -- internals ---------------------------------------------------

    def _debounced(self, fn):
        """Drop a transport command inside the unit's debounce window.

        A wand repeats each event several times because nothing is acked; the
        unit would otherwise stutter on the repeats.
        """
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last_ms) < DEBOUNCE_MS:
            return
        self._last_ms = now
        fn()
