# Minimal demo UI: test pattern plus a counter driven by the two buttons.
import time
from machine import Pin

import board

DISPLAY_PATH = "lvgl"  # "lvgl" (Path A) or "st7789" (Path B)
DEMO = "gallery"  # "gallery" (design-system pages, Path A only) or "test"

btn1 = Pin(board.BTN_USR1, Pin.IN, Pin.PULL_UP)
btn2 = Pin(board.BTN_USR2, Pin.IN, Pin.PULL_UP)

if DISPLAY_PATH == "lvgl" and DEMO == "gallery":
    import lvgl as lv
    import display_lvgl
    import gallery
    display, th = display_lvgl.init(lv.DISPLAY_ROTATION._90)

    def show(count):
        print(f"page {gallery.show(count)}")
elif DISPLAY_PATH == "lvgl":
    import display_lvgl
    display, th = display_lvgl.init()
    label = display_lvgl.test_pattern()

    def show(count):
        label.set_text(f"IPS096\nCount {count}")
else:
    import display_st7789
    import st7789py as st7789
    import vga1_8x8 as font
    tft = display_st7789.init()
    display_st7789.test_pattern(tft)

    def show(count):
        tft.fill_rect(4, 90, board.LCD_W - 8, 10, st7789.BLACK)
        tft.text(font, f"Cnt {count}", 8, 90, st7789.WHITE)

count = 0
prev1 = prev2 = 1
show(count)

while True:
    v1, v2 = btn1.value(), btn2.value()
    if prev1 == 1 and v1 == 0:
        count += 1
        show(count)
        print(f"USR1 count={count}")
    if prev2 == 1 and v2 == 0:
        count = 0
        show(count)
        print("USR2 reset")
    prev1, prev2 = v1, v2
    time.sleep_ms(1)
