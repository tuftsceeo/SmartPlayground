"""lv_probe.py -- facts needed to choose a faster keyboard rendering.

Prints: LVGL version, free MicroPython heap, display draw-buffer size
(if exposed), and whether LVGL can draw an RGB565 image read from a
/flash file (so a pre-rendered keyboard ring need not sit in RAM).

    mpremote connect <port> resume run tools/lv_probe.py

Writes /flash/lv_probe.bin (64x64 test image, 8 KB) and deletes it.
"""

import gc
import os
import struct
import time

import M5
import m5ui
import lvgl as lv

M5.begin()
m5ui.init()
gc.collect()
print("lvgl", lv.version_major(), lv.version_minor(), lv.version_patch())
print("mem_free", gc.mem_free())

disp = lv.display_get_default()
for name in ("get_horizontal_resolution", "get_vertical_resolution"):
    print(name, getattr(disp, name)())
buf = getattr(disp, "get_buf_active", None)
print("draw buffer accessor:", "yes" if buf else "no")

# LVGL 9 image header: magic 0x19, cf RGB565 0x12, flags, w, h, stride, reserved.
W = H = 64
path = "/flash/lv_probe.bin"
with open(path, "wb") as f:
    f.write(struct.pack("<BBHHHHH", 0x19, 0x12, 0, W, H, W * 2, 0))
    row = struct.pack("<H", 0xF81F) * W        # magenta
    for _ in range(H):
        f.write(row)

page = m5ui.M5Page(bg_c=0xFFFFFF)
page.screen_load()
img = lv.image(page)
img.set_src("S:" + path)
img.align(lv.ALIGN.CENTER, 0, 0)
t0 = time.ticks_ms()
lv.refr_now(None)
print("file image: size %dx%d, refresh %d ms"
      % (img.get_width(), img.get_height(), time.ticks_diff(time.ticks_ms(), t0)))
print("(64x64 means LVGL read the file; 0x0 means it could not)")
print("ASK: is a magenta square visible in the centre?")
os.remove(path)
gc.collect()
print("mem_free after", gc.mem_free())
