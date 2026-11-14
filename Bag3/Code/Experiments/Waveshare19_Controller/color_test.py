# Bench: four stripes top to bottom: red, green, blue, white.
import machine
import lcd_bus
import lvgl as lv
import st7789
import board

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

scr = lv.screen_active()
scr.set_style_bg_color(lv.color_hex(0x000000), 0)
for i, c in enumerate((0xFF0000, 0x00FF00, 0x0000FF, 0xFFFFFF)):
    band = lv.obj(scr)
    band.set_size(board.LCD_W, board.LCD_H // 4)
    band.set_pos(0, i * (board.LCD_H // 4))
    band.set_style_bg_color(lv.color_hex(c), 0)
    band.set_style_radius(0, 0)
    band.set_style_border_width(0, 0)
lv.refr_now(None)
print("stripes up")
