
import max7219
from machine import Pin, SPI
import framebuf
import time


matrix_count = 8
# Initialize MAX7219 display (8x32)
spi = SPI(1, baudrate=10000000, sck=Pin(8), mosi=Pin(10))
display = max7219.Max7219(matrix_count*8, 8, spi, Pin(2))
display.brightness(15)


# Example: Display numbers on each matrix individually
for i in range(matrix_count):
    display.draw_5x3_num(i, i)
    display.show()
    time.sleep(1)
    
for i in range(matrix_count):
    display.draw_5x3_num(i, i*3)
    display.show()
    time.sleep(1)


display.fill(0)
display.text("1234567890abcd",0, 0)
#display.show_icon("REQUEST", 3)
display.show()
time.sleep(20)
 
display.fill(0)
display.draw_5x3_string("TUFTS UNIVERSITY")
#display.show_icon("READY", matrix_index=3)
display.show()
time.sleep(10)

# display.draw_5x3_list([12, 10, 8 ,6, 4])
# display.show()
# time.sleep(.1)

display.fill(0)
display.show_icon("SAVE", matrix_index=0)    # Display SAVE icon on the first matrix
display.show_icon("LOAD", matrix_index=1)    # Display LOAD icon on the second matrix
display.show_icon("WAIT", matrix_index=2)
display.show_icon("ERROR", matrix_index=3)
display.show()
time.sleep(20)

display.fill(0)
display.show_icon("REQUEST", matrix_index=0)
display.show_icon("QUESTION", matrix_index=1) # Display SAVE icon on the first matrix
display.show_icon("READY", matrix_index=2)    # Display LOAD icon on the second matrix
display.show_icon("DONE", matrix_index=3)
display.show()
time.sleep(10)