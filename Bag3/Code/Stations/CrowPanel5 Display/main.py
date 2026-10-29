import time

import display_lvgl
import gallery

display, touch, th = display_lvgl.init()
gallery.show(0)
while True:
    time.sleep_ms(100)
