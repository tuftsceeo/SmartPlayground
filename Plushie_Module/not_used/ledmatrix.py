from time import sleep_ms
import time
I2C_CMD_CONTINUE_DATA = 0x81

GROVE_TWO_RGB_LED_MATRIX_DEF_I2C_ADDR = 0x65  # Default I2C address
GROVE_TWO_RGB_LED_MATRIX_VID = 0x2886         # Vendor ID
GROVE_TWO_RGB_LED_MATRIX_PID = 0x8005         # Product ID

I2C_CMD_GET_DEV_ID = 0x00
I2C_CMD_DISP_BAR = 0x01
I2C_CMD_DISP_EMOJI = 0x02
I2C_CMD_DISP_NUM = 0x03
I2C_CMD_DISP_STR = 0x04
I2C_CMD_DISP_CUSTOM = 0x05
I2C_CMD_DISP_OFF = 0x06
# I2C_CMD_DISP_ASCII is not used
I2C_CMD_DISP_FLASH = 0x08
I2C_CMD_DISP_COLOR_BAR = 0x09
I2C_CMD_DISP_COLOR_WAVE = 0x0A
I2C_CMD_DISP_COLOR_CLOCKWISE = 0x0B
I2C_CMD_DISP_COLOR_ANIMATION = 0x0C
I2C_CMD_DISP_COLOR_BLOCK = 0x0D

I2C_CMD_STORE_FLASH = 0xA0
I2C_CMD_DELETE_FLASH = 0xA1

I2C_CMD_LED_ON = 0xB0
I2C_CMD_LED_OFF = 0xB1
I2C_CMD_AUTO_SLEEP_ON = 0xB2
I2C_CMD_AUTO_SLEEP_OFF = 0xB3

I2C_CMD_DISP_ROTATE = 0xB4
I2C_CMD_DISP_OFFSET = 0xB5

I2C_CMD_SET_ADDR = 0xC0
I2C_CMD_RST_ADDR = 0xC1

I2C_CMD_TEST_TX_RX_ON = 0xE0
I2C_CMD_TEST_TX_RX_OFF = 0xE1
I2C_CMD_TEST_GET_VER = 0xE2

I2C_CMD_GET_DEVICE_UID = 0xF1


