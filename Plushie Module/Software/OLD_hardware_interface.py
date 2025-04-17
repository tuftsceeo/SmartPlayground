"""
Educational Module System - Asynchronous Hardware Interface
----------------------------------------------------------
This module provides an asyncio-based hardware interface for all components
on the ESP32-based educational modules, enabling concurrent operation.
"""
import time
import machine
from machine import Pin, PWM, SoftI2C
import neopixel
import gc
import uasyncio as asyncio

# I2C address and constants for the H3LIS331DL accelerometer
H3LIS331DL_DEFAULT_ADDRESS = 0x19

# H3LIS331DL Register Map
H3LIS331DL_REG_WHOAMI = 0x0F      # Who Am I Register
H3LIS331DL_REG_CTRL1 = 0x20       # Control Register-1
H3LIS331DL_REG_CTRL2 = 0x21       # Control Register-2
H3LIS331DL_REG_CTRL3 = 0x22       # Control Register-3
H3LIS331DL_REG_CTRL4 = 0x23       # Control Register-4
H3LIS331DL_REG_CTRL5 = 0x24       # Control Register-5
H3LIS331DL_REG_REFERENCE = 0x26   # Reference
H3LIS331DL_REG_STATUS = 0x27      # Status Register
H3LIS331DL_REG_OUT_X_L = 0x28     # X-Axis LSB
H3LIS331DL_REG_OUT_X_H = 0x29     # X-Axis MSB
H3LIS331DL_REG_OUT_Y_L = 0x2A     # Y-Axis LSB
H3LIS331DL_REG_OUT_Y_H = 0x2B     # Y-Axis MSB
H3LIS331DL_REG_OUT_Z_L = 0x2C     # Z-Axis LSB
H3LIS331DL_REG_OUT_Z_H = 0x2D     # Z-Axis MSB

# Accelerometer configuration constants
H3LIS331DL_ACCL_PM_PD = 0x00      # Power down Mode
H3LIS331DL_ACCL_PM_NRMl = 0x20    # Normal Mode
H3LIS331DL_ACCL_PM_0_5 = 0x40     # Low-Power Mode, ODR = 0.5Hz
H3LIS331DL_ACCL_PM_1 = 0x60       # Low-Power Mode, ODR = 1Hz
H3LIS331DL_ACCL_PM_2 = 0x80       # Low-Power Mode, ODR = 2Hz
H3LIS331DL_ACCL_PM_5 = 0xA0       # Low-Power Mode, ODR = 5Hz
H3LIS331DL_ACCL_PM_10 = 0xC0      # Low-Power Mode, ODR = 10Hz
H3LIS331DL_ACCL_DR_50 = 0x00      # ODR = 50Hz
H3LIS331DL_ACCL_DR_100 = 0x08     # ODR = 100Hz
H3LIS331DL_ACCL_DR_400 = 0x10     # ODR = 400Hz
H3LIS331DL_ACCL_DR_1000 = 0x18    # ODR = 1000Hz

# Axis configuration
H3LIS331DL_ACCL_LPEN = 0x00       # Normal Mode, Axis disabled
H3LIS331DL_ACCL_XAXIS = 0x04      # X-Axis enabled
H3LIS331DL_ACCL_YAXIS = 0x02      # Y-Axis enabled
H3LIS331DL_ACCL_ZAXIS = 0x01      # Z-Axis enabled

# Acceleration scale selection
H3LIS331DL_ACCL_BDU_CONT = 0x00      # Continuous update
H3LIS331DL_ACCL_BDU_NOT_CONT = 0x80  # Output registers not updated until MSB and LSB reading
H3LIS331DL_ACCL_BLE_MSB = 0x40       # MSB first
H3LIS331DL_ACCL_RANGE_400G = 0x30    # Full scale = +/-400g
H3LIS331DL_ACCL_RANGE_200G = 0x10    # Full scale = +/-200g
H3LIS331DL_ACCL_RANGE_100G = 0x00    # Full scale = +/-100g
H3LIS331DL_ACCL_SIM_3 = 0x01         # 3-Wire Interface
H3LIS331DL_RAW_DATA_MAX = 65536

# Default configuration
H3LIS331DL_DEFAULT_RANGE = H3LIS331DL_ACCL_RANGE_100G
H3LIS331DL_SCALE_FS = H3LIS331DL_RAW_DATA_MAX / 4 / ((H3LIS331DL_DEFAULT_RANGE >> 4) + 1)

