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
    CONTINUOUS = "CONTINUOUS"
    PULSE = "PULSE"
    DOUBLE = "DOUBLE"
    TRIPLE = "TRIPLE"
    LONG_SHORT = "LONG_SHORT"
    CONFIRM = "CONFIRM"  # Single short pulse for confirmation
    ERROR = "ERROR"  # Double pulse for error
    INFO = "INFO"  # Single medium pulse for information
    CONNECTING = "CONNECTING"  # Continuous gentle pulsing for connecting
    CONNECTED = "CONNECTED"  # Triple pulse for connection established
    ATTENTION = "ATTENTION"  # Long-short pattern for attention
    CALM = "CALM"  # Single gentle pulse for calm
    CELEBRATION = "CELEBRATION"  # Triple pulse with increasing intensity
    SLEEP = "SLEEP"  # Single gentle pulse for sleep
    HELP = "HELP"  # Double gentle pulse for help
    
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
        """Start a vibration pattern.
        
        Args:
            pattern_type: One of the pattern constants
            repeat: Number of times to repeat the pattern
            
        Returns:
            Task object that can be awaited
        """
        # Cancel any existing pattern
        self.cancel_vibration()
        
        # Set running flag
        self.running = True
        
        if pattern_type == self.CONTINUOUS:
            self.current_task = asyncio.create_task(self._continuous_pattern())
        elif pattern_type == self.PULSE:
            self.current_task = asyncio.create_task(self._pulse_pattern(repeat))
        elif pattern_type == self.DOUBLE:
            self.current_task = asyncio.create_task(self._double_pattern(repeat))
        elif pattern_type == self.TRIPLE:
            self.current_task = asyncio.create_task(self._triple_pattern(repeat))
        elif pattern_type == self.LONG_SHORT:
            self.current_task = asyncio.create_task(self._long_short_pattern(repeat))
        elif pattern_type == self.CONFIRM:
            self.current_task = asyncio.create_task(self._confirm_pattern())
        elif pattern_type == self.ERROR:
            self.current_task = asyncio.create_task(self._error_pattern())
        elif pattern_type == self.INFO:
            self.current_task = asyncio.create_task(self._info_pattern())
        elif pattern_type == self.CONNECTING:
            self.current_task = asyncio.create_task(self._connecting_pattern())
        elif pattern_type == self.CONNECTED:
            self.current_task = asyncio.create_task(self._connected_pattern())
        elif pattern_type == self.ATTENTION:
            self.current_task = asyncio.create_task(self._attention_pattern())
        elif pattern_type == self.CALM:
            self.current_task = asyncio.create_task(self._calm_pattern())
        elif pattern_type == self.CELEBRATION:
            self.current_task = asyncio.create_task(self._celebration_pattern())
        elif pattern_type == self.SLEEP:
            self.current_task = asyncio.create_task(self._sleep_pattern())
        elif pattern_type == self.HELP:
            self.current_task = asyncio.create_task(self._help_pattern())
        
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
    
    async def _confirm_pattern(self):
        """Single short pulse for confirmation."""
        await self._vibrate(200)
        self.running = False
    
    async def _error_pattern(self):
        """Double pulse for error."""
        await self._vibrate(200)
        await asyncio.sleep_ms(100)
        await self._vibrate(300)
        self.running = False
    
    async def _info_pattern(self):
        """Single medium pulse for information."""
        await self._vibrate(300)
        self.running = False
    
    async def _connecting_pattern(self):
        """Continuous gentle pulsing for connecting."""
        for _ in range(5):
            await self._vibrate(200)
            await asyncio.sleep_ms(300)
        self.running = False
    
    async def _connected_pattern(self):
        """Triple pulse for connection established."""
        await self._vibrate(200)
        await asyncio.sleep_ms(100)
        await self._vibrate(200)
        await asyncio.sleep_ms(100)
        await self._vibrate(300)
        self.running = False
    
    async def _attention_pattern(self):
        """Long-short pattern for attention."""
        await self._vibrate(500)
        await asyncio.sleep_ms(100)
        await self._vibrate(200)
        self.running = False
    
    async def _calm_pattern(self):
        """Single gentle pulse for calm."""
        await self._vibrate(300)
        self.running = False
    
    async def _celebration_pattern(self):
        """Triple pulse with increasing intensity for celebration."""
        await self._vibrate(200)
        await asyncio.sleep_ms(100)
        await self._vibrate(300)
        await asyncio.sleep_ms(100)
        await self._vibrate(400)
        self.running = False
    
    async def _sleep_pattern(self):
        """Single gentle pulse for sleep."""
        await self._vibrate(300)
        self.running = False
    
    async def _help_pattern(self):
        """Double gentle pulse for help."""
        await self._vibrate(200)
        await asyncio.sleep_ms(100)
        await self._vibrate(300)
        self.running = False 