"""Path A: LVGL display setup for lvgl_micropython firmware.

Import only after radio bring-up; driver buffers are allocated here.
"""

import lcd_bus
import machine
import lvgl as lv
import st7789
import task_handler

import board


def init(rotation=0):
    """Create the ST7789 display, turn on the backlight, start the LVGL task handler.

    Returns (display, task_handler) so callers keep references alive.
    """
    spi_bus = machine.SPI.Bus(host=1, mosi=board.LCD_MOSI, miso=-1, sck=board.LCD_SCK)
    display_bus = lcd_bus.SPIBus(
        spi_bus=spi_bus, freq=board.LCD_SPI_HZ, dc=board.LCD_DC, cs=board.LCD_CS
    )
    display = st7789.ST7789(
        data_bus=display_bus,
        display_width=board.LCD_W,
        display_height=board.LCD_H,
        offset_x=board.LCD_X_OFF,
        offset_y=board.LCD_Y_OFF,
        backlight_pin=board.LCD_BL,
        reset_pin=board.LCD_RST,
        reset_state=st7789.STATE_LOW,
        color_space=lv.COLOR_FORMAT.RGB565,
        color_byte_order=st7789.BYTE_ORDER_BGR if board.LCD_BGR else st7789.BYTE_ORDER_RGB,
        rgb565_byte_swap=True,
    )
    display.set_power(True)
    display.init()
    display.set_color_inversion(board.LCD_INVERT)
    display.set_rotation(rotation)
    display.set_backlight(100)
    th = task_handler.TaskHandler()
    return display, th


def test_pattern():
    """Draw a border, R/G/B bars and a label on the active screen."""
    scr = lv.screen_active()
    scr.set_style_bg_color(lv.color_black(), 0)

    border = lv.obj(scr)
    border.set_size(board.LCD_W, board.LCD_H)
    border.set_pos(0, 0)
    border.set_style_bg_opa(lv.OPA.TRANSP, 0)
    border.set_style_border_color(lv.color_white(), 0)
    border.set_style_border_width(1, 0)
    border.set_style_radius(0, 0)
    border.remove_flag(lv.obj.FLAG.SCROLLABLE)

    bar_w = (board.LCD_W - 4) // 3
    for i, hexval in enumerate((0xFF0000, 0x00FF00, 0x0000FF)):
        bar = lv.obj(scr)
        bar.set_size(bar_w, 30)
        bar.set_pos(2 + i * bar_w, 2)
        bar.set_style_bg_color(lv.color_hex(hexval), 0)
        bar.set_style_border_width(0, 0)
        bar.set_style_radius(0, 0)
        bar.remove_flag(lv.obj.FLAG.SCROLLABLE)

    label = lv.label(scr)
    label.set_text("IPS096\nLVGL")
    label.set_style_text_color(lv.color_white(), 0)
    label.align(lv.ALIGN.CENTER, 0, 10)
    return label