class H3LIS331DL:
    """Interface for the H3LIS331DL 3-axis accelerometer"""
    
    def __init__(self, i2c, address=H3LIS331DL_DEFAULT_ADDRESS):
        """Initialize the accelerometer.
        
        Args:
            i2c: I2C interface
            address: I2C address of the accelerometer
        """
        self._addr = address
        self._i2c = i2c
        self.select_datarate()
        self.select_data_config()
    
    def _write_register(self, register, value):
        """Write a byte to the specified register"""
        self._i2c.writeto_mem(self._addr, register, bytes([value]))
    
    def _read_register(self, register):
        """Read a byte from the specified register"""
        return self._i2c.readfrom_mem(self._addr, register, 1)[0]
    
    def select_datarate(self):
        """Select the data rate of the accelerometer from the given provided values"""
        DATARATE_CONFIG = (H3LIS331DL_ACCL_PM_NRMl | H3LIS331DL_ACCL_DR_50 | 
                           H3LIS331DL_ACCL_XAXIS | H3LIS331DL_ACCL_YAXIS | H3LIS331DL_ACCL_ZAXIS)
        self._write_register(H3LIS331DL_REG_CTRL1, DATARATE_CONFIG)
    
    def select_data_config(self):
        """Select the data configuration of the accelerometer from the given provided values"""
        DATA_CONFIG = (H3LIS331DL_DEFAULT_RANGE | H3LIS331DL_ACCL_BDU_CONT)
        self._write_register(H3LIS331DL_REG_CTRL4, DATA_CONFIG)
    
    def read_accl(self):
        """Read data from accelerometer and return X, Y, Z acceleration values"""
        # Read X-axis data
        data0 = self._read_register(H3LIS331DL_REG_OUT_X_L)
        data1 = self._read_register(H3LIS331DL_REG_OUT_X_H)
        
        xAccl = data1 * 256 + data0
        if xAccl > H3LIS331DL_RAW_DATA_MAX / 2:
            xAccl -= H3LIS331DL_RAW_DATA_MAX
        
        # Read Y-axis data
        data0 = self._read_register(H3LIS331DL_REG_OUT_Y_L)
        data1 = self._read_register(H3LIS331DL_REG_OUT_Y_H)
        
        yAccl = data1 * 256 + data0
        if yAccl > H3LIS331DL_RAW_DATA_MAX / 2:
            yAccl -= H3LIS331DL_RAW_DATA_MAX
        
        # Read Z-axis data
        data0 = self._read_register(H3LIS331DL_REG_OUT_Z_L)
        data1 = self._read_register(H3LIS331DL_REG_OUT_Z_H)
        
        zAccl = data1 * 256 + data0
        if zAccl > H3LIS331DL_RAW_DATA_MAX / 2:
            zAccl -= H3LIS331DL_RAW_DATA_MAX
        
        return {'x': xAccl, 'y': yAccl, 'z': zAccl}
    
    def read_g(self):
        """Read accelerometer values in g units"""
        accl = self.read_accl()
        return {
            'x': accl['x'] / H3LIS331DL_SCALE_FS,
            'y': accl['y'] / H3LIS331DL_SCALE_FS,
            'z': accl['z'] / H3LIS331DL_SCALE_FS
        }

