
import max7219
from machine import Pin, SPI
import framebuf
import time


# old test display
# Initialize MAX7219 display (8x32)
spi = SPI(1, baudrate=10000000, sck=Pin(8), mosi=Pin(10))
display = max7219.Max7219(32, 8, spi, Pin(2))
display.brightness(15)


# Example: Display numbers on each matrix individually
display.draw_5x3_num(0, 10)
display.show()
time.sleep(1)

display.draw_5x3_num(0, 9)
display.show()
time.sleep(1)

display.draw_5x3_num(0, 8)
display.show()
time.sleep(1)

display.draw_5x3_num(1, 7)
display.show()
time.sleep(1)

display.draw_5x3_num(2, 6)
display.show()
time.sleep(1)

display.draw_5x3_num(3, 5)
display.show()
time.sleep(1)

display.draw_5x3_num(0, 4)
display.show()
time.sleep(1)

display.draw_5x3_num(1, 3)
display.show()
time.sleep(1)

display.draw_5x3_num(2, 2)
display.show()
time.sleep(1)

display.draw_5x3_num(3, 1)
display.show()
time.sleep(1)
 
display.draw_5x3_string(" HELLO! ")
display.show()
time.sleep(1)

display.draw_5x3_list([12, 10, 8 ,6, 4])
display.show()
time.sleep(1)


