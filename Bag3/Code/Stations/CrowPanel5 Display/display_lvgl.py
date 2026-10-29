"""LVGL display and touch setup for lvgl_micropython firmware.

Import only after radio bring-up; driver buffers are allocated here.
"""

import time

import gt911
import i2c
import lcd_bus
import lvgl as lv
import rgb_display
import task_handler

import board

# PCA9557 registers
_OUT = 0x01
_CONFIG = 0x03  # 1 = input


def touch_reset(dev):
    """Elecrow's V3 touch timing: INT low while RST rises, so the GT911 takes address 0x5D."""
    rst = 1 << board.TOUCH_RST_IO
    irq = 1 << board.TOUCH_INT_IO
    dev.write_mem(_CONFIG, bytes([0x00]))
    dev.write_mem(_OUT, bytes([0x00]))
    time.sleep_ms(20)
    dev.write_mem(_OUT, bytes([rst]))
    time.sleep_ms(100)
    dev.write_mem(_CONFIG, bytes([irq]))
    time.sleep_ms(50)


def init():
    """Create the RGB display and GT911 touch, turn on the backlight, start the task handler.

    Returns (display, touch, task_handler) so callers keep references alive.
    """
    d = board.LCD_DATA
    bus = lcd_bus.RGBBus(
        hsync=board.LCD_HSYNC,
        vsync=board.LCD_VSYNC,
        de=board.LCD_DE,
        pclk=board.LCD_PCLK,
        data0=d[0], data1=d[1], data2=d[2], data3=d[3],
        data4=d[4], data5=d[5], data6=d[6], data7=d[7],
        data8=d[8], data9=d[9], data10=d[10], data11=d[11],
        data12=d[12], data13=d[13], data14=d[14], data15=d[15],
        freq=board.LCD_PCLK_HZ,
        hsync_front_porch=board.LCD_HSYNC_FRONT,
        hsync_back_porch=board.LCD_HSYNC_BACK,
        hsync_pulse_width=board.LCD_HSYNC_PULSE,
        vsync_front_porch=board.LCD_VSYNC_FRONT,
        vsync_back_porch=board.LCD_VSYNC_BACK,
        vsync_pulse_width=board.LCD_VSYNC_PULSE,
        pclk_active_low=board.LCD_PCLK_ACTIVE_LOW,
    )
    display = rgb_display.RGBDisplay(
        data_bus=bus,
        display_width=board.LCD_W,
        display_height=board.LCD_H,
        backlight_pin=board.LCD_BL,
        backlight_on_state=rgb_display.STATE_PWM,
        color_space=lv.COLOR_FORMAT.RGB565,
    )
    display.init()
    display.set_backlight(100)

    i2c_bus = i2c.I2C.Bus(host=0, scl=board.I2C_SCL, sda=board.I2C_SDA, freq=400000)
    touch_reset(i2c.I2C.Device(bus=i2c_bus, dev_id=board.PCA9557_ADDR, reg_bits=8))
    touch_dev = i2c.I2C.Device(bus=i2c_bus, dev_id=gt911.I2C_ADDR, reg_bits=gt911.BITS)
    touch = gt911.GT911(touch_dev)

    th = task_handler.TaskHandler()
    return display, touch, th


def test_pattern():
    """Border, R/G/B bars, a counter button and a label that follows touches."""
    scr = lv.screen_active()
    scr.set_style_bg_color(lv.color_black(), 0)
    scr.remove_flag(lv.obj.FLAG.SCROLLABLE)

    border = lv.obj(scr)
    border.set_size(board.LCD_W, board.LCD_H)
    border.set_pos(0, 0)
    border.set_style_bg_opa(lv.OPA.TRANSP, 0)
    border.set_style_border_color(lv.color_white(), 0)
    border.set_style_border_width(2, 0)
    border.set_style_radius(0, 0)
    border.remove_flag(lv.obj.FLAG.SCROLLABLE)
    border.remove_flag(lv.obj.FLAG.CLICKABLE)

    bar_w = (board.LCD_W - 8) // 3
    for i, hexval in enumerate((0xFF0000, 0x00FF00, 0x0000FF)):
        bar = lv.obj(scr)
        bar.set_size(bar_w, 120)
        bar.set_pos(4 + i * bar_w, 4)
        bar.set_style_bg_color(lv.color_hex(hexval), 0)
        bar.set_style_border_width(0, 0)
        bar.set_style_radius(0, 0)
        bar.remove_flag(lv.obj.FLAG.SCROLLABLE)
        bar.remove_flag(lv.obj.FLAG.CLICKABLE)

    label = lv.label(scr)
    label.set_text("CrowPanel 5.0\nTouch anywhere")
    label.set_style_text_color(lv.color_white(), 0)
    label.align(lv.ALIGN.CENTER, 0, 0)

    btn = lv.button(scr)
    btn.set_size(240, 90)
    btn.align(lv.ALIGN.BOTTOM_MID, 0, -30)
    btn_label = lv.label(btn)
    btn_label.set_text("Count 0")
    btn_label.center()
    count = [0]

    def on_click(e):
        count[0] += 1
        btn_label.set_text(f"Count {count[0]}")
        print(f"button count={count[0]}")

    btn.add_event_cb(on_click, lv.EVENT.CLICKED, None)

    def on_press(e):
        p = lv.point_t()
        lv.indev_active().get_point(p)
        label.set_text(f"CrowPanel 5.0\nTouch {p.x}, {p.y}")

    scr.add_event_cb(on_press, lv.EVENT.PRESSING, None)
    return label
