import machine
from machine import I2C
from machine import Pin
import ssd1306

i2c = I2C(scl = Pin(23), sda = Pin(22))
# note you might get a warning here - you can ignore it

display = ssd1306.SSD1306_I2C(128, 64,i2c)

display.rect(10,10,60,50,1)
display.text('Good Morning', 0, 0, 1)
display.show()
