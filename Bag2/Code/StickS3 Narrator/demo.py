"""
demo.py -- standalone bench demo, NO ESP-NOW / hub / wand required.
=====================================================================
Cycles through every phrase the Narrator can say -- using the exact same
narrator_ui.NarratorUI + phrases.py calls main.py makes on a real
start_game/stop packet -- so you can hear and see what the device does with
nothing else nearby. No WiFi, no ESP-NOW init at all.

Run from the REPL without disturbing main.py:
    import demo
    demo.main()

...or temporarily copy this file over main.py to have it run at boot.

Controls (best-effort guess at the API -- see the README's "Demo mode"
section for why; UNVERIFIED on real hardware):
    KEY1 (M5.BtnA) -- advance to the next phrase
    KEY2 (M5.BtnB) -- replay the current phrase

If neither button object exists on this firmware build, falls back to
auto-advancing every AUTO_ADVANCE_MS so the demo still runs untouched --
you'll see which mode it picked printed at startup.
"""

import time

import M5
from M5 import *

from narrator_ui import NarratorUI
from phrases import FREEZE_DANCE_LABELS, GAME_LABELS, label_for_tag, phrase_for_tag

AUTO_ADVANCE_MS = 3500
# See main.py's comment on StickS3's battery-power volume warning.
SPEAKER_VOLUME = 190

# Demo order: a "ready" idle beat, every game, Freeze Dance's own raw
# Go/Freeze/Dance/Ready calls (see phrases.py's FREEZE_DANCE_LABELS), then
# "stop", then repeat.
_SEQUENCE = (
    ["ready"]
    + sorted(GAME_LABELS.keys())
    + list(FREEZE_DANCE_LABELS.keys())
    + ["stop"]
)


def _play_and_show(ui, tag):
    label = label_for_tag(tag)
    print('  [demo] %s -> "%s"' % (tag, label))
    if tag in ("stop", "ready"):
        ui.paint_idle()
    else:
        ui.paint_game(tag)
    path = phrase_for_tag(tag)
    if path is None:
        print("  [demo] no WAV for %s (did you run assets/_generate_phrases.py?)" % tag)
        return
    try:
        M5.Speaker.playWavFile(path)
    except Exception as e:
        print("  [demo] speaker err (%s): %s" % (path, str(e)))


class _Advancer(object):
    """What steps the demo forward -- a button press or a timer -- so
    main() doesn't need to care which."""

    def __init__(self):
        self._idx = 0
        self._use_buttons = False
        try:
            M5.BtnA.isPressed()  # probe -- raises if this object doesn't exist
            M5.BtnB.isPressed()
            self._use_buttons = True
            print("  [demo] KEY1 = next, KEY2 = replay")
        except Exception:
            print(
                "  [demo] buttons unavailable on this firmware -- "
                "auto-advancing every %dms" % AUTO_ADVANCE_MS
            )
        self._last_auto = time.ticks_ms()

    def current_tag(self):
        return _SEQUENCE[self._idx]

    def poll(self):
        """Returns 'next', 'replay', or None."""
        if self._use_buttons:
            try:
                M5.update()
                if M5.BtnA.wasPressed():
                    return "next"
                if M5.BtnB.wasPressed():
                    return "replay"
                return None
            except Exception:
                self._use_buttons = False  # degrade to the timer mid-run
        now = time.ticks_ms()
        if time.ticks_diff(now, self._last_auto) >= AUTO_ADVANCE_MS:
            self._last_auto = now
            return "next"
        return None

    def advance(self):
        self._idx = (self._idx + 1) % len(_SEQUENCE)


def main():
    M5.begin()
    try:
        M5.Speaker.setVolume(SPEAKER_VOLUME)
    except Exception as e:
        print("  [demo] speaker volume err: %s" % str(e))

    ui = NarratorUI()
    adv = _Advancer()
    _play_and_show(ui, adv.current_tag())

    while True:
        action = adv.poll()
        if action == "next":
            adv.advance()
            _play_and_show(ui, adv.current_tag())
        elif action == "replay":
            _play_and_show(ui, adv.current_tag())
        time.sleep_ms(30)


if __name__ == "__main__":
    main()
