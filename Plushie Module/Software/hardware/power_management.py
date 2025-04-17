"""
Educational Module System - Power Management
------------------------------------------
This module provides power management functionality for the Educational Module System.
"""
import time
import gc
import machine
from machine import Pin, ADC, Timer

class PowerManagement:
    """Power management for the hardware interface"""
    
    def __init__(self, button_pin=0):
        """Initialize power management.
        
        Args:
            button_pin: Pin for wake-up button
        """


        
        self.last_activity = time.ticks_ms()
        self.light_sleep_timer = None
        self.deep_sleep_timer = None
        
        self.light_sleep_threshold_ms = 2 * 60 * 1000  # 2 minutes
        self.deep_sleep_threshold_ms = 10 * 60 * 1000  # 10 minutes
        
        self.button_pin = button_pin
        
        # Start sleep timers
        self._reset_timers()
    
    def _reset_timers(self):
        """Reset sleep timers"""
        self.last_activity = time.ticks_ms()
        
        # Stop existing timers
        if self.light_sleep_timer:
            self.light_sleep_timer.deinit()
        if self.deep_sleep_timer:
            self.deep_sleep_timer.deinit()
        
        # Start new timers
        self.light_sleep_timer = Timer(-1)
        self.deep_sleep_timer = Timer(-1)
        
        self.light_sleep_timer.init(
            period=self.light_sleep_threshold_ms, 
            mode=Timer.ONE_SHOT,
            callback=self._enter_light_sleep
        )
        
        self.deep_sleep_timer.init(
            period=self.deep_sleep_threshold_ms, 
            mode=Timer.ONE_SHOT,
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
    
