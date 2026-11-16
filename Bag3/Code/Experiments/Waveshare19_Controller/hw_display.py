# Display + touch bring-up for the mockup. Copied from display_test.py
# (same SPI bus, ST7789 settings, backlight pin and CST816 setup); display_test.py itself
# is unchanged and still runs on its own.
import machine
import lcd_bus
import lvgl as lv
import st7789
import i2c
import cst816s
import task_handler
import board


def init():
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
    backlight = machine.Pin(board.LCD_BL, machine.Pin.OUT, value=0)
    bus = i2c.I2C.Bus(host=0, scl=board.I2C_SCL, sda=board.I2C_SDA, freq=400000)
    dev = i2c.I2C.Device(bus=bus, dev_id=board.TOUCH_ADDR, reg_bits=8)
    touch = cst816s.CST816S(dev, reset_pin=board.TP_RST)
    th = task_handler.TaskHandler()
    return display, touch, th, backlight