class AsyncLEDRing:
    """Asynchronous interface for the 12 NeoPixel LED ring"""
    
    # LED patterns
    PATTERN_SOLID = "SOLID"
    PATTERN_BLINK = "BLINK"
    PATTERN_BREATHE = "BREATHE"
    PATTERN_CHASE = "CHASE"
    PATTERN_RAINBOW = "RAINBOW"
    PATTERN_ALTERNATE = "ALTERNATE"
    
    def __init__(self, pin_num=20, num_pixels=12):
        """Initialize the LED ring.
        
        Args:
            pin_num: GPIO pin connected to the LED data line
            num_pixels: Number of LEDs in the ring
        """
        self.num_pixels = num_pixels
        self.pixels = neopixel.NeoPixel(Pin(pin_num), num_pixels)
        self.current_color = (0, 0, 0)
        self.current_brightness = 255
        
        # Task management
        self.current_task = None
        self.running = False
        
        # Clear LEDs initially
        self.clear()
    
    def clear(self):
        """Turn off all LEDs"""
        for i in range(self.num_pixels):
            self.pixels[i] = (0, 0, 0)
        self.pixels.write()
    
    def set_color(self, color):
        """Set all LEDs to a specific color.
        
        Args:
            color: RGB tuple (0-255, 0-255, 0-255)
        """
        self.current_color = color
        scaled_color = self._scale_color(color, self.current_brightness)
        
        # Cancel any running pattern
        self.cancel_pattern()
        
        for i in range(self.num_pixels):
            self.pixels[i] = scaled_color
        self.pixels.write()
    
    def set_brightness(self, brightness):
        """Set the overall brightness.
        
        Args:
            brightness: Brightness level (0-255)
        """
        self.current_brightness = max(0, min(255, brightness))
        scaled_color = self._scale_color(self.current_color, self.current_brightness)
        for i in range(self.num_pixels):
            self.pixels[i] = scaled_color
        self.pixels.write()
    
    def set_count(self, count):
        """Illuminate a specific number of LEDs.
        
        Args:
            count: Number of LEDs to illuminate (0-12)
        """
        count = max(0, min(self.num_pixels, count))
        scaled_color = self._scale_color(self.current_color, self.current_brightness)
        
        # Cancel any running pattern
        self.cancel_pattern()
        
        for i in range(self.num_pixels):
            if i < count:
                self.pixels[i] = scaled_color
            else:
                self.pixels[i] = (0, 0, 0)
        self.pixels.write()
    
    def cancel_pattern(self):
        """Cancel any running pattern"""
        self.running = False
        if self.current_task:
            try:
                self.current_task.cancel()
            except:
                pass
            self.current_task = None
    
    def start_pattern(self, pattern, speed=5, duration_ms=1000):
        """Start a pattern as a background task.
        
        Args:
            pattern: One of the PATTERN_* constants
            speed: Animation speed (1-10)
            duration_ms: Duration in ms
            
        Returns:
            The running task
        """
        # Cancel any existing pattern
        self.cancel_pattern()
        
        # Create new pattern task
        self.running = True
        
        if pattern == self.PATTERN_BLINK:
            self.current_task = asyncio.create_task(self._blink_pattern(speed, duration_ms))
        elif pattern == self.PATTERN_BREATHE:
            self.current_task = asyncio.create_task(self._breathe_pattern(speed, duration_ms))
        elif pattern == self.PATTERN_CHASE:
            self.current_task = asyncio.create_task(self._chase_pattern(speed, duration_ms))
        elif pattern == self.PATTERN_RAINBOW:
            self.current_task = asyncio.create_task(self._rainbow_pattern(speed, duration_ms))
        elif pattern == self.PATTERN_ALTERNATE:
            self.current_task = asyncio.create_task(self._alternate_pattern(speed, duration_ms))
        elif pattern == self.PATTERN_SOLID:
            # Just set the solid color
            self.set_color(self.current_color)
            self.current_task = None
        
        return self.current_task
    
    async def _blink_pattern(self, speed, duration_ms):
        """Run the blink pattern.
        
        Args:
            speed: Animation speed (1-10)
            duration_ms: Duration in ms
        """
        delay = 0.1 / (speed / 5) if speed > 0 else 0.1
        start_time = time.ticks_ms()
        max_duration = duration_ms / 1000  # Convert to seconds
        
        original_color = self.current_color
        
        try:
            while self.running and (time.ticks_diff(time.ticks_ms(), start_time) / 1000) < max_duration:
                # On
                for i in range(self.num_pixels):
                    self.pixels[i] = self._scale_color(original_color, self.current_brightness)
                self.pixels.write()
                await asyncio.sleep(delay)
                
                # Off
                for i in range(self.num_pixels):
                    self.pixels[i] = (0, 0, 0)
                self.pixels.write()
                await asyncio.sleep(delay * 5)
        
        finally:
            # Reset to original color if still running
            if self.running:
                for i in range(self.num_pixels):
                    self.pixels[i] = self._scale_color(original_color, self.current_brightness)
                self.pixels.write()
            self.running = False
    
    async def _breathe_pattern(self, speed, duration_ms):
        """Run the breathe pattern.
        
        Args:
            speed: Animation speed (1-10)
            duration_ms: Duration in ms
        """
        delay = 0.01 / (speed / 5) if speed > 0 else 0.01
        start_time = time.ticks_ms()
        max_duration = duration_ms / 1000  # Convert to seconds
        
        original_color = self.current_color
        original_brightness = self.current_brightness
        
        try:
            while self.running and (time.ticks_diff(time.ticks_ms(), start_time) / 1000) < max_duration:
                steps = 20
                for step in range(steps * 2):
                    if not self.running:
                        break
                        
                    if step < steps:
                        brightness = int(step * 255 / steps)  # 0-255
                    else:
                        brightness = int((2 * steps - step) * 255 / steps)  # 255-0
                    
                    brightness = max(0, min(255, int(brightness * original_brightness / 255)))
                    
                    # Apply brightness without changing stored brightness
                    for i in range(self.num_pixels):
                        self.pixels[i] = self._scale_color(original_color, brightness)
                    self.pixels.write()
                    
                    await asyncio.sleep(delay)
        
        finally:
            # Reset to original color and brightness if still running
            if self.running:
                for i in range(self.num_pixels):
                    self.pixels[i] = self._scale_color(original_color, original_brightness)
                self.pixels.write()
            self.running = False
    
    async def _chase_pattern(self, speed, duration_ms):
        """Run the chase pattern.
        
        Args:
            speed: Animation speed (1-10)
            duration_ms: Duration in ms
        """
        delay = 0.1 / (speed / 5) if speed > 0 else 0.1
        start_time = time.ticks_ms()
        max_duration = duration_ms / 1000  # Convert to seconds
        
        original_color = self.current_color
        
        try:
            while self.running and (time.ticks_diff(time.ticks_ms(), start_time) / 1000) < max_duration:
                for i in range(self.num_pixels):
                    if not self.running:
                        break
                        
                    # Clear
                    for j in range(self.num_pixels):
                        self.pixels[j] = (0, 0, 0)
                    
                    # Set active pixel
                    self.pixels[i] = self._scale_color(original_color, self.current_brightness)
                    self.pixels.write()
                    
                    await asyncio.sleep(delay)
        
        finally:
            # Reset to original color if still running
            if self.running:
                for i in range(self.num_pixels):
                    self.pixels[i] = self._scale_color(original_color, self.current_brightness)
                self.pixels.write()
            self.running = False
    
    async def _rainbow_pattern(self, speed, duration_ms):
        """Run the rainbow pattern.
        
        Args:
            speed: Animation speed (1-10)
            duration_ms: Duration in ms
        """
        delay = 0.02 / (speed / 5) if speed > 0 else 0.02
        start_time = time.ticks_ms()
        max_duration = duration_ms / 1000  # Convert to seconds
        
        original_color = self.current_color
        brightness_scale = max(1, int(self.current_brightness / 25.5))
        
        try:
            while self.running and (time.ticks_diff(time.ticks_ms(), start_time) / 1000) < max_duration:
                for j in range(256):
                    if not self.running:
                        break
                        
                    for i in range(self.num_pixels):
                        pixel_index = (i * 256 // self.num_pixels) + j
                        self.pixels[i] = self._hue(pixel_index & 255, brightness_scale)
                    self.pixels.write()
                    
                    await asyncio.sleep(delay)
        
        finally:
            # Reset to original color if still running
            if self.running:
                for i in range(self.num_pixels):
                    self.pixels[i] = self._scale_color(original_color, self.current_brightness)
                self.pixels.write()
            self.running = False
    
    async def _alternate_pattern(self, speed, duration_ms):
        """Run the alternate pattern.
        
        Args:
            speed: Animation speed (1-10)
            duration_ms: Duration in ms
        """
        delay = 0.1 / (speed / 5) if speed > 0 else 0.1
        start_time = time.ticks_ms()
        max_duration = duration_ms / 1000  # Convert to seconds
        
        original_color = self.current_color
        
        try:
            while self.running and (time.ticks_diff(time.ticks_ms(), start_time) / 1000) < max_duration:
                for state in range(2):
                    if not self.running:
                        break
                        
                    # Set alternate pixels
                    for i in range(self.num_pixels):
                        if i % 2 == state:
                            self.pixels[i] = self._scale_color(original_color, self.current_brightness)
                        else:
                            self.pixels[i] = (0, 0, 0)
                    self.pixels.write()
                    
                    await asyncio.sleep(delay * 5)
        
        finally:
            # Reset to original color if still running
            if self.running:
                for i in range(self.num_pixels):
                    self.pixels[i] = self._scale_color(original_color, self.current_brightness)
                self.pixels.write()
            self.running = False
    
    async def demo_pattern(self):
        """Run a demonstration pattern similar to lightDemo() in original code"""
        self.cancel_pattern()
        self.running = True
        
        try:
            for j in range(2):  # Original does 2 cycles
                if not self.running:
                    break
                    
                for i in range(12):  # One full rotation
                    if not self.running:
                        break
                        
                    self.pixels[i % 12] = (255, 0, 0)  # Red
                    self.pixels[(i + 1) % 12] = (0, 255, 0)  # Green
                    self.pixels.write()
                    await asyncio.sleep(0.1)  # Add a slight delay between updates
        
        finally:
            self.running = False
    
    def _hue(self, pos, brightness=10):
        """Generate RGB color across 0-255 positions.
        
        Args:
            pos: Position in the color wheel (0-255)
            brightness: Brightness scale (1-10)
            
        Returns:
            RGB color tuple
        """
        bright_scale = brightness / 10
        
        if pos < 85:
            return (int((255 - pos * 3) * bright_scale), 
                    int((pos * 3) * bright_scale), 
                    0)  # Red to green
        elif pos < 170:
            pos -= 85
            return (0, 
                    int((255 - pos * 3) * bright_scale), 
                    int((pos * 3) * bright_scale))  # Green to blue
        else:
            pos -= 170
            return (int((pos * 3) * bright_scale), 
                    0, 
                    int((255 - pos * 3) * bright_scale))  # Blue to red
    
    def _scale_color(self, color, brightness):
        """Scale RGB color by brightness value"""
        return tuple(int(c * brightness / 255) for c in color)

class Button:
    """Interface for the tactile button"""
    
    def __init__(self, pin_num=0):
        """Initialize the button.
        
        Args:
            pin_num: GPIO pin connected to the button
        """
        self.pin = Pin(pin_num, Pin.IN)
        self.press_time = 0
        self.last_state = True  # Pull-up, so True is not pressed
        self.debounce_time = 20  # ms
        self.last_debounce = 0
        self.press_count = 0
        self.press_count_time = 0
        self.double_tap_window = 500  # ms
        
        # Set up callback for button events
        self.callbacks = {
            "press": [],
            "release": [],
            "hold": [],
            "double_tap": []
        }
        
        # Set up interrupt for button events
        self.pin.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, 
                    handler=self._button_callback)
    
    def _button_callback(self, pin):
        """IRQ handler for button events"""
        current_time = time.ticks_ms()
        
        # Debounce
        if time.ticks_diff(current_time, self.last_debounce) < self.debounce_time:
            return
        
        self.last_debounce = current_time
        state = self.pin.value()
        
        # State changed
        if state != self.last_state:
            self.last_state = state
            
            # Button pressed (False with pull-up)
            if state == False:
                self.press_time = current_time
                self._trigger_callbacks("press")
                
                # Check for double tap
                if time.ticks_diff(current_time, self.press_count_time) < self.double_tap_window:
                    self.press_count += 1
                    if self.press_count == 2:
                        self._trigger_callbacks("double_tap")
                        self.press_count = 0
                else:
                    self.press_count = 1
                    self.press_count_time = current_time
                    
            # Button released (True with pull-up)
            else:
                hold_duration = time.ticks_diff(current_time, self.press_time)
                self._trigger_callbacks("release", hold_duration)
                if hold_duration > 500:  # Hold threshold
                    self._trigger_callbacks("hold", hold_duration)
    
    def add_callback(self, event_type, callback):
        """Add a callback for button events.
        
        Args:
            event_type: One of "press", "release", "hold", "double_tap"
            callback: Function to call when event occurs
        """
        if event_type in self.callbacks:
            self.callbacks[event_type].append(callback)
    
    def remove_callback(self, event_type, callback):
        """Remove a callback for button events."""
        if event_type in self.callbacks and callback in self.callbacks[event_type]:
            self.callbacks[event_type].remove(callback)
    
    def _trigger_callbacks(self, event_type, *args):
        """Trigger all callbacks for a given event type"""
        for callback in self.callbacks[event_type]:
            callback(*args)
            
    def is_pressed(self):
        """Return True if button is currently pressed"""
        return not self.pin.value()  # Inverted due to pull-up

