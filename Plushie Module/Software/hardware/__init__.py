"""
Educational Module System - Hardware Interface
-------------------------------------------
This module provides a unified interface for all hardware components.
"""
from .accelerometer import Accelerometer
from .led_ring import AsyncLEDRing
from .button import Button
from .buzzer import Buzzer
from .vibration import Vibration
from .power_management import PowerManagement

class HardwareInterface:
    """Unified interface for all hardware components"""
    
    def __init__(self):
        """Initialize all hardware components"""
        # Initialize accelerometer
        self.accelerometer = Accelerometer()
        
        # Initialize LED ring
        self.led_ring = AsyncLEDRing(pin_num=20)
        
        # Initialize button
        self.button = Button(pin_num=17)
        
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