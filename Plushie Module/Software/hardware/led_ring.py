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
        self.current_count = self.num_pixels
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
        self._update_pixels()
    
    def set_brightness(self, brightness):
        """Set the overall brightness.
        
        Args:
            brightness: Brightness level (0-255)
        """
        self.current_brightness = max(0, min(255, brightness))
        self._update_pixels()
    
    def set_count(self, count):
        """Illuminate a specific number of LEDs.
        
        Args:
            count: Number of LEDs to illuminate (0-12)
        """
        self.current_count = max(0, min(self.num_pixels, count))
        self._update_pixels()
        
        
      
    
    def _update_pixels(self):
          # Cancel any running pattern
        scaled_color = self._scale_color(self.current_color, self.current_brightness)
        self.cancel_pattern()
        
        for i in range(self.num_pixels):
            if i < self.current_count:
                self.pixels[i] = scaled_color
            else:
                self.pixels[i] = (0, 0, 0)
        self.pixels.write()
    
    def cancel_pattern(self):
        """Cancel any running pattern"""
        print("DEBUG: cancel_pattern - Setting running to False")
        self.running = False
        if self.current_task:
            self.current_task.cancel()
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
        print(f"DEBUG: start_pattern - Setting running to True for pattern {pattern}, duration_ms={duration_ms}")
        self.running = True
        
        # Create the appropriate pattern task
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
            # Create a dummy task that completes immediately
            self.current_task = asyncio.create_task(self._dummy_task(duration_ms))
        elif pattern == self.RAINBOW_BLUE:
            self.current_task = asyncio.create_task(self._rainbow_blue_pattern(speed, duration_ms))
        
        return self.current_task
    
    async def _dummy_task(self, duration_ms):
        """A dummy task that just sleeps for the specified duration.
        
        This is used for patterns that don't need animation but should still
        run for a specific duration.
        
        Args:
            duration_ms: Duration in milliseconds
        """
        print(f"DEBUG: _dummy_task - Starting with duration_ms={duration_ms}")
        await asyncio.sleep_ms(duration_ms)
        print("DEBUG: _dummy_task - Setting running to False")
        self.running = False
    
    async def _blink_pattern(self, speed, duration_ms):
        """Run the blink pattern.
        
        Args:
            speed: Animation speed (1-10)
            duration_ms: Duration in ms
        """
        print(f"DEBUG: _blink_pattern - Starting with speed={speed}, duration_ms={duration_ms}")
        delay = 1 / (speed) if speed > 0 else 2
        start_time = time.ticks_ms()
        max_duration = duration_ms  # Keep in milliseconds
        
        original_color = self.current_color
        
        while self.running and time.ticks_diff(time.ticks_ms(), start_time) < max_duration:
            # On
            for i in range(self.num_pixels):
                self.pixels[i] = self._scale_color(original_color, self.current_brightness)
            self.pixels.write()
            await asyncio.sleep(delay)
            
            # Off
            for i in range(self.num_pixels):
                self.pixels[i] = (0, 0, 0)
            self.pixels.write()
            await asyncio.sleep(delay)
        
        # Reset to original color if still running
        if self.running:
            for i in range(self.num_pixels):
                self.pixels[i] = self._scale_color(original_color, self.current_brightness)
            self.pixels.write()
        print("DEBUG: _blink_pattern - Setting running to False")
        self.running = False
    
    async def _breathe_pattern(self, speed, duration_ms):
        """Run the breathe pattern.
        
        Args:
            speed: Animation speed (1-10)
            duration_ms: Duration in ms
        """
        print(f"DEBUG: _breathe_pattern - Starting with speed={speed}, duration_ms={duration_ms}")
        delay = 1 / (speed) if speed > 0 else 2
        start_time = time.ticks_ms()
        max_duration = duration_ms  # Keep in milliseconds
        
        original_color = self.current_color
        original_brightness = self.current_brightness
        
        while self.running and time.ticks_diff(time.ticks_ms(), start_time) < max_duration:
            steps = 20
            for step in range(steps * 2):
                if not self.running:
                    print("DEBUG: _breathe_pattern - break at step", step)
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
        
        # Reset to original color and brightness if still running
        if self.running:
            for i in range(self.num_pixels):
                self.pixels[i] = self._scale_color(original_color, original_brightness)
            self.pixels.write()
        print("DEBUG: _breathe_pattern - Setting running to False")
        self.running = False
    
    async def _chase_pattern(self, speed, duration_ms):
        """Run the chase pattern.
        
        Args:
            speed: Animation speed (1-10)
            duration_ms: Duration in ms
        """
        print(f"DEBUG: _chase_pattern - Starting with speed={speed}, duration_ms={duration_ms}")
        delay = 1 / (speed) if speed > 0 else 2
        start_time = time.ticks_ms()
        max_duration = duration_ms  # Keep in milliseconds
        
        original_color = self.current_color
        
        while self.running and time.ticks_diff(time.ticks_ms(), start_time) < max_duration:
            for i in range(self.num_pixels):
                if not self.running:
                    print("DEBUG: _chase_pattern - break at step", step)
                    break
                    
                # Clear
                for j in range(self.num_pixels):
                    self.pixels[j] = (0, 0, 0)
                
                # Set active pixel
                self.pixels[i] = self._scale_color(original_color, self.current_brightness)
                self.pixels.write()
                
                await asyncio.sleep(delay)
        
        # Reset to original color if still running
        if self.running:
            for i in range(self.num_pixels):
                self.pixels[i] = self._scale_color(original_color, self.current_brightness)
            self.pixels.write()
        print("DEBUG: _chase_pattern - Setting running to False")
        self.running = False
    
    async def _rainbow_pattern(self, speed, duration_ms):
        """Run the rainbow pattern.
        
        Args:
            speed: Animation speed (1-10) (this must be faster because the rainbow animation is slow)
            duration_ms: Duration in ms
        """
        print(f"DEBUG: _rainbow_pattern - Starting with speed={speed}, duration_ms={duration_ms}")
        delay = 0.01 / (speed) if speed > 0 else 0.01
        start_time = time.ticks_ms()
        max_duration = duration_ms  # Keep in milliseconds
        
        while self.running and time.ticks_diff(time.ticks_ms(), start_time) < max_duration:
            for i in range(self.num_pixels):
                if not self.running:
                    print("DEBUG: _rainbow_pattern - break at step", step)

                    break
                
                # Calculate hue based on position and time
                hue = (i * 360 / self.num_pixels) % 360
                self.pixels[i] = self._hue(hue, self.current_brightness)
                if i == 0:
                    print("pixel 1", self._hue(hue, self.current_brightness))
            
            self.pixels.write()
            await asyncio.sleep(delay)
        
        # Clear LEDs if still running
        if self.running:
            self.clear()
        print("DEBUG: _rainbow_pattern - Setting running to False")
        self.running = False
    
    async def _alternate_pattern(self, speed, duration_ms):
        """Run the alternate pattern.
        
        Args:
            speed: Animation speed (1-10)
            duration_ms: Duration in ms
        """
        print(f"DEBUG: _alternate_pattern - Starting with speed={speed}, duration_ms={duration_ms}")
        delay = 1 / (speed) if speed > 0 else 2
        start_time = time.ticks_ms()
        max_duration = duration_ms  # Keep in milliseconds
        
        original_color = self.current_color
        
        while self.running and time.ticks_diff(time.ticks_ms(), start_time) < max_duration:
            # Even LEDs on
            for i in range(0, self.num_pixels, 2):
                self.pixels[i] = self._scale_color(original_color, self.current_brightness)
            for i in range(1, self.num_pixels, 2):
                self.pixels[i] = (0, 0, 0)
            self.pixels.write()
            await asyncio.sleep(delay)
            
            # Odd LEDs on
            for i in range(0, self.num_pixels, 2):
                self.pixels[i] = (0, 0, 0)
            for i in range(1, self.num_pixels, 2):
                self.pixels[i] = self._scale_color(original_color, self.current_brightness)
            self.pixels.write()
            await asyncio.sleep(delay)
        
        # Reset to original color if still running
        if self.running:
            for i in range(self.num_pixels):
                self.pixels[i] = self._scale_color(original_color, self.current_brightness)
            self.pixels.write()
        print("DEBUG: _alternate_pattern - Setting running to False")
        self.running = False
    
    async def _rainbow_blue_pattern(self, speed, duration_ms):
        """Run the blue-tinted rainbow pattern.
        
        Args:
            speed: Animation speed (1-10)
            duration_ms: Duration in ms
        """
        print(f"DEBUG: _rainbow_blue_pattern - Starting with speed={speed}, duration_ms={duration_ms}")
        delay = 0.01 / (speed) if speed > 0 else 0.01
        start_time = time.ticks_ms()
        max_duration = duration_ms  # Keep in milliseconds
        
        while self.running and time.ticks_diff(time.ticks_ms(), start_time) < max_duration:
            for i in range(self.num_pixels):
                if not self.running:
                    print("DEBUG: _rainbow_blue_pattern - break at step", step)
                    break
                
                # Calculate hue based on position and time, with blue tint
                hue = (i * 360 / self.num_pixels + 240) % 360  # Start at blue (240)
                self.pixels[i] = self._hue(hue, self.current_brightness)
            
            self.pixels.write()
            await asyncio.sleep(delay)
        
        # Clear LEDs if still running
        if self.running:
            self.clear()
        print("DEBUG: _rainbow_blue_pattern - Setting running to False")
        self.running = False
    
    def _hue(self, pos, brightness=10):
        """Convert a position in the hue wheel to an RGB color.
        
        Args:
            pos: Position in the hue wheel (0-360)
            brightness: Brightness level (0-255)
            
        Returns:
            RGB tuple (0-255, 0-255, 0-255)
        """
        return self._hsv_to_rgb(pos / 360, 1.0, brightness / 255)
    
    def _hsv_to_rgb(self, h, s, v):
        """Convert HSV color values to RGB.
        
        Args:
            h: Hue (0-1)
            s: Saturation (0-1)
            v: Value/Brightness (0-1)
            
        Returns:
            RGB tuple (0-255, 0-255, 0-255)
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
        """Scale a color by brightness.
        
        Args:
            color: RGB tuple (0-255, 0-255, 0-255)
            brightness: Brightness level (0-255)
            
        Returns:
            Scaled RGB tuple
        """
        return (
            int(color[0] * brightness / 255),
            int(color[1] * brightness / 255),
            int(color[2] * brightness / 255)
        )
    
    def cancel_all_tasks(self):
        """Cancel all running tasks"""
        self.cancel_pattern() 