class AsyncBuzzer:
    """Asynchronous interface for the buzzer (sound output)"""
    
    # Note frequency mapping (in Hz)
    NOTES = {
        "C4": 262,
        "D4": 294,
        "E4": 330,
        "F4": 349,
        "G4": 392,
        "A4": 440,
        "B4": 494,
        "C5": 523
    }
    
    # Buzzer patterns
    PATTERN_SINGLE = "SINGLE"
    PATTERN_DOUBLE = "DOUBLE"
    PATTERN_TRIPLE = "TRIPLE"
    PATTERN_ASCENDING = "ASCENDING"
    PATTERN_DESCENDING = "DESCENDING"
    PATTERN_SOS = "SOS"
    
    def __init__(self, pin_num=19):
        """Initialize the buzzer.
        
        Args:
            pin_num: GPIO pin connected to the buzzer
        """
        self.pwm = PWM(Pin(pin_num, Pin.OUT), freq=1000, duty=0)
        self.volume = 50  # Default volume (0-100)
        
        # Task management
        self.current_task = None
        self.running = False
    
    def set_volume(self, volume):
        """Set buzzer volume.
        
        Args:
            volume: Volume level (0-100)
        """
        self.volume = max(0, min(100, volume))
    
    def stop(self):
        """Stop buzzer"""
        self.pwm.duty(0)
        self.cancel_sound()
    
    def cancel_sound(self):
        """Cancel any running sound pattern"""
        self.running = False
        if self.current_task:
            try:
                self.current_task.cancel()
            except:
                pass
            self.current_task = None
    
    def play_tone(self, frequency, duration_ms=0):
        """Play a tone immediately (non-async version).
        
        Args:
            frequency: Tone frequency in Hz
            duration_ms: Duration in milliseconds (0 for continuous)
        """
        # Cancel any running sound
        self.cancel_sound()
        
        # Convert volume to PWM duty cycle (0-1023)
        duty = int(400 * self.volume / 100)
        
        self.pwm.freq(int(frequency))
        self.pwm.duty(duty)
        
        # If duration is specified, create a task to stop after duration
        if duration_ms > 0:
            self.current_task = asyncio.create_task(self._auto_stop(duration_ms / 1000))
    
    async def _auto_stop(self, delay):
        """Auto-stop the sound after a delay.
        
        Args:
            delay: Delay in seconds
        """
        await asyncio.sleep(delay)
        self.pwm.duty(0)
    
    def start_tone(self, frequency, duration_ms=500):
        """Start playing a tone as a background task.
        
        Args:
            frequency: Tone frequency in Hz
            duration_ms: Duration in milliseconds
            
        Returns:
            The running task
        """
        # Cancel any existing sound
        self.cancel_sound()
        
        # Create new sound task
        self.running = True
        self.current_task = asyncio.create_task(self._play_tone(frequency, duration_ms))
        return self.current_task
    
    async def _play_tone(self, frequency, duration_ms):
        """Asynchronously play a tone.
        
        Args:
            frequency: Tone frequency in Hz
            duration_ms: Duration in milliseconds
        """
        # Convert volume to PWM duty cycle (0-1023)
        duty = int(400 * self.volume / 100)
        
        try:
            # Set frequency and duty cycle
            self.pwm.freq(int(frequency))
            self.pwm.duty(duty)
            
            # Wait for the specified duration
            await asyncio.sleep(duration_ms / 1000)
        
        finally:
            # Only turn off the buzzer if we're still running
            if self.running:
                self.pwm.duty(0)
            self.running = False
    
    def start_note(self, note_name, duration_ms=500):
        """Start playing a musical note as a background task.
        
        Args:
            note_name: Note name (e.g., "C4", "D4", etc.)
            duration_ms: Duration in milliseconds
            
        Returns:
            The running task or None if note not found
        """
        if note_name in self.NOTES:
            return self.start_tone(self.NOTES[note_name], duration_ms)
        return None
    
    def start_pattern(self, pattern_type, base_frequency=440):
        """Start playing a pattern as a background task.
        
        Args:
            pattern_type: One of the PATTERN_* constants
            base_frequency: Base frequency for patterns
            
        Returns:
            The running task
        """
        # Cancel any existing sound
        self.cancel_sound()
        
        # Create new pattern task
        self.running = True
        
        if pattern_type == self.PATTERN_SINGLE:
            self.current_task = asyncio.create_task(self._single_pattern(base_frequency))
        elif pattern_type == self.PATTERN_DOUBLE:
            self.current_task = asyncio.create_task(self._double_pattern(base_frequency))
        elif pattern_type == self.PATTERN_TRIPLE:
            self.current_task = asyncio.create_task(self._triple_pattern(base_frequency))
        elif pattern_type == self.PATTERN_ASCENDING:
            self.current_task = asyncio.create_task(self._ascending_pattern())
        elif pattern_type == self.PATTERN_DESCENDING:
            self.current_task = asyncio.create_task(self._descending_pattern())
        elif pattern_type == self.PATTERN_SOS:
            self.current_task = asyncio.create_task(self._sos_pattern(base_frequency))
        
        # Return the task for proper awaiting
        return self.current_task
    
    async def _single_pattern(self, frequency):
        """Play a single tone pattern.
        
        Args:
            frequency: Tone frequency in Hz
        """
        try:
            await self._play_tone(frequency, 300)
        except asyncio.CancelledError:
            # Handle cancellation properly
            self.running = False
            raise
        finally:
            # Only set running to False if we're not being cancelled
            if self.running:
                self.running = False
    
    async def _double_pattern(self, frequency):
        """Play a double tone pattern.
        
        Args:
            frequency: Tone frequency in Hz
        """
        try:
            if self.running:
                await self._play_tone(frequency, 200)
            if self.running:
                await asyncio.sleep(0.1)
            if self.running:
                await self._play_tone(frequency, 200)
        except asyncio.CancelledError:
            # Handle cancellation properly
            self.running = False
            raise
        finally:
            # Only set running to False if we're not being cancelled
            if self.running:
                self.running = False
    
    async def _triple_pattern(self, frequency):
        """Play a triple tone pattern.
        
        Args:
            frequency: Tone frequency in Hz
        """
        try:
            for _ in range(3):
                if not self.running:
                    break
                await self._play_tone(frequency, 200)
                if self.running:
                    await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            # Handle cancellation properly
            self.running = False
            raise
        finally:
            # Only set running to False if we're not being cancelled
            if self.running:
                self.running = False
    
    async def _ascending_pattern(self):
        """Play an ascending scale pattern."""
        try:
            notes = ["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"]
            for note in notes:
                if not self.running:
                    break
                # Play each note for a longer duration
                await self._play_tone(self.NOTES[note], 300)
                # Add a small delay between notes
                if self.running:
                    await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            # Handle cancellation properly
            self.running = False
            raise
        finally:
            # Only set running to False if we're not being cancelled
            if self.running:
                self.running = False
    
    async def _descending_pattern(self):
        """Play a descending scale pattern."""
        try:
            notes = ["C5", "B4", "A4", "G4", "F4", "E4", "D4", "C4"]
            for note in notes:
                if not self.running:
                    break
                await self._play_tone(self.NOTES[note], 200)
                # Add a small delay between notes
                if self.running and note != notes[-1]:  # Don't delay after the last note
                    await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            # Handle cancellation properly
            self.running = False
            raise
        finally:
            # Only set running to False if we're not being cancelled
            if self.running:
                self.running = False
    
    async def _sos_pattern(self, frequency):
        """Play an SOS pattern.
        
        Args:
            frequency: Tone frequency in Hz
        """
        try:
            # Three short
            for _ in range(3):
                if not self.running:
                    break
                await self._play_tone(frequency, 200)
                if self.running:
                    await asyncio.sleep(0.1)
            
            if self.running:
                await asyncio.sleep(0.3)
            
            # Three long
            for _ in range(3):
                if not self.running:
                    break
                await self._play_tone(frequency, 500)
                if self.running:
                    await asyncio.sleep(0.1)
            
            if self.running:
                await asyncio.sleep(0.3)
            
            # Three short
            for _ in range(3):
                if not self.running:
                    break
                await self._play_tone(frequency, 200)
                if self.running:
                    await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            # Handle cancellation properly
            self.running = False
            raise
        finally:
            # Only set running to False if we're not being cancelled
            if self.running:
                self.running = False
    
    async def play_demo(self):
        """Play a demonstration phone ring melody"""
        self.cancel_sound()
        self.running = True
        
        try:
            tones = [
                (659.26, 150),  # E5
                (587.33, 150),  # D5
                (369.99, 300),  # F#4
                (415.3, 300),   # G#4
                (554.37, 150),  # C#5
                (493.88, 150),  # B4
                (293.66, 300),  # D4
                (329.63, 300),  # E4
                (493.88, 150),  # B4
                (440, 150),     # A4
                (277.18, 300),  # C#4
                (329.62, 300),  # E4
                (440, 600)      # A4
            ]
            
            for freq, duration in tones:
                if not self.running:
                    break
                # Play each tone with a small pause between notes
                await self._play_tone(freq, duration)
                if self.running and freq != tones[-1][0]:  # Don't pause after the last note
                    await asyncio.sleep(0.05)
        
        finally:
            self.running = False

