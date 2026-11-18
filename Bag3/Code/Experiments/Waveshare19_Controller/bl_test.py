# Bench: solid red screen, backlight pin HIGH for 2 s then LOW for 6 s, forever.
# Whichever phase is lit tells us the backlight polarity.
import time
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
    color_byte_order=st7789.BYTE_ORDER_RGB,
    rgb565_byte_swap=True,
)
display.set_power(True)
display.init()
display.set_color_inversion(True)

scr = lv.screen_active()
scr.set_style_bg_color(lv.color_hex(0xFF0000), 0)
lv.refr_now(None)

bl = machine.Pin(board.LCD_BL, machine.Pin.OUT)
while True:
    bl.value(1)
    print("BL high (2 s)")
    time.sleep_ms(2000)
    bl.value(0)
    print("BL low (6 s)")
    time.sleep_ms(6000)