class LEDMATRIX:
    def __init__(self, i2c, base_address=GROVE_TWO_RGB_LED_MATRIX_DEF_I2C_ADDR, offset_address=0):
        self.i2c = i2c
        self.base_address = base_address
        self.offset_address = offset_address
        self.current_device_address = base_address + offset_address

    def _i2c_send_byte(self, address, data):
        self.i2c.writeto(address, bytearray([data]))
    

    def _i2c_send_continue_bytes(self, address: int, data):
        """Send multiple bytes starting with a continue command."""
        cbytes = I2C_CMD_CONTINUE_DATA
        self.i2c.writeto(address, bytearray([cbytes] + data))

    def _i2c_send_bytes(self, address, data):
        self.i2c.writeto(address, bytearray(data))

    def _i2c_receive_bytes(self, address, length):
        return self.i2c.readfrom(address, length)

    def get_device_vid(self):
        self._i2c_send_byte(self.current_device_address, I2C_CMD_GET_DEV_ID)
        data = self._i2c_receive_bytes(self.current_device_address, 4)
        return data[0] + (data[1] << 8)

    def get_device_pid(self):
        self._i2c_send_byte(self.current_device_address, I2C_CMD_GET_DEV_ID)
        data = self._i2c_receive_bytes(self.current_device_address, 4)
        return data[2] + (data[3] << 8)

    def change_device_base_address(self, new_address):
        if not (0x10 <= new_address <= 0x70):
            new_address = GROVE_TWO_RGB_LED_MATRIX_DEF_I2C_ADDR

        data = [I2C_CMD_SET_ADDR, new_address]
        self._i2c_send_bytes(self.current_device_address, data)
        self.base_address = new_address
        self.current_device_address = self.base_address + self.offset_address
        time.time.sleep_ms(200)

    def device_address(self):
        self._i2c_send_byte(self.current_device_address, I2C_CMD_RST_ADDR)
        self.base_address = GROVE_TWO_RGB_LED_MATRIX_DEF_I2C_ADDR
        self.current_device_address = self.base_address + self.offset_address
        time.sleep_ms(200)

    def turn_on_led_flash(self):
        self._i2c_send_byte(self.current_device_address, I2C_CMD_LED_ON)

    def turn_off_led_flash(self):
        self._i2c_send_byte(self.current_device_address, I2C_CMD_LED_OFF)

    def enable_auto_sleep(self):
        self._i2c_send_byte(self.current_device_address, I2C_CMD_AUTO_SLEEP_ON)

    def wake_device(self):
        sleep_us(200)

    def disable_auto_sleep(self):
        self._i2c_send_byte(self.current_device_address, I2C_CMD_AUTO_SLEEP_OFF)

    def set_display_orientation(self, orientation):
        data = [I2C_CMD_DISP_ROTATE, orientation]
        self._i2c_send_bytes(self.current_device_address, data)

    def set_display_offset(self, offset_x, offset_y):
        offset_x = max(0, min(16, offset_x + 8))
        offset_y = max(0, min(16, offset_y + 8))
        data = [I2C_CMD_DISP_OFFSET, offset_x, offset_y]
        self._i2c_send_bytes(self.current_device_address, data)

    def display_bar(self, bar, duration_time, forever_flag, color):
        if bar > 32:
            bar = 32
        data = [I2C_CMD_DISP_BAR, bar, duration_time & 0xff, (duration_time >> 8) & 0xff, forever_flag, color]
        self._i2c_send_bytes(self.current_device_address, data)

    def display_emoji(self, emoji, duration_time, forever_flag):
        # * Description
        # *    Display emoji on LED matrix.
        # * Parameter
        # *    emoji: Set a number from 0 to 29 for different emoji.
        # *        0    smile        10    heart           20    house
        # *        1    laugh        11    small heart     21    tree
        # *        2    sad          12    broken heart    22    flower
        # *        3    mad          13    waterdrop       23    umbrella
        # *        4    angry        14    flame           24    rain
        # *        5    cry          15    creeper         25    monster
        # *        6    greedy       16    mad creeper     26    crab
        # *        7    cool         17    sword           27    duck
        # *        8    shy          18    wooden sword    28    rabbit
        # *        9    awkward      19    crystal sword   29    cat
        # *        30   up           31    down            32    left
        # *        33   right        34    smile face 3
        # *    duration_time: Set the display time(ms) duration. Set it to 0 to not display.
        # *    forever_flag: Set it to true to display forever, and the duration_time will not work.
        # *                  Or set it to false to display one time.
        
        data = [I2C_CMD_DISP_EMOJI, emoji, duration_time & 0xff, (duration_time >> 8) & 0xff, forever_flag]
        self._i2c_send_bytes(self.current_device_address, data)

    def display_number(self, number, duration_time, forever_flag, color):
        data = [I2C_CMD_DISP_NUM, number & 0xff, (number >> 8) & 0xff, duration_time & 0xff,
                (duration_time >> 8) & 0xff, forever_flag, color]
        self._i2c_send_bytes(self.current_device_address, data)
        
        
        

    def display_string(self, text, duration_time, forever_flag, color):
        text = text[:28]  # Max length is 28
        length = len(text)
        data = [I2C_CMD_DISP_STR, forever_flag, duration_time & 0xff, (duration_time >> 8) & 0xff, length, color] + \
               list(map(ord, text))
        if length > 25:
            self._i2c_send_bytes(self.current_device_address, data[:31])
            time.sleep_ms(1)
            self._i2c_send_bytes(self.current_device_address, data[31:])
        else:
            self._i2c_send_bytes(self.current_device_address, data)


    def display_frames(self, buffer, duration_time, forever_flag, frames_number):
        # * Description
        # *    Display user-defined frames on the LED matrix.
        # * Parameter
        # *    buffer: The data pointer. 1 frame needs 64 bytes of data.
        # *            Frames will switch automatically when the frames_number is larger than 1.
        # *            The shorter you set the duration_time, the faster it switches.
        # *    duration_time: Set the display time (ms) duration. Set it to 0 to not display.
        # *    forever_flag: Set it to True to display forever, or set it to False to display one time.
        # *    frames_number: The number of frames in your buffer. Range from 1 to 5.               
        
        
        if frames_number > 5:
            frames_number = 5
        if frames_number == 0:
            return
        
        data = [0x0]*72 # intialize an array of zeros 72 long
        data[0] = I2C_CMD_DISP_CUSTOM
        data[1] = 0x0
        data[2] = 0x0
        data[3] = 0x0
        data[4] = frames_number;
        
        for i in range(frames_number - 1, -1, -1):
            data[5] = i
            
            # Fill the frame data (reverse byte order for each 8x8 block if necessary)
            """This version is for 64 bit integer buffer"""
            for j in range(8):
                for k in range(7, -1, -1):
                    data[8 + j * 8 + (7 - k)] = buffer[j * 8 + k + i * 64]
            