class Vibration:
    """Interface for the vibration motor"""
    
    # Vibration patterns
    PATTERN_CONTINUOUS = "CONTINUOUS"
    PATTERN_PULSE = "PULSE"
    PATTERN_DOUBLE = "DOUBLE"
    PATTERN_TRIPLE = "TRIPLE"
    PATTERN_LONG_SHORT = "LONG_SHORT"
    
    def __init__(self, pin_num=21):
        """Initialize the vibration motor.
        
        Args:
            pin_num: GPIO pin connected to the vibration motor
        """
        self.pin = Pin(pin_num, Pin.OUT)
        self.pin.off()  # Ensure vibration motor is off
        
        # Task management
        self.current_task = None
        self.running = False
    
    def cancel_vibration(self):
        """Cancel any running vibration pattern"""
        self.running = False
        self.pin.off()  # Ensure motor is off
        
        if self.current_task:
            try:
                self.current_task.cancel()
            except:
                pass
            self.current_task = None
    
    def start_vibration(self, duration_ms=500):
        """Start vibration as a background task.
        
        Args:
            duration_ms: Duration in milliseconds
            
        Returns:
            The running task
        """
        # Cancel any existing vibration
        self.cancel_vibration()
        
        # Create new vibration task
        self.running = True
        self.current_task = asyncio.create_task(self._vibrate(duration_ms))
        return self.current_task
    
    async def _vibrate(self, duration_ms):
        """Asynchronously vibrate for a duration.
        
        Args:
            duration_ms: Duration in milliseconds
        """
        try:
            self.pin.on()
            await asyncio.sleep(duration_ms / 1000)
        finally:
            self.pin.off()
            self.running = False
    
    def start_pattern(self, pattern_type, repeat=1):
        """Start a vibration pattern as a background task.
        
        Args:
            pattern_type: One of the PATTERN_* constants
            repeat: Number of times to repeat pattern
            
        Returns:
            The running task
        """
        # Cancel any existing vibration
        self.cancel_vibration()
        
        # Create new pattern task
        self.running = True
        
        if pattern_type == self.PATTERN_CONTINUOUS:
            self.current_task = asyncio.create_task(self._continuous_pattern())
        elif pattern_type == self.PATTERN_PULSE:
            self.current_task = asyncio.create_task(self._pulse_pattern(repeat))
        elif pattern_type == self.PATTERN_DOUBLE:
            self.current_task = asyncio.create_task(self._double_pattern(repeat))
        elif pattern_type == self.PATTERN_TRIPLE:
            self.current_task = asyncio.create_task(self._triple_pattern(repeat))
        elif pattern_type == self.PATTERN_LONG_SHORT:
            self.current_task = asyncio.create_task(self._long_short_pattern(repeat))
        
        return self.current_task
    
    async def _continuous_pattern(self):
        """Run a continuous vibration pattern."""
        try:
            self.pin.on()
            await asyncio.sleep(0.5)
        finally:
            self.pin.off()
            self.running = False
    
    async def _pulse_pattern(self, repeat):
        """Run a pulse vibration pattern.
        
        Args:
            repeat: Number of times to repeat
        """
        try:
            for _ in range(repeat):
                if not self.running:
                    break
                    
                self.pin.on()
                await asyncio.sleep(0.2)
                self.pin.off()
                await asyncio.sleep(0.2)
        finally:
            self.pin.off()
            self.running = False
    
    async def _double_pattern(self, repeat):
        """Run a double pulse vibration pattern.
        
        Args:
            repeat: Number of times to repeat
        """
        try:
            for _ in range(repeat):
                if not self.running:
                    break
                    
                self.pin.on()
                await asyncio.sleep(0.1)
                self.pin.off()
                await asyncio.sleep(0.1)
                self.pin.on()
                await asyncio.sleep(0.1)
                self.pin.off()
                await asyncio.sleep(0.3)
        finally:
            self.pin.off()
            self.running = False
    
    async def _triple_pattern(self, repeat):
        """Run a triple pulse vibration pattern.
        
        Args:
            repeat: Number of times to repeat
        """
        try:
            for _ in range(repeat):
                if not self.running:
                    break
                    
                for _ in range(3):
                    if not self.running:
                        break
                        
                    self.pin.on()
                    await asyncio.sleep(0.1)
                    self.pin.off()
                    await asyncio.sleep(0.1)
                
                await asyncio.sleep(0.3)
        finally:
            self.pin.off()
            self.running = False
    
    async def _long_short_pattern(self, repeat):
        """Run a long-short vibration pattern.
        
        Args:
            repeat: Number of times to repeat
        """
        try:
            for _ in range(repeat):
                if not self.running:
                    break
                    
                self.pin.on()
                await asyncio.sleep(0.4)
                self.pin.off()
                await asyncio.sleep(0.1)
                self.pin.on()
                await asyncio.sleep(0.1)
                self.pin.off()
                await asyncio.sleep(0.3)
        finally:
            self.pin.off()
            self.running = False

