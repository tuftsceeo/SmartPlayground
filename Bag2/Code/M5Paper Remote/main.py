"""
M5Paper Standalone Wand Remote

Self-contained teacher remote: e-ink touch UI + ESP-NOW broadcast to Bag2 wands.
Hardware: M5Paper (ESP32-D0WDQ6), UIFlow2 MicroPython.
"""

import time

import machine
import M5
from M5 import *
import network

from config import (
    BATT_CRIT_SOC,
    BATT_POLL_MS,
    ESPNOW_CHANNEL,
    INACTIVITY_SLEEP_MS,
    SIDE_BTN_DOWN,
    SIDE_BTN_PRESS,
    SIDE_BTN_UP,
    SLEEP_TICK_MS,
    USE_LIGHTSLEEP,
    build_commands,
    load_enabled_ids,
    validate_config,
)
from espnow_manager import ESPNowManager, get_own_mac
from ui import RemoteUI


class SideButtons:
    """M5Paper 3-way side rocker on G37/G38/G39. Edge-detects presses.

    GPIO 37-39 are input-only (no internal pulls); the board's external
    pull-ups make value() == 0 mean pressed. poll() returns 'up'/'press'/
    'down' once on the press edge, else None.
    """

    def __init__(self):
        self.pins = {}
        for name, gpio in (
            ("up", SIDE_BTN_UP),
            ("press", SIDE_BTN_PRESS),
            ("down", SIDE_BTN_DOWN),
        ):
            try:
                self.pins[name] = machine.Pin(gpio, machine.Pin.IN)
            except Exception as e:
                print("  side btn %s (G%s) init err: %s" % (name, gpio, str(e)))
        self._last = dict((k, 1) for k in self.pins)

    def poll(self):
        event = None
        for name, pin in self.pins.items():
            try:
                v = pin.value()
            except Exception:
                continue
            if v == 0 and self._last.get(name, 1) == 1:
                event = name
            self._last[name] = v
        return event

    def any_pressed(self):
        for pin in self.pins.values():
            try:
                if pin.value() == 0:
                    return True
            except Exception:
                pass
        return False


class Ctx(object):
    """Mutable runtime context shared across the loop."""

    def __init__(self, enow, ui, sidebtn):
        self.enow = enow
        self.ui = ui
        self.sidebtn = sidebtn
        self.last_activity = time.ticks_ms()
        self.sleeping = False
        self.sleep_batt_ms = 0
        self.batt_crit_shown = False


def _broadcast_twice(send_fn):
    send_fn()
    time.sleep_ms(100)
    send_fn()


def _broadcast_thrice(send_fn):
    send_fn()
    time.sleep_ms(60)
    send_fn()
    time.sleep_ms(60)
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


def _drain_status_reports(enow, ui):
    if ui.mode != "status":
        return
    for _ in range(12):
        msg_type, data, mac = enow.poll()
        if msg_type is None:
            break
        if msg_type != "status_report" or not mac:
            continue
        battery = None
        rssi = None
        if isinstance(data, dict):
            battery = data.get("battery")
            rssi = data.get("rssi")
        ui.upsert_status_report(mac, battery, rssi)


def _dispatch(enow, btn):
    if btn.kind == "game":
        _broadcast_twice(lambda: enow.broadcast_start_game(btn.button_id))
    elif btn.button_id == "stop":
        _broadcast_twice(enow.broadcast_stop)


def _enter_sleep(ctx):
    """Show the sleep screen and power down the radio (the big battery draw)."""
    print("  Sleeping (no activity for %ds)" % (INACTIVITY_SLEEP_MS // 1000))
    try:
        ctx.enow.shutdown()
    except Exception as e:
        print("  enow shutdown err: %s" % str(e))
    try:
        network.WLAN(network.STA_IF).active(False)
    except Exception:
        pass
    ctx.sleeping = True
    ctx.batt_crit_shown = False
    ctx.sleep_batt_ms = time.ticks_ms()
    level = ctx.ui.read_soc()
    low = level is not None and level <= BATT_CRIT_SOC
    ctx.batt_crit_shown = low
    ctx.ui.paint_sleep(low_batt=low)


def _wake(ctx):
    print("  Waking")
    try:
        ctx.enow.init()
    except Exception as e:
        print("  enow init err: %s" % str(e))
    _maybe_set_channel()
    ctx.sleeping = False
    ctx.last_activity = time.ticks_ms()
    ctx.ui.mode = "main"
    ctx.ui.paint_full()


def _sleep_tick(ctx):
    """Low-power loop body while asleep: watch for wake, warn on low battery."""
    if ctx.sidebtn.any_pressed() or ctx.ui.poll_touch() is not None:
        _wake(ctx)
        return
    now = time.ticks_ms()
    if time.ticks_diff(now, ctx.sleep_batt_ms) >= BATT_POLL_MS:
        ctx.sleep_batt_ms = now
        level = ctx.ui.read_soc()
        if level is not None and level <= BATT_CRIT_SOC and not ctx.batt_crit_shown:
            ctx.batt_crit_shown = True
            ctx.ui.paint_sleep(low_batt=True)
    if USE_LIGHTSLEEP:
        try:
            machine.lightsleep(SLEEP_TICK_MS)
            return
        except Exception:
            pass
    time.sleep_ms(SLEEP_TICK_MS)


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
    return Ctx(enow, ui, SideButtons())


def loop(ctx):
    if ctx.sleeping:
        _sleep_tick(ctx)
        return

    if time.ticks_diff(time.ticks_ms(), ctx.last_activity) > INACTIVITY_SLEEP_MS:
        _enter_sleep(ctx)
        return

    enow, ui = ctx.enow, ctx.ui
    ui.update_battery()
    _drain_status_reports(enow, ui)

    # Physical side rocker: counts as activity; pages the list in status mode.
    btn = ctx.sidebtn.poll()
    if btn is not None:
        ctx.last_activity = time.ticks_ms()
        if ui.mode == "status" and btn in ("up", "down"):
            ui.scroll_status(btn)
            return

    touch = ui.poll_touch()
    if touch is None:
        time.sleep_ms(50)
        return
    ctx.last_activity = time.ticks_ms()

    x, y = touch
    result = ui.on_touch(x, y)
    if result == "open_settings":
        if not ui.try_debounce():
            return
        ui.open_settings()
        return
    if result == "close_status":
        ui.close_status()
        return
    if result == "status_up":
        ui.scroll_status("up")
        return
    if result == "status_down":
        ui.scroll_status("down")
        return
    if isinstance(result, tuple) and result[0] == "find_device":
        mac = result[1]
        print("  Tap: Find %s" % mac)
        _broadcast_thrice(lambda: enow.broadcast_find_device(mac))
        ui.flash_status_row(mac)
        return
    if result is None:
        return
    if not ui.try_debounce():
        return

    if result.button_id == "status":
        print("  Tap: Status (%s,%s)" % (x, y))
        _broadcast_thrice(enow.broadcast_status_poll)
        ui.open_status()
        return

    print("  Tap: %s (%s,%s)" % (result.label, x, y))
    _dispatch(enow, result)
    ui.show_feedback(result, result.label)


def main():
    try:
        ctx = setup()
        while True:
            loop(ctx)
    except (Exception, KeyboardInterrupt) as e:
        try:
            from utility import print_error_msg

            print_error_msg(e)
        except ImportError:
            raise


if __name__ == "__main__":
    main()
