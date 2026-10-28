# Smoke test: radio first, then display, then poll buttons and ESP-NOW.
import network
import espnow

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
esp = espnow.ESPNow()
esp.active(True)
esp.add_peer(b"\xff" * 6)

import time
from machine import Pin

import board

DISPLAY_PATH = "lvgl"  # "lvgl" (Path A) or "st7789" (Path B)

btn1 = Pin(board.BTN_USR1, Pin.IN, Pin.PULL_UP)
btn2 = Pin(board.BTN_USR2, Pin.IN, Pin.PULL_UP)

if DISPLAY_PATH == "lvgl":
    import display_lvgl
    display, th = display_lvgl.init()
    label = display_lvgl.test_pattern()
else:
    import display_st7789
    tft = display_st7789.init()
    display_st7789.test_pattern(tft)
    label = None

start = time.ticks_ms()
last_tx = start
rx_count = 0
last_state = None

while True:
    now = time.ticks_ms()
    if time.ticks_diff(now, last_tx) >= 1000:
        esp.send(b"\xff" * 6, f"ips096 {time.ticks_diff(now, start) // 1000}", False)
        last_tx = now
    host, msg = esp.irecv(0)
    if msg:
        rx_count += 1
    state = (btn1.value() == 0, btn2.value() == 0, rx_count)
    if state != last_state:
        print(f"b1={state[0]} b2={state[1]} rx={rx_count}")
        if label is not None:
            label.set_text(f"B1 {int(state[0])} B2 {int(state[1])}\nRX {rx_count}")
        last_state = state
    time.sleep_ms(1)
