"""
Educational Module System - Hardware Interface
-------------------------------------------
This module provides a unified interface for all hardware components.
"""
import uasyncio as asyncio
from .accelerometer import Accelerometer
from .led_ring import AsyncLEDRing
from .button import Button
from .buzzer import Buzzer
from .vibration import Vibration
from .power_management import PowerManagement

class HardwareInterface:
    """Unified interface for all hardware components
    
    This class provides a simplified interface to all hardware components
    in the Educational Module System. It handles initialization, cleanup,
    and provides convenience methods for common operations.
    """
    
    # Common colors for UI indicators
    RED = (255, 0, 0)
    GREEN = (0, 255, 0)
    BLUE = (0, 0, 255)
    YELLOW = (255, 255, 0)
    PURPLE = (128, 0, 128)
    WHITE = (255, 255, 255)
    OFF = (0, 0, 0)
    
    def __init__(self):
        """Initialize all hardware components"""
        # Initialize accelerometer
        self.accelerometer = Accelerometer()
        
        # Initialize LED ring
        self.led_ring = AsyncLEDRing(pin_num=20)
        
        # Initialize button
        self.button = Button(pin_num=0)
        
        # Initialize buzzer
        self.buzzer = Buzzer(pin_num=19)
        
        # Initialize vibration motor
        self.vibration = Vibration(pin_num=21)
        
        # Initialize power management
        self.power = PowerManagement(button_pin=17)  # Using same pin as button for wake-up
    
    def cleanup(self):
        """Clean up all hardware components"""
        # Stop any running tasks
        self.led_ring.cancel_all_tasks()
        self.buzzer.cancel_all()
        self.vibration.cancel_vibration()
        
        # Turn off outputs
        self.led_ring.clear()
        self.buzzer.stop()
        self.vibration.cancel_vibration()
    
    # Convenience methods for LED ring
    def set_led_color(self, color):
        """Set all LEDs to a specific color."""
        self.led_ring.set_color(color)
    
    def set_led_brightness(self, brightness):
        """Set LED brightness."""
        self.led_ring.set_brightness(brightness)
    
    def set_led_count(self, count):
        """Set number of active LEDs."""
        self.led_ring.set_count(count)
    
    def start_led_pattern(self, pattern, speed=5, duration_ms=1000):
        """Start an LED pattern."""
        return self.led_ring.start_pattern(pattern, speed, duration_ms)
    
    # Convenience methods for buzzer
    def play_note(self, note_name, duration_ms=500):
        """Play a musical note."""
        return self.buzzer.play_note(note_name, duration_ms)
    
    def play_frequency(self, frequency, duration_ms=500):
        """Play a specific frequency."""
        return self.buzzer.play_frequency(frequency, duration_ms)
    
    def set_volume(self, volume):
        """Set buzzer volume."""
        self.buzzer.set_volume(volume)
    
    def start_buzzer_pattern(self, pattern, base_frequency=440):
        """Start a buzzer pattern."""
        return self.buzzer.play_pattern(pattern, base_frequency)
    
    # Convenience methods for vibration
    def vibrate(self, duration_ms=500):
        """Start vibration."""
        return self.vibration.start_vibration(duration_ms)
    
    def start_vibration_pattern(self, pattern, repeat=1):
        """Start a vibration pattern."""
        return self.vibration.start_pattern(pattern, repeat)
    
    # Convenience methods for button
    def add_button_callback(self, event_type, callback):
        """Add a button callback."""
        self.button.add_callback(event_type, callback)
    
    def remove_button_callback(self, event_type, callback):
        """Remove a button callback."""
        self.button.remove_callback(event_type, callback)
    
    # Convenience methods for accelerometer
    def get_orientation(self):
        """Get current orientation."""
        return self.accelerometer.get_orientation()
    
    def get_tilt_angles(self):
        """Get tilt angles."""
        return self.accelerometer.get_tilt_angles()
    
    def detect_shake(self):
        """Detect if device is being shaken."""
        return self.accelerometer.detect_shake()
    
    def detect_movement(self):
        """Detect if device is moving."""
        return self.accelerometer.detect_movement()
    
    # Convenience methods for power management
    def register_activity(self):
        """Register activity to reset sleep timers."""
        self.power.register_activity()
    
    # UI Indicator methods
    def show_confirmation(self):
        """Show a confirmation indicator (green pulsing light, ascending ding, short vibration).
        
        This indicator is designed for 5-year-olds and their teachers to indicate
        a successful action or completion of a task.
        
        Returns:
            List of task objects that can be awaited
        """
        # Cancel any existing patterns
        self.led_ring.cancel_pattern()
        self.buzzer.cancel_all()
        self.vibration.cancel_vibration()
        self.set_led_color((255, 0, 0)) 
        
        # Create tasks for the indicator
        led_task = self.led_ring.start_pattern(self.led_ring.BREATHE, speed=3, duration_ms=2000)
        buzzer_task = self.buzzer.play_pattern(self.buzzer.DING)
        vib_task = self.vibration.start_pattern(self.vibration.CONFIRM, repeat=1)
        
        return [led_task, buzzer_task, vib_task]
    
    def show_error(self):
        """Show an error indicator (red blinking light, descending error tone, double vibration).
        
        This indicator is designed for 5-year-olds and their teachers to indicate
        an error or failed action.
        
        Returns:
            List of task objects that can be awaited
        """
        # Cancel any existing patterns
        self.led_ring.cancel_pattern()
        self.buzzer.cancel_all()
        self.vibration.cancel_vibration()
        self.set_led_color((255, 0, 0)) 
        # Create tasks for the indicator
        led_task = self.led_ring.start_pattern(self.led_ring.BLINK, speed=5, duration_ms=2000)
        buzzer_task = self.buzzer.play_pattern(self.buzzer.ERROR)
        vib_task = self.vibration.start_pattern(self.vibration.ERROR, repeat=1)
        
        return [led_task, buzzer_task, vib_task]
    
    def show_information(self):
        """Show an information indicator (yellow pulsing light, medium tone, single vibration).
        
        This indicator is designed for 5-year-olds and their teachers to indicate
        information or a warning.
        
        Returns:
            List of task objects that can be awaited
        """
        # Cancel any existing patterns
        self.led_ring.cancel_pattern()
        self.buzzer.cancel_all()
        self.vibration.cancel_vibration()
        self.set_led_color((255, 255, 0)) 
        
        # Create tasks for the indicator
        led_task = self.led_ring.start_pattern(self.led_ring.BREATHE, speed=4, duration_ms=2000)
        buzzer_task = self.buzzer.play_pattern(self.buzzer.INFO)
        vib_task = self.vibration.start_pattern(self.vibration.INFO, repeat=1)
        
        return [led_task, buzzer_task, vib_task]
    
    def show_connecting(self):
        """Show a connecting indicator (blue chasing light, ascending/descending tones, continuous pulsing).
        
        This indicator is designed for 5-year-olds and their teachers to indicate
        that the device is searching or connecting.
        
        Returns:
            List of task objects that can be awaited
        """
        # Cancel any existing patterns
        self.led_ring.cancel_pattern()
        self.buzzer.cancel_all()
        self.vibration.cancel_vibration()
        self.set_led_color((0, 0, 255)) 
        
        # Create tasks for the indicator
        led_task = self.led_ring.start_pattern(self.led_ring.CHASE, speed=3, duration_ms=5000)
        buzzer_task = self.buzzer.play_pattern(self.buzzer.CONNECTING)
        vib_task = self.vibration.start_pattern(self.vibration.CONNECTING, repeat=0)  # Repeat indefinitely
        
        return [led_task, buzzer_task, vib_task]
    
    def show_connection_established(self):
        """Show a connection established indicator (blue rainbow, connection melody, triple pulse).
        
        This indicator is designed for 5-year-olds and their teachers to indicate
        that a connection has been established.
        
        Returns:
            List of task objects that can be awaited
        """
        # Cancel any existing patterns
        self.led_ring.cancel_pattern()
        self.buzzer.cancel_all()
        self.vibration.cancel_vibration()
        self.set_led_color((0, 0, 255)) 
        
        # Create tasks for the indicator
        led_task = self.led_ring.start_pattern(self.led_ring.RAINBOW_BLUE, speed=4, duration_ms=3000)
        buzzer_task = self.buzzer.play_pattern(self.buzzer.CONNECTED)
        vib_task = self.vibration.start_pattern(self.vibration.CONNECTED, repeat=1)
        
        return [led_task, buzzer_task, vib_task]
    
    def show_attention(self):
        """Show an attention indicator (multi-color alternating, attention melody, long-short vibration).
        
        This indicator is designed for 5-year-olds and their teachers to indicate
        that attention is needed.
        
        Returns:
            List of task objects that can be awaited
        """
        # Cancel any existing patterns
        self.led_ring.cancel_pattern()
        self.buzzer.cancel_all()
        self.vibration.cancel_vibration()
        self.set_led_color((255, 255, 0)) 
        # Create tasks for the indicator
        led_task = self.led_ring.start_pattern(self.led_ring.ALTERNATE, speed=5, duration_ms=3000)
        buzzer_task = self.buzzer.play_pattern(self.buzzer.ATTENTION)
        vib_task = self.vibration.start_pattern(self.vibration.ATTENTION, repeat=1)
        
        return [led_task, buzzer_task, vib_task]
    
    def show_calm(self):
        """Show a calm indicator (soft blue breathing light, gentle descending tone, no vibration).
        
        This indicator is designed for 5-year-olds and their teachers to indicate
        that the device is ready or in a calm state.
        
        Returns:
            List of task objects that can be awaited
        """
        # Cancel any existing patterns
        self.led_ring.cancel_pattern()
        self.buzzer.cancel_all()
        self.vibration.cancel_vibration()
        self.set_led_color((0, 0, 255)) 
        # Create tasks for the indicator
        led_task = self.led_ring.start_pattern(self.led_ring.BREATHE, speed=2, duration_ms=3000)
        buzzer_task = self.buzzer.play_pattern(self.buzzer.CALM)
        
        return [led_task, buzzer_task]
    
    def show_celebration(self):
        """Show a celebration indicator (rainbow pattern, celebratory melody, triple pulse).
        
        This indicator is designed for 5-year-olds and their teachers to indicate
        an achievement or celebration.
        
        Returns:
            List of task objects that can be awaited
        """
        # Cancel any existing patterns
        self.led_ring.cancel_pattern()
        self.buzzer.cancel_all()
        self.vibration.cancel_vibration()
                
        # Create tasks for the indicator
        led_task = self.led_ring.start_pattern(self.led_ring.RAINBOW, speed=5, duration_ms=3000)
        buzzer_task = self.buzzer.play_pattern(self.buzzer.CELEBRATION)
        vib_task = self.vibration.start_pattern(self.vibration.CELEBRATION, repeat=1)
        
        return [led_task, buzzer_task, vib_task]
    
    def show_sleep(self):
        """Show a sleep indicator (dimming light, soft descending tone, gentle pulse).
        
        This indicator is designed for 5-year-olds and their teachers to indicate
        that the device is going to sleep or shutting down.
        
        Returns:
            List of task objects that can be awaited
        """
        # Cancel any existing patterns
        self.led_ring.cancel_pattern()
        self.buzzer.cancel_all()
        self.vibration.cancel_vibration()
        self.set_led_color((0, 128, 255)) 
        # Create tasks for the indicator
        buzzer_task = self.buzzer.play_pattern(self.buzzer.SLEEP)
        vib_task = self.vibration.start_pattern(self.vibration.SLEEP, repeat=1)
        
        # Create a task for dimming the light
        async def dim_light():
            # Start with current brightness
            brightness = self.led_ring.current_brightness
            steps = 20
            for i in range(steps):
                new_brightness = int(brightness * (1 - i / steps))
                self.led_ring.set_brightness(new_brightness)
                await asyncio.sleep_ms(100)
            self.led_ring.clear()
        
        led_task = asyncio.create_task(dim_light())
        
        return [led_task, buzzer_task, vib_task]
    
    def show_help(self):
        """Show a help indicator (purple pulsing light, friendly alternating notes, double gentle pulse).
        
        This indicator is designed for 5-year-olds and their teachers to indicate
        that help is available.
        
        Returns:
            List of task objects that can be awaited
        """
        # Cancel any existing patterns
        self.led_ring.cancel_pattern()
        self.buzzer.cancel_all()
        self.vibration.cancel_vibration()
        self.set_led_color((128, 0, 255)) 
        # Create tasks for the indicator
        led_task = self.led_ring.start_pattern(self.led_ring.BREATHE, speed=3, duration_ms=3000)
        buzzer_task = self.buzzer.play_pattern(self.buzzer.HELP)
        vib_task = self.vibration.start_pattern(self.vibration.HELP, repeat=1)
        
        return [led_task, buzzer_task, vib_task] 