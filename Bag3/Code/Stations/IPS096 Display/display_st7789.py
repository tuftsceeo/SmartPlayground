"""Path B: stock MicroPython with russhughes st7789py (pure Python).

Import only after radio bring-up.
"""

from machine import Pin, SPI

import st7789py as st7789
import vga1_8x8 as font

import board


def init():
    """Create and return the ST7789 display with the backlight on."""
    spi = SPI(
        1, baudrate=board.LCD_SPI_HZ, polarity=1, phase=1,
        sck=Pin(board.LCD_SCK), mosi=Pin(board.LCD_MOSI),
    )
    # custom_rotations entry: (width, height, x_start, y_start, madctl)
    rotations = ((board.LCD_W, board.LCD_H, board.LCD_X_OFF, board.LCD_Y_OFF, 0x00),)
    tft = st7789.ST7789(
        spi, board.LCD_W, board.LCD_H,
        reset=Pin(board.LCD_RST, Pin.OUT),
        dc=Pin(board.LCD_DC, Pin.OUT),
        cs=Pin(board.LCD_CS, Pin.OUT),
        backlight=Pin(board.LCD_BL, Pin.OUT),
        rotation=0,
        custom_rotations=rotations,
        color_order=st7789.BGR if board.LCD_BGR else st7789.RGB,
    )
    tft.inversion_mode(board.LCD_INVERT)
    return tft


def test_pattern(tft):
    """Draw a border, R/G/B bars and a label."""
    tft.fill(st7789.BLACK)
    tft.rect(0, 0, board.LCD_W, board.LCD_H, st7789.WHITE)
    bar_w = (board.LCD_W - 4) // 3
    for i, c in enumerate((st7789.RED, st7789.GREEN, st7789.BLUE)):
        tft.fill_rect(2 + i * bar_w, 2, bar_w, 30, c)
    tft.text(font, "IPS096", 16, 70, st7789.WHITE)