class Accelerometer:
    """Interface for the 3-axis accelerometer"""
    
    # Orientation constants
    ORIENTATION_UP = "UP"
    ORIENTATION_DOWN = "DOWN"
    ORIENTATION_LEFT = "LEFT"
    ORIENTATION_RIGHT = "RIGHT"
    ORIENTATION_FRONT = "FRONT"
    ORIENTATION_BACK = "BACK"
    
    def __init__(self, scl_pin=23, sda_pin=22):
        """Initialize the accelerometer.
        
        Args:
            scl_pin: I2C SCL pin
            sda_pin: I2C SDA pin
        """
        self.i2c = SoftI2C(scl=Pin(scl_pin), sda=Pin(sda_pin))
        
        # Check available I2C devices
        devices = self.i2c.scan()
        self.available = H3LIS331DL_DEFAULT_ADDRESS in devices
        
        if self.available:
            self.sensor = H3LIS331DL(self.i2c)
            # Initialize with default configuration
            self.sensor.select_datarate()
            self.sensor.select_data_config()
            
            # Data for shake detection
            self.last_reading = {'x': 0, 'y': 0, 'z': 0}
            self.shake_threshold = 0.5  # g units
            self.movement_threshold = 0.1  # g units
        else:
            print("H3LIS331DL accelerometer not found!")
    
    def read_raw(self):
        """Read raw accelerometer values"""
        if not self.available:
            return {'x': 0, 'y': 0, 'z': 0}
        
        return self.sensor.read_accl()
    
    def read_g(self):
        """Read accelerometer values in g units"""
        if not self.available:
            return {'x': 0, 'y': 0, 'z': 0}
        
        return self.sensor.read_g()
    
    def get_orientation(self):
        """Determine the current orientation"""
        if not self.available:
            return self.ORIENTATION_UP
        
        accel = self.read_g()
        x, y, z = accel['x'], accel['y'], accel['z']
        
        # Simple orientation detection based on dominant axis
        if z > 0.7:
            return self.ORIENTATION_UP
        elif z < -0.7:
            return self.ORIENTATION_DOWN
        elif x > 0.7:
            return self.ORIENTATION_RIGHT
        elif x < -0.7:
            return self.ORIENTATION_LEFT
        elif y > 0.7:
            return self.ORIENTATION_FRONT
        elif y < -0.7:
            return self.ORIENTATION_BACK
        else:
            return self.ORIENTATION_UP  # Default if no orientation is dominant
    
    def get_tilt_angles(self):
        """Get tilt angles in degrees for each axis"""
        if not self.available:
            return (0, 0, 0)
        
        accel = self.read_g()
        x, y, z = accel['x'], accel['y'], accel['z']
        
        # Convert g values to angles in degrees
        import math
        angle_x = math.atan2(x, math.sqrt(y*y + z*z)) * 180 / math.pi
        angle_y = math.atan2(y, math.sqrt(x*x + z*z)) * 180 / math.pi
        angle_z = math.atan2(z, math.sqrt(x*x + y*y)) * 180 / math.pi
        
        return (angle_x, angle_y, angle_z)
    
    def detect_shake(self):
        """Detect shaking and return shake intensity (0-100)"""
        if not self.available:
            return 0
        
        current = self.read_g()
        last = self.last_reading
        
        # Calculate movement magnitude across all axes
        delta_sq = (current['x'] - last['x'])**2 + (current['y'] - last['y'])**2 + (current['z'] - last['z'])**2
        
        self.last_reading = current
        
        # Scale to 0-100 intensity range
        if delta_sq < self.movement_threshold:
            return 0
        
        intensity = min(100, int(delta_sq * 100 / self.shake_threshold))
        return intensity
    
    def detect_movement(self):
        """Detect general movement and return intensity (0-100)"""
        if not self.available:
            return 0
        
        current = self.read_g()
        last = self.last_reading
        
        # Calculate movement magnitude across all axes
        delta_sq = (current['x'] - last['x'])**2 + (current['y'] - last['y'])**2 + (current['z'] - last['z'])**2
        
        self.last_reading = current
        
        # Scale to 0-100 intensity range with lower threshold than shake
        intensity = min(100, int(delta_sq * 100 / self.movement_threshold))
        return intensity

