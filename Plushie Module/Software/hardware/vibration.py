"""
Educational Module System - Vibration Interface
--------------------------------------------
This module provides an asynchronous interface for the vibration motor.
"""
import time
from machine import Pin
import uasyncio as asyncio

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