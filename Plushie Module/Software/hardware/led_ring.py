"""
Educational Module System - LED Ring Interface
--------------------------------------------
This module provides an asynchronous interface for the 12 NeoPixel LED ring.
"""
import time
from machine import Pin
import neopixel
import uasyncio as asyncio

class AsyncLEDRing:
    """Asynchronous interface for the 12 NeoPixel LED ring"""
    
    # LED patterns
    SOLID = "SOLID"
    BLINK = "BLINK"
    BREATHE = "BREATHE"
    CHASE = "CHASE"
    RAINBOW = "RAINBOW"
    ALTERNATE = "ALTERNATE"
    RAINBOW_BLUE = "RAINBOW_BLUE"  # Blue-tinted rainbow for connection established
    
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
        
        self.tasks = {}  # Dictionary to store running tasks
    
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
    
    async def start_pattern(self, pattern, speed=5, duration_ms=1000):
        """Start a pattern as a background task.
        
        Args:
            pattern: Pattern to run
            speed: Pattern speed (1-10)
            duration_ms: Duration in milliseconds
            
        Returns:
            Task object that can be awaited
        """
        # Cancel any existing pattern
        self.cancel_pattern()
        
        # Set running flag
        self.running = True
        
        if pattern == self.BLINK:
            self.current_task = asyncio.create_task(self._blink_pattern(speed, duration_ms))
        elif pattern == self.BREATHE:
            self.current_task = asyncio.create_task(self._breathe_pattern(speed, duration_ms))
        elif pattern == self.CHASE:
            self.current_task = asyncio.create_task(self._chase_pattern(speed, duration_ms))
        elif pattern == self.RAINBOW:
            self.current_task = asyncio.create_task(self._rainbow_pattern(speed, duration_ms))
        elif pattern == self.ALTERNATE:
            self.current_task = asyncio.create_task(self._alternate_pattern(speed, duration_ms))
        elif pattern == self.SOLID:
            # Just set the solid color
            self.set_color(self.current_color)
        elif pattern == self.RAINBOW_BLUE:
            self.current_task = asyncio.create_task(self._rainbow_blue_pattern(speed, duration_ms))
        
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
        delay = 0.02 / (speed * 5) if speed > 0 else 0.02
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
        """Convert a position to an RGB color using the hue wheel.
        
        Args:
            pos: Position in the hue wheel (0-1)
            brightness: Brightness value (0-255)
            
        Returns:
            RGB tuple (r, g, b)
        """
        # Convert position to hue (0-360)
        hue = pos * 360
        
        # Convert hue to RGB
        r, g, b = self._hsv_to_rgb(hue / 360, 1.0, brightness / 255)
        
        return (r, g, b)
    
    def _hsv_to_rgb(self, h, s, v):
        """Convert HSV to RGB.
        
        Args:
            h: Hue (0-1)
            s: Saturation (0-1)
            v: Value (0-1)
            
        Returns:
            RGB tuple (r, g, b) with values 0-255
        """
        if s == 0.0:
            return (int(v * 255), int(v * 255), int(v * 255))
        
        i = int(h * 6.0)
        f = (h * 6.0) - i
        p = v * (1.0 - s)
        q = v * (1.0 - s * f)
        t = v * (1.0 - s * (1.0 - f))
        i = i % 6
        
        if i == 0:
            return (int(v * 255), int(t * 255), int(p * 255))
        elif i == 1:
            return (int(q * 255), int(v * 255), int(p * 255))
        elif i == 2:
            return (int(p * 255), int(v * 255), int(t * 255))
        elif i == 3:
            return (int(p * 255), int(q * 255), int(v * 255))
        elif i == 4:
            return (int(t * 255), int(p * 255), int(v * 255))
        else:
            return (int(v * 255), int(p * 255), int(q * 255))
    
    def _scale_color(self, color, brightness):
        """Scale RGB color by brightness value"""
        return tuple(int(c * brightness / 255) for c in color)

    def cancel_all_tasks(self):
        """Cancel all running LED tasks"""
        for task in self.tasks.values():
            try:
                task.cancel()
            except:
                pass
        self.tasks.clear()
        self.clear()  # Turn off all LEDs

    async def _rainbow_blue_pattern(self, speed, duration_ms):
        """Run a blue-tinted rainbow pattern.
        
        Args:
            speed: Pattern speed (1-10)
            duration_ms: Duration in milliseconds
        """
        start_time = time.ticks_ms()
        step = 0
        
        while self.running and time.ticks_diff(time.ticks_ms(), start_time) < duration_ms:
            for i in range(self.num_pixels):
                # Create a blue-tinted rainbow effect
                hue = (i * 360 / self.num_pixels + step) % 360
                # Adjust hue to favor blue tones
                if hue > 180:
                    hue = 180 + (hue - 180) * 0.5  # Compress red/yellow range
                
                # Get color with blue emphasis
                r, g, b = self._hsv_to_rgb(hue / 360, 1.0, 1.0)
                # Enhance blue component
                b = min(255, int(b * 1.5))
                
                self.pixels[i] = (r, g, b)
            
            self.pixels.write()
            step = (step + speed * 5) % 360
            await asyncio.sleep_ms(50)
        
        self.running = False 