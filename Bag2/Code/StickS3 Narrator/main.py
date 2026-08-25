"""
StickS3 Wand Narrator -- main.py

Listens on ESP-NOW for start_game/stop broadcasts and Freeze Dance's raw
Go/Freeze/Dance/Ready calls (see phrases.py), plays the matching WAV clip,
and shows the label on the LCD. Does not handle LED-matrix content or the
Programming Station's scanned-color broadcast -- see README.md.

Read-only on ESP-NOW: never sends.

Hardware: M5Stack StickS3 (ESP32-S3), UIFlow2 MicroPython. Bench tested
against an M5Paper Remote -- see README.md's bench checklist for what's
confirmed vs. still open.
"""

import time

import network
import M5
from M5 import *

from espnow_manager import ESPNowManager
from narrator_ui import NarratorUI
from phrases import phrase_for_tag, tag_for_raw_bytes, validate_phrases

# 0-255. StickS3's own docs warn to stay under ~75% (~191) on battery power
# to avoid a brown-out reboot when USB is unplugged -- see README.md.
SPEAKER_VOLUME = 190

# Senders re-send commands for reliability (e.g. M5Paper Remote sends
# start_game/stop twice, freeze_dance.py sends raw calls 5x) -- collapse
# repeats of the same tag within this window into one announcement.
ANNOUNCE_REPEAT_GUARD_MS = 400

LOOP_SLEEP_MS = 100  # loop() pacing; enow.poll() itself is non-blocking

# Gap between receiving a message and starting playback. ESP-NOW activity
# too close to a playback boundary causes an audible pop; this gap also
# gives the resend (see ANNOUNCE_REPEAT_GUARD_MS) time to arrive so
# enow.drain() can discard it before playback starts.
PRE_PLAY_DELAY_MS = 400

RECONNECT_GRACE_S = 5  # countdown in _reconnect_grace() before WiFi/ESP-NOW init


def _reconnect_grace(ui):
    """Interruptible countdown, run before WiFi/ESP-NOW init on every
    boot/reboot, so a serial IDE has a clean window to interrupt."""
    ui.paint_booting()
    print("Narrator booting -- Ctrl-C within %ds to stay at the REPL" % RECONNECT_GRACE_S)
    for remaining in range(RECONNECT_GRACE_S, 0, -1):
        print("  %d..." % remaining)
        time.sleep_ms(1000)


def _play_phrase(tag):
    path = phrase_for_tag(tag)
    if path is None:
        return
    try:
        M5.Speaker.playWavFile(path)
    except Exception as e:
        print("  speaker err (%s): %s" % (path, str(e)))


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


def setup(ui):
    validate_phrases()
    try:
        M5.Speaker.setVolume(SPEAKER_VOLUME)
    except Exception as e:
        print("  speaker volume err: %s" % str(e))

    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    sta.disconnect()

    enow = ESPNowManager()
    enow.init()

    ui.paint_idle()
    _play_phrase("ready")
    return enow, _AnnounceDebounce()


def loop(enow, ui, debounce):
    msg_type, data, mac = enow.poll()
    if msg_type == "start_game":
        name = data.get("name") if isinstance(data, dict) else None
        if name and debounce.should_announce(name):
            ui.paint_game(name)
            time.sleep_ms(PRE_PLAY_DELAY_MS)
            enow.drain()
            _play_phrase(name)
    elif msg_type == "stop":
        if debounce.should_announce("stop"):
            ui.paint_idle()
            time.sleep_ms(PRE_PLAY_DELAY_MS)
            enow.drain()
            _play_phrase("stop")
    elif msg_type == "raw":
        tag = tag_for_raw_bytes(data)
        if tag and debounce.should_announce(tag):
            ui.paint_game(tag)
            time.sleep_ms(PRE_PLAY_DELAY_MS)
            enow.drain()
            _play_phrase(tag)
    # status_poll / status_report / scan_request / anything else: ignored.
    # This device never replies -- it only listens.
    time.sleep_ms(LOOP_SLEEP_MS)


def main():
    try:
        M5.begin()
        ui = NarratorUI()
        _reconnect_grace(ui)
        enow, debounce = setup(ui)
        while True:
            loop(enow, ui, debounce)
    except (Exception, KeyboardInterrupt) as e:
        try:
            from utility import print_error_msg

            print_error_msg(e)
        except ImportError:
            raise


if __name__ == "__main__":
    main()
