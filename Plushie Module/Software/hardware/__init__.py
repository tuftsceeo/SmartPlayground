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
    
    Example:
        hardware = HardwareInterface()
        
        # Set LED color
        hardware.set_led_color((255, 0, 0))  # Red
        
        # Play a note
        hardware.play_note("C4", 500)  # Play C4 for 500ms
        
        # Vibrate
        hardware.vibrate(1000)  # Vibrate for 1 second
        
        # Clean up when done
        hardware.cleanup()
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
        """Set all LEDs to a specific color.
        
        Args:
            color: RGB tuple (r, g, b) with values 0-255
        """
        self.led_ring.set_color(color)
    
    def set_led_brightness(self, brightness):
        """Set LED brightness.
        
        Args:
            brightness: Value from 0-255
        """
        self.led_ring.set_brightness(brightness)
    
    def set_led_count(self, count):
        """Set number of active LEDs.
        
        Args:
            count: Number of LEDs to activate (0-12)
        """
        self.led_ring.set_count(count)
    
    def start_led_pattern(self, pattern, speed=5, duration_ms=1000):
        """Start an LED pattern.
        
        Args:
            pattern: Pattern to run (e.g., hardware.led_ring.BREATHE)
            speed: Pattern speed (1-10)
            duration_ms: Duration in milliseconds
            
        Returns:
            Task object that can be awaited
        """
        return self.led_ring.start_pattern(pattern, speed, duration_ms)
    
    # Convenience methods for buzzer
    def play_note(self, note_name, duration_ms=500):
        """Play a musical note.
        
        Args:
            note_name: Note name (e.g., "C4", "A4")
            duration_ms: Duration in milliseconds
            
        Returns:
            Task object that can be awaited
        """
        return self.buzzer.play_note(note_name, duration_ms)
    
    def play_frequency(self, frequency, duration_ms=500):
        """Play a specific frequency.
        
        Args:
            frequency: Frequency in Hz
            duration_ms: Duration in milliseconds
            
        Returns:
            Task object that can be awaited
        """
        return self.buzzer.play_frequency(frequency, duration_ms)
    
    def set_volume(self, volume):
        """Set buzzer volume.
        
        Args:
            volume: Volume level (0-100)
        """
        self.buzzer.set_volume(volume)
    
    def start_buzzer_pattern(self, pattern, base_frequency=440):
        """Start a buzzer pattern.
        
        Args:
            pattern: Pattern to run (e.g., hardware.buzzer.ASCENDING)
            base_frequency: Base frequency in Hz
            
        Returns:
            Task object that can be awaited
        """
        return self.buzzer.play_pattern(pattern, base_frequency)
    
    # Convenience methods for vibration
    def vibrate(self, duration_ms=500):
        """Start vibration.
        
        Args:
            duration_ms: Duration in milliseconds
            
        Returns:
            Task object that can be awaited
        """
        return self.vibration.start_vibration(duration_ms)
    
    def start_vibration_pattern(self, pattern, repeat=1):
        """Start a vibration pattern.
        
        Args:
            pattern: Pattern to run (e.g., hardware.vibration.PULSE)
            repeat: Number of times to repeat the pattern
            
        Returns:
            Task object that can be awaited
        """
        return self.vibration.start_pattern(pattern, repeat)
    
    # Convenience methods for button
    def add_button_callback(self, event_type, callback):
        """Add a button callback.
        
        Args:
            event_type: Event type ("press", "release", "hold", "double_tap")
            callback: Function to call when event occurs
        """
        self.button.add_callback(event_type, callback)
    
    def remove_button_callback(self, event_type, callback):
        """Remove a button callback.
        
        Args:
            event_type: Event type ("press", "release", "hold", "double_tap")
            callback: Function to remove
        """
        self.button.remove_callback(event_type, callback)
    
    # Convenience methods for accelerometer
    def get_orientation(self):
        """Get current orientation.
        
        Returns:
            String describing orientation ("flat", "upright", "upside_down", "left", "right")
        """
        return self.accelerometer.get_orientation()
    
    def get_tilt_angles(self):
        """Get tilt angles.
        
        Returns:
            Tuple of (x_angle, y_angle, z_angle) in degrees
        """
        return self.accelerometer.get_tilt_angles()
    
    def detect_shake(self):
        """Detect if device is being shaken.
        
        Returns:
            Shake intensity (0-100)
        """
        return self.accelerometer.detect_shake()
    
    def detect_movement(self):
        """Detect if device is moving.
        
        Returns:
            Movement intensity (0-100)
        """
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
        tasks = []
        self.set_led_color(self.GREEN)
        tasks.append(self.start_led_pattern(self.led_ring.BREATHE, speed=5, duration_ms=1000))
        tasks.append(self.start_buzzer_pattern(self.buzzer.DING))
        tasks.append(self.start_vibration_pattern(self.vibration.CONFIRM))
        return tasks
    
    def show_error(self):
        """Show an error indicator (red blinking light, descending error tone, double vibration).
        
        This indicator is designed for 5-year-olds and their teachers to indicate
        something went wrong or an incorrect action.
        
        Returns:
            List of task objects that can be awaited
        """
        tasks = []
        self.set_led_color(self.RED)
        tasks.append(self.start_led_pattern(self.led_ring.ALTERNATE, speed=8, duration_ms=1000))
        tasks.append(self.start_buzzer_pattern(self.buzzer.ERROR))
        tasks.append(self.start_vibration_pattern(self.vibration.ERROR))
        return tasks
    
    def show_information(self):
        """Show an information/warning indicator (yellow pulsing light, medium tone, single vibration).
        
        This indicator is designed for 5-year-olds and their teachers to provide
        information or a gentle warning.
        
        Returns:
            List of task objects that can be awaited
        """
        tasks = []
        self.set_led_color(self.YELLOW)
        tasks.append(self.start_led_pattern(self.led_ring.BREATHE, speed=4, duration_ms=1000))
        tasks.append(self.start_buzzer_pattern(self.buzzer.INFO))
        tasks.append(self.start_vibration_pattern(self.vibration.INFO))
        return tasks
    
    def show_connecting(self):
        """Show a searching/connecting indicator (blue chasing light, ascending/descending tones, continuous pulsing).
        
        This indicator is designed for 5-year-olds and their teachers to indicate
        the system is searching or trying to connect.
        
        Returns:
            List of task objects that can be awaited
        """
        tasks = []
        self.set_led_color(self.BLUE)
        tasks.append(self.start_led_pattern(self.led_ring.CHASE, speed=5, duration_ms=2000))
        tasks.append(self.start_buzzer_pattern(self.buzzer.CONNECTING))
        tasks.append(self.start_vibration_pattern(self.vibration.CONNECTING))
        return tasks
    
    def show_connection_established(self):
        """Show a connection established indicator (blue rainbow, connection melody, triple pulse).
        
        This indicator is designed for 5-year-olds and their teachers to indicate
        a successful connection.
        
        Returns:
            List of task objects that can be awaited
        """
        tasks = []
        self.set_led_color(self.BLUE)
        tasks.append(self.start_led_pattern(self.led_ring.RAINBOW_BLUE, speed=5, duration_ms=2000))
        tasks.append(self.start_buzzer_pattern(self.buzzer.CONNECTED))
        tasks.append(self.start_vibration_pattern(self.vibration.CONNECTED))
        return tasks
    
    def show_attention(self):
        """Show an attention indicator (multi-color alternating, attention melody, long-short vibration).
        
        This indicator is designed for 5-year-olds and their teachers to get
        the user's attention.
        
        Returns:
            List of task objects that can be awaited
        """
        tasks = []
        # Set up multi-color alternating pattern
        self.set_led_color(self.RED)
        tasks.append(self.start_led_pattern(self.led_ring.ALTERNATE, speed=7, duration_ms=1500))
        tasks.append(self.start_buzzer_pattern(self.buzzer.ATTENTION))
        tasks.append(self.start_vibration_pattern(self.vibration.ATTENTION))
        return tasks
    
    def show_calm(self):
        """Show a calm/ready indicator (soft blue breathing light, gentle descending tone, no vibration).
        
        This indicator is designed for 5-year-olds and their teachers to indicate
        the system is ready or in a calm state.
        
        Returns:
            List of task objects that can be awaited
        """
        tasks = []
        self.set_led_color(self.BLUE)
        tasks.append(self.start_led_pattern(self.led_ring.BREATHE, speed=3, duration_ms=2000))
        tasks.append(self.start_buzzer_pattern(self.buzzer.CALM))
        return tasks
    
    def show_celebration(self):
        """Show a celebration indicator (rainbow pattern, celebratory melody, triple pulse).
        
        This indicator is designed for 5-year-olds and their teachers to celebrate
        an achievement or milestone.
        
        Returns:
            List of task objects that can be awaited
        """
        tasks = []
        # Increase brightness for celebration
        self.set_led_brightness(255)
        tasks.append(self.start_led_pattern(self.led_ring.RAINBOW, speed=8, duration_ms=2000))
        tasks.append(self.start_buzzer_pattern(self.buzzer.CELEBRATION))
        tasks.append(self.start_vibration_pattern(self.vibration.CELEBRATION))
        return tasks
    
    def show_sleep(self):
        """Show a sleep/shutdown indicator (dimming light, soft descending tone, gentle pulse).
        
        This indicator is designed for 5-year-olds and their teachers to indicate
        the system is going to sleep or shutting down.
        
        Returns:
            List of task objects that can be awaited
        """
        tasks = []
        # Start with full brightness and gradually dim
        self.set_led_brightness(255)
        self.set_led_color(self.BLUE)
        
        # Create a task to gradually dim the light
        async def dim_light():
            for brightness in range(255, 0, -5):
                self.set_led_brightness(brightness)
                await asyncio.sleep_ms(50)
            self.set_led_color(self.OFF)
        
        tasks.append(asyncio.create_task(dim_light()))
        tasks.append(self.start_buzzer_pattern(self.buzzer.SLEEP))
        tasks.append(self.start_vibration_pattern(self.vibration.SLEEP))
        return tasks
    
    def show_help(self):
        """Show a help/assistance indicator (purple pulsing light, friendly alternating notes, double gentle pulse).
        
        This indicator is designed for 5-year-olds and their teachers to indicate
        help is available.
        
        Returns:
            List of task objects that can be awaited
        """
        tasks = []
        self.set_led_color(self.PURPLE)
        tasks.append(self.start_led_pattern(self.led_ring.BREATHE, speed=4, duration_ms=1500))
        tasks.append(self.start_buzzer_pattern(self.buzzer.HELP))
        tasks.append(self.start_vibration_pattern(self.vibration.HELP))
        return tasks 