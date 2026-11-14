# Bench test: LVGL screen with corner marks, live touch dot and coordinate label.
# Runs until reset; logs raw touch registers and LVGL points to test.log.
import time
import machine
import lcd_bus
import lvgl as lv
import st7789
import i2c
import cst816s
import task_handler
import board

_log = open('test.log', 'w')


def log(*a):
    print(*a)
    _log.write(' '.join(str(x) for x in a) + '\n')
    _log.flush()


spi_bus = machine.SPI.Bus(host=1, mosi=board.LCD_MOSI, miso=-1, sck=board.LCD_CLK)
display_bus = lcd_bus.SPIBus(spi_bus=spi_bus, freq=40000000, dc=board.LCD_DC, cs=board.LCD_CS)
display = st7789.ST7789(
    data_bus=display_bus,
    display_width=board.LCD_W,
    display_height=board.LCD_H,
    offset_x=board.LCD_X_OFFSET,
    offset_y=board.LCD_Y_OFFSET,
    reset_pin=board.LCD_RST,
    reset_state=st7789.STATE_LOW,
    color_space=lv.COLOR_FORMAT.RGB565,
    color_byte_order=st7789.BYTE_ORDER_BGR if board.LCD_BGR else st7789.BYTE_ORDER_RGB,
    rgb565_byte_swap=True,
)
display.set_power(True)
display.init()
display.set_color_inversion(True)
# Driver's set_backlight() follows power polarity, not backlight; drive the pin directly.
backlight = machine.Pin(board.LCD_BL, machine.Pin.OUT, value=0)

bus = i2c.I2C.Bus(host=0, scl=board.I2C_SCL, sda=board.I2C_SDA, freq=400000)
dev = i2c.I2C.Device(bus=bus, dev_id=board.TOUCH_ADDR, reg_bits=8)
touch = cst816s.CST816S(dev, reset_pin=board.TP_RST)

th = task_handler.TaskHandler()

scr = lv.screen_active()
scr.set_style_bg_color(lv.color_hex(0x000000), 0)

frame = lv.obj(scr)
frame.set_size(board.LCD_W, board.LCD_H)
frame.set_pos(0, 0)
frame.set_style_bg_opa(0, 0)
frame.set_style_border_color(lv.color_hex(0xFFFFFF), 0)
frame.set_style_border_width(2, 0)
frame.set_style_radius(0, 0)

for i, (c, x) in enumerate(((0xFF0000, 10), (0x00FF00, 60), (0x0000FF, 110))):
    bar = lv.obj(scr)
    bar.set_size(50, 60)
    bar.set_pos(x, 40)
    bar.set_style_bg_color(lv.color_hex(c), 0)
    bar.set_style_radius(0, 0)
    bar.set_style_border_width(0, 0)

title = lv.label(scr)
title.set_text("R  G  B\nTL corner")
title.set_pos(6, 6)
title.set_style_text_color(lv.color_hex(0xFFFFFF), 0)

coords = lv.label(scr)
coords.set_text("touch me")
coords.align(lv.ALIGN.BOTTOM_MID, 0, -10)
coords.set_style_text_color(lv.color_hex(0xFFFF00), 0)

dot = lv.obj(scr)
dot.set_size(16, 16)
dot.set_style_radius(8, 0)
dot.set_style_bg_color(lv.color_hex(0xFF00FF), 0)
dot.add_flag(lv.obj.FLAG.HIDDEN)

pt = lv.point_t()
raw = bytearray(6)
lastraw = None
last = None
while True:
    lv.refr_now(None)
    dev.read_mem(0x01, buf=raw)
    if raw != lastraw:
        lastraw = bytes(raw)
        log("raw", [hex(b) for b in raw])
    touch.get_point(pt)
    p = (pt.x, pt.y)
    if p != last:
        last = p
        dot.remove_flag(lv.obj.FLAG.HIDDEN)
        dot.set_pos(pt.x - 8, pt.y - 8)
        coords.set_text(f"x={pt.x} y={pt.y}")
        log("touch", pt.x, pt.y)
    time.sleep_ms(30)