class PowerManagement:
    """Power management for the hardware interface"""
    
    def __init__(self, battery_pin=34, button_pin=0):
        """Initialize power management.
        
        Args:
            battery_pin: ADC pin for battery voltage monitoring
            button_pin: Pin for wake-up button
        """
        self.battery_adc = None
        if hasattr(machine, 'ADC'):
            try:
                self.battery_adc = machine.ADC(Pin(battery_pin))
                # Configure ADC (if needed)
                if hasattr(self.battery_adc, 'atten'):
                    self.battery_adc.atten(machine.ADC.ATTN_11DB)  # Full range
            except:
                self.battery_adc = None
        
        self.last_activity = time.ticks_ms()
        self.light_sleep_timer = machine.Timer(-1)
        self.deep_sleep_timer = machine.Timer(-1)
        
        self.light_sleep_threshold_ms = 2 * 60 * 1000  # 2 minutes
        self.deep_sleep_threshold_ms = 10 * 60 * 1000  # 10 minutes
        
        self.button_pin = button_pin
        
        # Start sleep timers
        self._reset_timers()
    
    def _reset_timers(self):
        """Reset sleep timers"""
        self.last_activity = time.ticks_ms()
        
        # Stop existing timers
        self.light_sleep_timer.deinit()
        self.deep_sleep_timer.deinit()
        
        # Start new timers
        self.light_sleep_timer.init(
            period=self.light_sleep_threshold_ms, 
            mode=machine.Timer.ONE_SHOT,
            callback=self._enter_light_sleep
        )
        
        self.deep_sleep_timer.init(
            period=self.deep_sleep_threshold_ms, 
            mode=machine.Timer.ONE_SHOT,
            callback=self._enter_deep_sleep
        )
    
    def _enter_light_sleep(self, timer):
        """Enter light sleep mode"""
        print("Entering light sleep mode")
        # Implementation would reduce sensor polling, etc.
    
    def _enter_deep_sleep(self, timer):
        """Enter deep sleep mode"""
        print("Entering deep sleep mode")
        # Save state if needed
        # Configure wake sources
        if hasattr(machine, 'wake_on_ext0'):
            machine.wake_on_ext0(Pin(self.button_pin, Pin.IN), 0)  # Wake on button press
        
        # Clear garbage before sleep
        gc.collect()
        
        # Enter deep sleep
        if hasattr(machine, 'deepsleep'):
            machine.deepsleep()
    
    def register_activity(self):
        """Register user activity to reset sleep timers"""
        self._reset_timers()
    
    def get_battery_voltage(self):
        """Get battery voltage"""
        if self.battery_adc is None:
            return 3.8  # Default if ADC not available
        
        # Read ADC value
        try:
            adc_value = self.battery_adc.read()
            
            # Convert to voltage (adjust for your specific battery monitor circuit)
            voltage = adc_value * 3.3 / 4095  # Assuming 12-bit ADC
            
            # If using voltage divider, adjust calculation
            # voltage = adc_value * 6.6 / 4095 for a 1:1 divider
            
            return voltage
        except:
            return 3.8  # Default if reading fails
    
    def get_battery_percentage(self):
        """Get battery percentage (0-100)"""
        voltage = self.get_battery_voltage()
        
        # Adjust these thresholds based on your battery
        min_voltage = 3.2  # Battery minimum safe voltage
        max_voltage = 4.2  # Battery maximum voltage
        
        # Calculate percentage
        percentage = (voltage - min_voltage) / (max_voltage - min_voltage) * 100
        percentage = max(0, min(100, percentage))
        
        return int(percentage)
    
    def get_battery_state(self):
        """Get battery state (LOW, MEDIUM, HIGH)"""
        percentage = self.get_battery_percentage()
        
        if percentage < 20:
            return "LOW"
        elif percentage < 50:
            return "MEDIUM"
        else:
            return "HIGH"

