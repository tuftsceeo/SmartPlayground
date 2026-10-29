# Minimal demo UI: test pattern, touch coordinates and a counter button.
import time

import display_lvgl

display, touch, th = display_lvgl.init()
display_lvgl.test_pattern()

while True:
    time.sleep_ms(100)
