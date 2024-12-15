from machine import Pin
from micropython import const
import framebuf

_DIGIT_0 = const(0x1)

_DECODE_MODE = const(0x9)
_NO_DECODE = const(0x0)

_INTENSITY = const(0xA)
_INTENSITY_MIN = const(0x0)

_SCAN_LIMIT = const(0xB)
_DISPLAY_ALL_DIGITS = const(0x7)

_SHUTDOWN = const(0xC)
_SHUTDOWN_MODE = const(0x0)
_NORMAL_OPERATION = const(0x1)

_DISPLAY_TEST = const(0xF)
_DISPLAY_TEST_NORMAL_OPERATION = const(0x0)

_MATRIX_SIZE = const(8)


# 5x3 font for digits 0-9, capital letters A-Z, and a space character
FONT_5x3 = {
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

ICONS = {
    "SAVE": [
        0b11111111,
        0b10001101,
        0b10000001,
        0b10111101,
        0b10111101,
        0b10111101,
        0b10000001,
        0b11111111,
        
    ],
    "LOAD": [
        0b00000000,
        0b00011000,
        0b00011000,
        0b00011000,
        0b01111110,
        0b00111100,
        0b00011000,
        0b00000000,
    ],
    "WAIT": [
        0b11111110,
        0b10000010,
        0b01000100,
        0b00101000,
        0b00101000,
        0b01010100,
        0b10111010,
        0b11111110,
        
    ],
    "ERROR": [
        0b11111111,
        0b10111101,
        0b11011011,
        0b11100111,
        0b11100111,
        0b11011011,
        0b10111101,
        0b11111111,
    ],
    "REQUEST": [
        0b11111111,
        0b11000011,
        0b11011011,
        0b11110111,
        0b11100111,
        0b11111111,
        0b11100111,
        0b11111111,
    ],
    "QUESTION": [
        
        0b00111100,
        0b01100110,
        0b01100110,
        0b00001100,
        0b00011000,
        0b00011000,
        0b00000000,
        0b00011000,
        
    ],
    "READY": [
        0b11111111,
        0b11111101,
        0b11111001,
        0b11110011,
        0b10100111,
        0b10001111,
        0b11011111,
        0b11111111,
    ],
    "DONE": [
        0b00000001,
        0b00000011,
        0b00000110,
        0b00001100,
        0b10011000,
        0b11110000,
        0b01100000,
        0b00000000,
    ],
}


class Max7219(framebuf.FrameBuffer):
    """
    Driver for MAX7219 8x8 LED matrices

    Example for ESP8266 with 2x4 matrices (one on top, one on bottom),
    so we have a 32x16 display area:

    >>> from machine import Pin, SPI
    >>> from max7219 import Max7219
    >>> spi = SPI(1, baudrate=10000000)
    >>> screen = Max7219(32, 16, spi, Pin(15))
    >>> screen.rect(0, 0, 32, 16, 1)  # Draws a frame
    >>> screen.text('Hi!', 4, 4, 1)
    >>> screen.show()

    On some matrices, the display is inverted (rotated 180°), in this case
     you can use `rotate_180=True` in the class constructor.
    """

    def __init__(self, width, height, spi, cs, rotate_180=False):
        # Pins setup
        self.spi = spi
        self.cs = cs
        self.cs.init(Pin.OUT, True)

        # Dimensions
        self.width = width
        self.height = height
        
        # Guess matrices disposition
        self.cols = width // _MATRIX_SIZE
        self.rows = height // _MATRIX_SIZE
        self.nb_matrices = self.cols * self.rows
        self.rotate_180 = rotate_180

        # 1 bit per pixel (on / off) -> 8 bytes per matrix
        self.buffer = bytearray(width * height // 8)
        format = framebuf.MONO_HLSB if not self.rotate_180 else framebuf.MONO_HMSB
        super().__init__(self.buffer, width, height, format)

        # Init display
        self.init_display()

    def _write_command(self, command, data):
        """Write command on SPI"""
        cmd = bytearray([command, data])
        self.cs(0)
        for matrix in range(self.nb_matrices):
            self.spi.write(cmd)
        self.cs(1)

    def init_display(self):
        """Init hardware"""
        for command, data in (
            (_SHUTDOWN, _SHUTDOWN_MODE),  # Prevent flash during init
            (_DECODE_MODE, _NO_DECODE),
            (_DISPLAY_TEST, _DISPLAY_TEST_NORMAL_OPERATION),
            (_INTENSITY, _INTENSITY_MIN),
            (_SCAN_LIMIT, _DISPLAY_ALL_DIGITS),
            (_SHUTDOWN, _NORMAL_OPERATION),  # Let's go
        ):
            self._write_command(command, data)

        self.fill(0)
        self.show()

    def brightness(self, value):
        """Set display brightness (0 to 15)"""
        if not 0 <= value < 16:
            raise ValueError("Brightness must be between 0 and 15")
        self._write_command(_INTENSITY, value)

    def show(self):
        """Update display"""
        # Write line per line on the matrices
        for line in range(8):
            self.cs(0)

            for matrix in range(self.nb_matrices):
                # Guess where the matrix is placed
                row, col = divmod(matrix, self.cols)
                # Compute where the data starts
                if not self.rotate_180:
                    offset = row * 8 * self.cols
                    index = col + line * self.cols + offset
                else:
                    offset = 8 * self.cols - row * self.cols * 8 - 1
                    index = self.cols * (8 - line) - col + offset

                self.spi.write(bytearray([_DIGIT_0 + line, self.buffer[index]]))

            self.cs(1)
    
    # Function to draw a single character at a specified position
    def _draw_5x3_char(self, fb, char, x, y):
        """
        Draw a single character using the 5x3 font at the specified position
        in a provided framebuffer. 
        
        :param fb: The frame buffer
        :param char: The character to draw ('0' to '9' or ' ')
        :param x: x-coordinate (column) where the character will be drawn
        :param y: y-coordinate (row) where the character will be drawn
        :param color: Color to use for the character (e.g., 1 for white)
        """
        color = 1
        if char not in FONT_5x3:
            return  # Skip if the character is not in the font set

        for row_idx, row_bits in enumerate(FONT_5x3[char]):
            for col_idx in range(3):
                if (row_bits >> (2 - col_idx)) & 1:
                    fb.pixel(x + col_idx, y + row_idx, color)
                    
    def draw_5x3_string(self, text, x=1, y=1, spacing=1):
        """
        Draw a string with 5x3 font across multiple MAX7219 matrices.

        :param text: The string to display (supports '0'-'9', 'A'-'Z', and ' ')
        :param x: Starting x-coordinate (default is 0)
        :param y: Starting y-coordinate (default is 1)
        :param spacing: Space between characters (default is 1 pixel)
        """

        # Create a temporary frame buffer for the full display width
        buffer = bytearray(self.width * _MATRIX_SIZE // 8)  # width * height / 8 (1 bit per pixel)
        fb = framebuf.FrameBuffer(buffer, self.width, _MATRIX_SIZE, framebuf.MONO_HLSB)

        # Current x position for drawing
        current_x = x

        # Loop through each character in the string
        for char in text:
            # Draw the character using draw_char
            self._draw_5x3_char(fb, char, current_x, y)
            current_x += 3 + spacing  # Move to the next position (3 pixels wide + spacing)

            # Stop if the text exceeds the display width
            if current_x >= self.width:
                break

        # Transfer the buffer to the display
        for y_idx in range(_MATRIX_SIZE):
            for x_idx in range(self.width):
                self.pixel(x_idx, y_idx, fb.pixel(x_idx, y_idx))

 
    def draw_5x3_num(self, matrix_num, text, x=1, y=1):
        """
        Draw a two character string or digit on MAX7219 matrices using
        the 5x3 font.

        :param matrix_num: The matrix to display on
        :param text: Space between characters (default is 1 pixel)
        :param x: Starting x-coordinate (default is 1)
        :param y: Starting y-coordinate (default is 1)
        """
        
        # Convert a number to a string pad with a space if it's a single-character
        text_str = str(text)
        if len(text_str) == 1:
            text_str = ' ' + text_str
        
        # Create a temporary 8x8 frame buffer for the individual matrix
        buffer = bytearray(_MATRIX_SIZE * _MATRIX_SIZE // 8)  # 8x8, 1 bit per pixel
        fb = framebuf.FrameBuffer(buffer, _MATRIX_SIZE, _MATRIX_SIZE, framebuf.MONO_HLSB)

        # Draw the first digit at position (0, 1) of the matrix
        self._draw_5x3_char(fb, text_str[0], x, y)

        # Draw the second digit at position (5, 1) of the matrix
        self._draw_5x3_char(fb, text_str[1], x+4, y)

        # Update only the target matrix with the new data
        for y_idx in range(_MATRIX_SIZE):
            for x_idx in range(_MATRIX_SIZE):
                self.pixel(matrix_num * _MATRIX_SIZE + x_idx, y_idx, fb.pixel(x_idx, y_idx))

    def draw_5x3_list(self, num_list, x=1, y=1):
        """
        Draw a two character string or digit on MAX7219 matrices using
        the 5x3 font.

        :param matrix_num: The matrix to display on
        :param text: Space between characters (default is 1 pixel)
        :param x: Starting x-coordinate (default is 1)
        :param y: Starting y-coordinate (default is 1)
        """
        for m_idx, num in enumerate(num_list[:self.nb_matrices]):
            self.draw_5x3_num(m_idx, num, x, y)
    
    def show_icon(self, icon_name, matrix_index=0):
        """
        Display a predefined 8x8 icon on a specified matrix without overwriting other matrices.
        
        :param icon_name: The name of the icon ("SAVE", "LOAD", "WAIT", "ERROR", "REQUEST", "READY", "DONE")
        :param matrix_index: The index of the matrix to display the icon on (0-based)
        """
        icon = ICONS.get(icon_name)
        if not icon:
            print(f"Icon '{icon_name}' not found.")
            return

        # Display the icon on the specified matrix only
        for y, row in enumerate(icon):
            for x in range(8):
                if (row >> (7 - x)) & 1:
                    self.pixel(matrix_index * _MATRIX_SIZE + x, y, 1)

           