class AsyncHardware:
    """Asynchronous hardware interface class that integrates all components"""
    
    def __init__(self):
        """Initialize all hardware components"""
        print("Initializing async hardware components...")
        
        self.led_ring = AsyncLEDRing()
        self.button = Button()
        self.accelerometer = Accelerometer()
        self.vibration = Vibration()
        self.buzzer = AsyncBuzzer()
        self.power = PowerManagement()
        
        # Register button activity for power management
        self.button.add_callback("press", lambda: self.power.register_activity())
        
        print("Async hardware initialization complete")
    
    async def setup_activity_detection(self):
        """Set up activity detection for power management"""
        while True:
            # Check accelerometer for movement
            if self.accelerometer.detect_movement() > 10:
                self.power.register_activity()
            
            await asyncio.sleep(1)
    
    async def demo_all(self):
        """Run a demo of all hardware components asynchronously"""
        print("Starting async hardware demo...")
        
        # Start LED rainbow pattern
        led_task = self.led_ring.start_pattern(self.led_ring.PATTERN_RAINBOW, 5, 10000)
        
        # Play demo sound after a short delay
        await asyncio.sleep(0.5)
        sound_task = asyncio.create_task(self.buzzer.play_demo())
        
        # Vibrate after another short delay
        await asyncio.sleep(1)
        vib_task = self.vibration.start_vibration(200)
        
        # Show accelerometer readings
        if self.accelerometer.available:
            print("Accelerometer readings:")
            for i in range(5):
                accel_g = self.accelerometer.read_g()
                print("X: {:.3f}g, Y: {:.3f}g, Z: {:.3f}g".format(
                    accel_g['x'], accel_g['y'], accel_g['z']))
                await asyncio.sleep(0.2)
        
        # Wait for all tasks to complete
        await asyncio.gather(led_task, sound_task, vib_task)
        
        print("Async hardware demo complete")
