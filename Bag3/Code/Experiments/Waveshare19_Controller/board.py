# Waveshare ESP32-S3-Touch-LCD-1.9 pin map (from Waveshare's GPIO table).
# Confirmed against Waveshare's examples (github.com/waveshareteam/ESP32-S3-LCD-1.9).
# GPIO33-37 belong to the octal PSRAM and must not be used.

LCD_W = 170
LCD_H = 320
LCD_X_OFFSET = 35   # 170 of the ST7789's 240 columns, centered
LCD_Y_OFFSET = 0

LCD_RST = 9
LCD_CLK = 10
LCD_DC = 11
LCD_CS = 12
LCD_MOSI = 13
LCD_BL = 14         # active LOW (confirmed on bench)
LCD_BGR = True      # red shows blue in RGB order (confirmed on bench)

TP_RST = 17
TP_INT = 21

I2C_SDA = 47        # touch and IMU share this bus
I2C_SCL = 48
TOUCH_ADDR = 0x15   # CST816D (chip ID 0xB6)
IMU_ADDR = 0x6B     # QMI8658 (WHO_AM_I 0x05)

IMU_INT1 = 8
IMU_INT2 = 7

# SD card is SDMMC 1-bit, not SPI
SD_CMD = 39
SD_D0 = 40
SD_CLK = 41

BAT_ADC = 4         # ADC1 ch3; battery V = pin V x 3
BAT_DIVIDER = 3
BTN_BOOT = 0

FREE_PINS = (1, 2, 3, 5, 6, 15, 16, 18, 19, 20, 38, 42, 45, 46)

# NFC reader (not fitted; pins chosen 2026-11-15, never run). Own I2C bus so the
# reader cannot stall touch or IMU on the shared bus. All four come from FREE_PINS.
NFC_SDA = 1         # plain GPIO (ADC1 ch0), no strapping or boot role
NFC_SCL = 2         # plain GPIO (ADC1 ch1), no strapping or boot role
NFC_RST = 5         # reader reset / power-down, plain GPIO
NFC_IRQ = 6         # reader interrupt, plain GPIO (optional, polling works without)
NFC_I2C_HOST = 1    # host 0 is the touch/IMU bus
# Avoided on purpose: 3, 45, 46 (strapping), 19/20 (native USB D-/D+), 42 (JTAG pad),
# 15/16 (32 kHz crystal pads), 38 (kept spare).
