"""
Educational Module System - Button Interface
------------------------------------------
This module provides an interface for the tactile button.
"""
import time
from machine import Pin

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