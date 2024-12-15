
import max7219
from machine import Pin, SPI
import framebuf
import time

# spi = SPI(1, baudrate=10000000, sck=Pin(8), mosi=Pin(10))
# screen = max7219.Max7219(32, 8, spi, Pin(2))
# screen.brightness(15)
# screen.text('1234', 0, 0, 1)
# screen.show()
# print("sent")

# 5x3 font for digits 0-9, capital letters A-Z, and a space character
font_5x3 = {
    '0': [0b111, 0b101, 0b101, 0b101, 0b111],
    '1': [0b110, 0b010, 0b010, 0b010, 0b111],
    '2': [0b111, 0b001, 0b111, 0b100, 0b111],
    '3': [0b111, 0b001, 0b111, 0b001, 0b111],
    '4': [0b001, 0b011, 0b101, 0b111, 0b001],
    '5': [0b111, 0b100, 0b111, 0b001, 0b111],
    '6': [0b111, 0b100, 0b111, 0b101, 0b111],
    '7': [0b111, 0b001, 0b010, 0b100, 0b100],
    '8': [0b111, 0b101, 0b111, 0b101, 0b111],
    '9': [0b111, 0b101, 0b111, 0b001, 0b111],
    'A': [0b111, 0b101, 0b111, 0b101, 0b101],
    'B': [0b110, 0b101, 0b110, 0b101, 0b110],
    'C': [0b111, 0b100, 0b100, 0b100, 0b111],
    'D': [0b110, 0b101, 0b101, 0b101, 0b110],
    'E': [0b111, 0b100, 0b110, 0b100, 0b111],
    'F': [0b111, 0b100, 0b110, 0b100, 0b100],
    'G': [0b111, 0b100, 0b101, 0b101, 0b111],
    'H': [0b101, 0b101, 0b111, 0b101, 0b101],
    'I': [0b111, 0b010, 0b010, 0b010, 0b111],
    'J': [0b001, 0b001, 0b001, 0b001, 0b111],
    'K': [0b101, 0b101, 0b110, 0b101, 0b101],
    'L': [0b100, 0b100, 0b100, 0b100, 0b111],
    'M': [0b101, 0b111, 0b111, 0b101, 0b101],
    'N': [0b111, 0b101, 0b101, 0b101, 0b101],
    'O': [0b010, 0b101, 0b101, 0b101, 0b010],
    'P': [0b111, 0b101, 0b111, 0b100, 0b100],
    'Q': [0b111, 0b101, 0b101, 0b111, 0b011],
    'R': [0b111, 0b101, 0b110, 0b101, 0b101],
    'S': [0b011, 0b100, 0b010, 0b001, 0b110],
    'T': [0b111, 0b010, 0b010, 0b010, 0b010],
    'U': [0b101, 0b101, 0b101, 0b101, 0b111],
    'V': [0b101, 0b101, 0b101, 0b110, 0b100],
    'W': [0b101, 0b101, 0b111, 0b111, 0b101],
    'X': [0b101, 0b101, 0b010, 0b101, 0b101],
    'Y': [0b101, 0b101, 0b111, 0b001, 0b111],
    'Z': [0b111, 0b001, 0b010, 0b100, 0b111],
    ' ': [0b000, 0b000, 0b000, 0b000, 0b000],  # Space character
    '!': [0b010, 0b010, 0b010, 0b000, 0b010],
    '?': [0b111, 0b001, 0b011, 0b000, 0b010],
    '.': [0b000, 0b000, 0b000, 0b000, 0b010],
    ':': [0b000, 0b010, 0b000, 0b010, 0b000],
}


# Function to draw a single character at a specified position
def draw_char(fb, char, x, y):
    """
    Draw a single character at the specified position.
    
    :param fb: The frame buffer
    :param char: The character to draw ('0' to '9' or ' ')
    :param x: x-coordinate (column) where the character will be drawn
    :param y: y-coordinate (row) where the character will be drawn
    :param color: Color to use for the character (e.g., 1 for white)
    """
    color = 1
    if char not in font_5x3:
        return  # Skip if the character is not in the font set

    for row_idx, row_bits in enumerate(font_5x3[char]):
        for col_idx in range(3):
            if (row_bits >> (2 - col_idx)) & 1:
                fb.pixel(x + col_idx, y + row_idx, color)
                
                
def draw_string(display, text, num_matrices, x=0, y=1, spacing=1):
    """
    Draw a string across multiple MAX7219 matrices.

    :param display: The MAX7219 display object
    :param text: The string to display (supports '0'-'9', 'A'-'Z', and ' ')
    :param num_matrices: The number of cascaded matrices
    :param x: Starting x-coordinate (default is 0)
    :param y: Starting y-coordinate (default is 1)
    :param color: Color to use for the characters (default is 1 for ON)
    :param spacing: Space between characters (default is 1 pixel)
    """
    # Calculate the total display width in pixels (each matrix is 8 pixels wide)
    display_width = num_matrices * 8

    # Create a temporary frame buffer for the full display width
    buffer = bytearray(display_width * 8 // 8)  # width * height / 8 (1 bit per pixel)
    fb = framebuf.FrameBuffer(buffer, display_width, 8, framebuf.MONO_HLSB)

    # Current x position for drawing
    current_x = x

    # Loop through each character in the string
    for char in text:
        # Draw the character using draw_char
        draw_char(fb, char, current_x, y)
        current_x += 3 + spacing  # Move to the next position (3 pixels wide + spacing)

        # Stop if the text exceeds the display width
        if current_x >= display_width:
            break

    # Transfer the buffer to the display
    for row in range(8):
        for col in range(display_width):
            display.pixel(col, row, fb.pixel(col, row))

    # Show the updated display
    display.show()

# Function to update a specific matrix with a two-digit number, right-justified
def update_matrix_number(display, matrix_num, number):
    
    # Convert the number to a string and pad with a space if it's a single-digit number
    number_str = str(number)
    if len(number_str) == 1:
        number_str = ' ' + number_str
    
    # Create a temporary 8x8 frame buffer for the individual matrix
    buffer = bytearray(8 * 8 // 8)  # 8x8, 1 bit per pixel
    fb = framebuf.FrameBuffer(buffer, 8, 8, framebuf.MONO_HLSB)

    # Draw the first digit at position (0, 1)
    draw_char(fb, number_str[0], 1, 1)

    # Draw the second digit at position (5, 1)
    draw_char(fb, number_str[1], 5, 1)

    # Update only the target matrix with the new data
    for y in range(8):
        for x in range(8):
            display.pixel(matrix_num * 8 + x, y, fb.pixel(x, y))

    # Show the updated display
    display.show()

# Initialize MAX7219 display (8x32)
spi = SPI(1, baudrate=10000000, sck=Pin(8), mosi=Pin(10))
display = max7219.Max7219(32, 8, spi, Pin(2))
display.brightness(15)


# Example: Display numbers on each matrix individually
update_matrix_number(display, 0, 10)     
time.sleep(1)

update_matrix_number(display, 0, 9)     
time.sleep(1)

update_matrix_number(display, 0, 8)     
time.sleep(1)

update_matrix_number(display, 1, 7)    
time.sleep(1)

update_matrix_number(display, 2, 6)     
time.sleep(1)

update_matrix_number(display, 3, 5)    
time.sleep(1)

update_matrix_number(display, 0, 4)     
time.sleep(1)

update_matrix_number(display, 1, 3)    
time.sleep(1)

update_matrix_number(display, 2, 2)     
time.sleep(1)

update_matrix_number(display, 3, 1)    
time.sleep(1)
 
draw_string(display, " HELLO! ", 4)
