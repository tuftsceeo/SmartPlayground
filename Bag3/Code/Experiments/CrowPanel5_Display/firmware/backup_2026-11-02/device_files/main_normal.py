import time

import display_lvgl
import home

display, touch, th = display_lvgl.init()
home.show()
while True:
    time.sleep_ms(100)
