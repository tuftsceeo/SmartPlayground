# Pin map for the Seeed XIAO 0.96" IPS Display (ESP32-S3 Plus).
# Constants only: safe to import before radio bring-up.

LCD_CS = 3      # D2
LCD_DC = 4      # D3
LCD_SCK = 7     # D8
LCD_MOSI = 9    # D10
LCD_RST = 13    # D17
LCD_BL = 12     # D18, backlight PWM

LCD_W = 80
LCD_H = 160
LCD_X_OFF = 24  # panel RAM offsets; tune on first test
LCD_Y_OFF = 0
LCD_BGR = True
LCD_INVERT = False
LCD_SPI_HZ = 40_000_000

BTN_USR1 = 43   # D6, active-low; UART0 TX
BTN_USR2 = 44   # D7, active-low; UART0 RX

I2C_SDA = 5     # D4, LSM6DS3 + back pad
I2C_SCL = 6     # D5
IMU_INT = 41    # D14

PDM_CLK = 1     # D0
PDM_DATA = 2    # D1
I2S_SD = 38     # D11
I2S_SCK = 39    # D12
I2S_WS = 40     # D13

VBAT_ADC = 10   # D16, 316k/160k divider
VBAT_RATIO = (316 + 160) / 160
