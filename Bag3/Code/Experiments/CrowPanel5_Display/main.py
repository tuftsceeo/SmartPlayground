import gc
import time
import machine

import board
import code_link

code_link.prewarm()
code = code_link.CodeLink()
code.mgr.init()

import display_lvgl
display, touch, th = display_lvgl.init()

import ui_kit
ui_kit.fs_init()
import panel
panel.Panel(code)
ui_kit.go("home", push=False)
panel.run()
