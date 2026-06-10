"""
M5Paper Standalone Wand Remote

Self-contained teacher remote: e-ink touch UI + ESP-NOW broadcast to Bag2 wands.
Hardware: M5Paper (ESP32-D0WDQ6), UIFlow2 MicroPython.
"""

import time

import M5
from M5 import *
import network

from config import (
    ESPNOW_CHANNEL,
    build_commands,
    load_enabled_ids,
    validate_config,
)
from espnow_manager import ESPNowManager, get_own_mac
from ui import RemoteUI


def _broadcast_twice(send_fn):
    send_fn()
    time.sleep_ms(100)
    send_fn()


def _maybe_set_channel():
    if ESPNOW_CHANNEL is None:
        return
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    try:
        sta.config(channel=ESPNOW_CHANNEL)
        print("  WiFi channel set to %s" % ESPNOW_CHANNEL)
    except Exception as e:
        print("  WiFi channel config err: %s" % str(e))


def _dispatch(enow, btn):
    if btn.kind == "game":
        _broadcast_twice(lambda: enow.broadcast_start_game(btn.button_id))
    elif btn.button_id == "stop":
        _broadcast_twice(enow.broadcast_stop)
    elif btn.button_id == "battery":
        _broadcast_twice(lambda: enow.broadcast(["battery"]))


def setup():
    M5.begin()
    validate_config()

    _maybe_set_channel()
    enow = ESPNowManager()
    enow.init()

    mac_str = get_own_mac()
    enabled = load_enabled_ids()
    commands = build_commands(enabled)
    ui = RemoteUI(mac_str, commands, espnow_ready=enow.is_active)
    ui.paint_full()
    return enow, ui


def loop(enow, ui):
    ui.update_battery()
    touch = ui.poll_touch()
    if touch is None:
        time.sleep_ms(50)
        return

    x, y = touch
    result = ui.on_touch(x, y)
    if result == "open_settings":
        if not ui.try_debounce():
            return
        ui.open_settings()
        return
    if result is None:
        return
    if not ui.try_debounce():
        return

    print("  Tap: %s (%s,%s)" % (result.label, x, y))
    _dispatch(enow, result)
    ui.show_feedback(result, result.label)


def main():
    try:
        enow, ui = setup()
        while True:
            loop(enow, ui)
    except (Exception, KeyboardInterrupt) as e:
        try:
            from utility import print_error_msg

            print_error_msg(e)
        except ImportError:
            raise


if __name__ == "__main__":
    main()