#             """This version is for 8 bit integer buffer"""
#             for j in range(64):
#                     data[8 + j] = buffer[j + i * 64]

            # For the last frame, set the duration and forever_flag
            if i == 0:
                data[1] = duration_time & 0xff
                data[2] = (duration_time >> 8) & 0xff
                data[3] = forever_flag

            # Send first 24 bytes
            self._i2c_send_bytes(self.current_device_address, data[:24])
            time.sleep_ms(1)  # Small delay

            # Send next 24 bytes (from index 24 to 48)
            self._i2c_send_continue_bytes(self.current_device_address, data[24:48])
            time.sleep_ms(1)  # Small delay

            # Send last 24 bytes (from index 48 to 72)
            self._i2c_send_continue_bytes(self.current_device_address, data[48:72])
            time.sleep_ms(1)
               # Small delay
    '''
    def display_frames(self, buffer, duration_time, forever_flag, frames_number):
        if frames_number > 5:
            frames_number = 5
        if frames_number == 0:
            return
        for i in range(frames_number - 1, -1, -1):
            data = [I2C_CMD_DISP_CUSTOM, 0, 0, 0, frames_number, i] + buffer[i * 64: (i + 1) * 64]
            if i == 0:
                data[1] = duration_time & 0xff
                data[2] = (duration_time >> 8) & 0xff
                data[3] = forever_flag
            self._i2c_send_bytes(self.current_device_address, data[:24])
            time.sleep_ms(1)
            self._i2c_send_bytes(self.current_device_address, data[24:48])
            time.sleep_ms(1)
            self._i2c_send_bytes(self.current_device_address, data[48:72])
    '''
    def stop_display(self):
        self._i2c_send_byte(self.current_device_address, I2C_CMD_DISP_OFF)

    def store_frames(self):
        self._i2c_send_byte(self.current_device_address, I2C_CMD_STORE_FLASH)
        time.sleep_ms(200)


    def delete_frames(self):
        self._i2c_send_byte(self.current_device_address, I2C_CMD_DELETE_FLASH)
        time.sleep_ms(200)

    def display_frames_from_flash(self, duration_time, forever_flag):
        data = [I2C_CMD_DISP_FLASH, duration_time & 0xff, (duration_time >> 8) & 0xff, forever_flag]
        self._i2c_send_bytes(self.current_device_address, data)

    def display_color_block(self, color):
        data = [I2C_CMD_DISP_COLOR_BLOCK, color]
        self._i2c_send_bytes(self.current_device_address, data)

    def display_color_bar(self, duration_time, forever_flag):
        data = [I2C_CMD_DISP_COLOR_BAR, duration_time & 0xff, (duration_time >> 8) & 0xff, forever_flag]
        self._i2c_send_bytes(self.current_device_address, data)

    def display_color_wave(self, duration_time, forever_flag):
        data = [I2C_CMD_DISP_COLOR_WAVE, duration_time & 0xff, (duration_time >> 8) & 0xff, forever_flag]
        self._i2c_send_bytes(self.current_device_address, data)

    def display_clockwise(self, duration_time, forever_flag):
        data = [I2C_CMD_DISP_COLOR_CLOCKWISE, duration_time & 0xff, (duration_time >> 8) & 0xff, forever_flag]
        self._i2c_send_bytes(self.current_device_address, data)

    def display_color_animation(self, index, duration_time, forever_flag):
        
        if(index ==0):
            fro = 0
            to =28
        elif(index ==1):
            fro = 29
            to =41
        elif(index ==2):
            fro = 255
            to =255
        elif(index ==3):
            fro =254
            to =254
        elif(index ==4):
            fro = 42
            to =43
        elif(index ==5):
            fro = 44
            to =52
            
        data = [I2C_CMD_DISP_COLOR_ANIMATION, fro, to, duration_time & 0xff, (duration_time >> 8) & 0xff, forever_flag]
        self._i2c_send_bytes(self.current_device_address, data)
        
    
    def enable_test_mode(self):
        self._i2c_send_byte(self.current_device_address, I2C_CMD_TEST_TX_RX_ON)

    def disable_test_mode(self):
        self._i2c_send_byte(self.current_device_address, I2C_CMD_TEST_TX_RX_OFF)

    def get_test_version(self):
        self._i2c_send_byte(self.current_device_address, I2C_CMD_TEST_GET_VER)
        return self._i2c_receive_bytes(self.current_device_address, 3)

    def get_device_uid(self):
        self._i2c_send_byte(self.current_device_address, I2C_CMD_GET_DEVICE_UID)
        return self._i2c_receive_bytes(self.current_device_address, 4)


