"""
StickS3 Wand Narrator -- Tier 0 accessibility companion
========================================================
Passively listens on ESP-NOW for the "start_game"/"stop" broadcasts already
sent by the hub, the M5Paper Remote, or any other wand-triggering device,
and narrates them out loud (speaker) plus in large text (color LCD) for a
low-vision or blind student wearing it.

This device sends nothing -- it is read-only on the wire. That means it is
compatible with any Bag2 or Bag3 wand/hub as-is, with no firmware change on
their side and no exposure to the Bag2 verification gate (../../../AGENTS.md).

Tier 0 scope: game name + stop announcements, PLUS Freeze Dance's own
Go/Freeze/Dance calls (raw, non-JSON ESP-NOW broadcasts -- see
phrases.py's FREEZE_DANCE_CALLS). It does NOT narrate what the wand's 5x5
LED matrix is showing (colors, shapes, correct/wrong), and it does NOT
narrate the Programming Station's scanned-color broadcast -- see
phrases.py's docstring and README.md's "Broadcast coverage" section.

Hardware: M5Stack StickS3 (ESP32-S3), UIFlow2 MicroPython.
NOT YET BENCH-VERIFIED -- no StickS3 hardware in hand at time of writing.
See README.md's bench checklist before trusting this on a real device.
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

# freeze_dance.py sends each raw Go/Freeze/Dance call 5x, ~1ms apart, as a
# reliability measure (not a repeated command) -- without this guard the
# Narrator would announce the same word 5 times in a row.
RAW_REPEAT_GUARD_MS = 400


def _play_phrase(tag):
    path = phrase_for_tag(tag)
    if path is None:
        return
    try:
        M5.Speaker.playWavFile(path)
    except Exception as e:
        print("  speaker err (%s): %s" % (path, str(e)))


class _RawDebounce(object):
    """Collapses freeze_dance.py's 5x-repeated raw broadcast into one
    announcement -- same spirit as the NFC repeat-scan guards used
    elsewhere in this repo (e.g. freeze_dance.py's own REPEAT_SCAN_GUARD_MS)."""

    def __init__(self):
        self._last_tag = None
        self._last_ms = 0

    def should_announce(self, tag):
        now = time.ticks_ms()
        if tag == self._last_tag and time.ticks_diff(now, self._last_ms) < RAW_REPEAT_GUARD_MS:
            return False
        self._last_tag = tag
        self._last_ms = now
        return True


def setup():
    M5.begin()
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

    ui = NarratorUI()
    ui.paint_idle()
    _play_phrase("ready")
    return enow, ui, _RawDebounce()


def loop(enow, ui, raw_debounce):
    # Blocking-ish poll (see espnow_manager.poll): waits up to 100ms for a
    # packet, so this loop needs no separate sleep_ms.
    msg_type, data, mac = enow.poll(timeout_ms=100)
    if msg_type == "start_game":
        name = data.get("name") if isinstance(data, dict) else None
        if name:
            ui.paint_game(name)
            _play_phrase(name)
    elif msg_type == "stop":
        ui.paint_idle()
        _play_phrase("stop")
    elif msg_type == "raw":
        tag = tag_for_raw_bytes(data)
        if tag and raw_debounce.should_announce(tag):
            ui.paint_game(tag)
            _play_phrase(tag)
    # status_poll / status_report / scan_request / anything else: ignored.
    # This device never replies -- it only listens.


def main():
    try:
        enow, ui, raw_debounce = setup()
        while True:
            loop(enow, ui, raw_debounce)
    except (Exception, KeyboardInterrupt) as e:
        try:
            from utility import print_error_msg

            print_error_msg(e)
        except ImportError:
            raise


if __name__ == "__main__":
    main()
