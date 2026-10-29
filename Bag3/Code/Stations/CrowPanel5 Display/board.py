# Pin map for the Elecrow CrowPanel HMI 5.0" V3 (ESP32-S3-WROOM-1-N4R8).
# Constants only: safe to import before radio bring-up.
# RGB pins and timings: Elecrow's LovyanGFX config for this board.

LCD_W = 800
LCD_H = 480

# 16-bit RGB565 parallel bus, data0..data15 = B0-B4, G0-G5, R0-R4
LCD_DATA = (8, 3, 46, 9, 1, 5, 6, 7, 15, 16, 4, 45, 48, 47, 21, 14)
LCD_DE = 40
LCD_VSYNC = 41
LCD_HSYNC = 39
LCD_PCLK = 0
LCD_PCLK_HZ = 12_000_000   # LGFX uses 15 MHz; at 15 the image drifts sideways
LCD_PCLK_ACTIVE_LOW = True   # LGFX pclk_active_neg = 1

LCD_HSYNC_FRONT = 8
LCD_HSYNC_PULSE = 4
LCD_HSYNC_BACK = 43
LCD_VSYNC_FRONT = 8
LCD_VSYNC_PULSE = 4
LCD_VSYNC_BACK = 12

LCD_BL = 2      # backlight

# I2C: GT911 touch (0x5D), PCA9557 expander (0x18); 0x24 also answers
I2C_SDA = 19
I2C_SCL = 20
PCA9557_ADDR = 0x18
TOUCH_RST_IO = 0   # PCA9557 IO0
TOUCH_INT_IO = 1   # PCA9557 IO1

# HMI port
GPIO_D = 38
UART_TX = 43
UART_RX = 44

I2S_LRCLK = 18
I2S_BCLK = 42
I2S_SDIN = 17

SD_MOSI = 11
SD_MISO = 13
SD_CLK = 12
SD_CS = 10