def apple(matrix):
    c = {
        'red': 0x00,
        'orange': 0x12,
        'yellow': 0x18,
        'green': 0x52,
        'cyan': 0x7f,
        'blue': 0xaa,
        'purple': 0xc3,
        'pink': 0xdc,
        'white': 0xfe,
        'black': 0xff,
    }

    apple_icon = [
        [c['cyan'], c['cyan'],  c['cyan'],  c['cyan'],  c['green'],  c['cyan'],  c['cyan'],  c['cyan']],
        [c['cyan'], c['cyan'],  c['cyan'],  c['green'],  c['black'],  c['cyan'],  c['cyan'],  c['cyan']],
        [c['cyan'], c['cyan'],  c['red'],   c['red'],    c['black'],    c['red'],   c['cyan'],  c['cyan']],
        [c['cyan'], c['red'],   c['red'],   c['red'],    c['red'],    c['red'],   c['red'],   c['cyan']],
        [c['cyan'], c['red'],   c['red'],   c['red'],    c['red'],    c['red'],   c['red'],   c['cyan']],
        [c['cyan'], c['red'],  c['red'],   c['red'],    c['red'],    c['red'],   c['red'],  c['cyan']],
        [c['cyan'], c['cyan'],  c['red'],  c['red'],    c['red'],    c['red'],  c['cyan'],  c['cyan']],
        [c['cyan'], c['cyan'],  c['cyan'],  c['cyan'],   c['cyan'],   c['cyan'],  c['cyan'],  c['cyan']],
    ]
    apple_icon_flattened = [pixel for row in apple_icon for pixel in row]
    buffer = apple_icon_flattened


    # Duration for each frame (e.g., 1000ms)
    duration_time = 1000

    ## NOTE DURATION does not work immediately following matrix.stop_display() or when first initialized
    ## Either call display_emoji or display_frames briefly first to fix the duration.


    # Whether the frames should loop forever (1 for true, 0 for false)
    forever_flag = 1 # frames displays repeating for the set duration until interrupted by another command

    # Number of frames in the buffer (1 for a single icon)
    frames_number = 1

    # Call display_frames to display the animation
    matrix.display_frames(buffer, duration_time, forever_flag, frames_number)
