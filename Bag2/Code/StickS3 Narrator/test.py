"""
test.py -- delay-before-playback diagnostic. Does not touch main.py.

Same auto-play-on-receipt flow as main.py, except playback is delayed
DELAY_MS after the message is received instead of starting immediately.
Tests whether that alone (no radio state change) fixes the pop.

Includes the same debounce + drain() as main.py, since the delay alone
reintroduces the double-playback bug (the resend arrives during the delay
sleep instead of during playback, but is otherwise the same problem).

KEY1 (M5.BtnA) replays the current tag immediately, no delay -- a manual
no-delay comparison point. No KEY2 (unsafe reset combo on this board).

Run from the REPL without disturbing main.py:
    import test
    test.main()
"""

import time

import network
import M5
from M5 import *

from espnow_manager import ESPNowManager
from narrator_ui import NarratorUI
from phrases import phrase_for_tag, tag_for_raw_bytes, label_for_tag

DELAY_MS = 400
ANNOUNCE_REPEAT_GUARD_MS = 400
SPEAKER_VOLUME = 190


class _AnnounceDebounce(object):
    """Suppresses re-announcing the same tag within ANNOUNCE_REPEAT_GUARD_MS."""

    def __init__(self):
        self._last_tag = None
        self._last_ms = 0

    def should_announce(self, tag):
        now = time.ticks_ms()
        if tag == self._last_tag and time.ticks_diff(now, self._last_ms) < ANNOUNCE_REPEAT_GUARD_MS:
            return False
        self._last_tag = tag
        self._last_ms = now
        return True


def _play(tag):
    path = phrase_for_tag(tag)
    if path is None:
        print("  no WAV for %s" % tag)
        return
    try:
        M5.Speaker.playWavFile(path)
    except Exception as e:
        print("  speaker err (%s): %s" % (path, str(e)))


def main():
    M5.begin()
    try:
        M5.Speaker.setVolume(SPEAKER_VOLUME)
    except Exception as e:
        print("  speaker volume err: %s" % str(e))

    ui = NarratorUI()
    ui.paint_idle()

    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    sta.disconnect()
    enow = ESPNowManager()
    enow.init()

    use_buttons = False
    try:
        M5.BtnA.isPressed()
        use_buttons = True
        print("  KEY1 = replay current tag immediately (no delay)")
    except Exception:
        print("  KEY1 unavailable on this firmware")

    current_tag = None
    debounce = _AnnounceDebounce()
    print("test.py running -- delaying %dms before auto-play on receipt" % DELAY_MS)

    while True:
        msg_type, data, mac = enow.poll()
        tag = None
        if msg_type == "start_game":
            name = data.get("name") if isinstance(data, dict) else None
            if name:
                tag = name
        elif msg_type == "stop":
            tag = "stop"
        elif msg_type == "raw":
            tag = tag_for_raw_bytes(data)

        if tag and debounce.should_announce(tag):
            current_tag = tag
            if tag == "stop":
                ui.paint_idle()
            else:
                ui.paint_game(tag)
            print('  received: "%s" -- waiting %dms' % (label_for_tag(tag), DELAY_MS))
            time.sleep_ms(DELAY_MS)
            enow.drain()  # discard the resend that arrived during the delay
            print("  playing now")
            _play(tag)

        if use_buttons:
            try:
                M5.update()
                if M5.BtnA.wasPressed() and current_tag:
                    print('  [KEY1: no delay] "%s"' % label_for_tag(current_tag))
                    _play(current_tag)
            except Exception:
                use_buttons = False

        time.sleep_ms(30)


if __name__ == "__main__":
    main()
