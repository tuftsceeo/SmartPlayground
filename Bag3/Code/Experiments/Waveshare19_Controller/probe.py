# Bench probe: I2C scan, battery ADC, backlight, touch and IMU reads.
# Run with: mpremote run probe.py
import time
from machine import Pin, I2C, ADC, PWM
import board

Pin(board.TP_RST, Pin.OUT, value=0)
time.sleep_ms(10)
Pin(board.TP_RST, Pin.OUT, value=1)
time.sleep_ms(50)

i2c = I2C(0, sda=Pin(board.I2C_SDA), scl=Pin(board.I2C_SCL), freq=400000)
print("i2c:", [hex(a) for a in i2c.scan()])

adc = ADC(Pin(board.BAT_ADC))
adc.atten(ADC.ATTN_11DB)
print("bat raw mV:", adc.read_uv() // 1000)

bl = PWM(Pin(board.LCD_BL), freq=1000, duty_u16=40000)
print("backlight on")

for addr in (0x6A, 0x6B):
    try:
        print(f"imu {hex(addr)} WHO_AM_I:", hex(i2c.readfrom_mem(addr, 0x00, 1)[0]))
    except OSError:
        pass

print("touch the screen (10 s)...")
end = time.ticks_add(time.ticks_ms(), 10000)
while time.ticks_diff(end, time.ticks_ms()) > 0:
    try:
        d = i2c.readfrom_mem(board.TOUCH_ADDR, 0x02, 5)
        if d[0] & 0x0F:
            x = ((d[1] & 0x0F) << 8) | d[2]
            y = ((d[3] & 0x0F) << 8) | d[4]
            print("touch", x, y)
    except OSError:
        pass
    time.sleep_ms(50)
print("done")
