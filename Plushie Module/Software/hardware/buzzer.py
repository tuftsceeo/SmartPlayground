"""
Educational Module System - Buzzer Interface
------------------------------------------
This module provides an asynchronous interface for the buzzer (sound output).
"""
import time
from machine import Pin, PWM
import uasyncio as asyncio

class Buzzer:
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
    
    # Predefined sound patterns
    DOUBLE = "DOUBLE"
    TRIPLE = "TRIPLE"
    ASCENDING = "ASCENDING"
    DESCENDING = "DESCENDING"
    SOS = "SOS"
    DING = "DING"  # Short ascending ding for confirmation
    ERROR = "ERROR"  # Descending error tone
    INFO = "INFO"  # Single medium tone for information
    CONNECTING = "CONNECTING"  # Ascending and descending for connecting
    CONNECTED = "CONNECTED"  # Connection established melody
    ATTENTION = "ATTENTION"  # Attention-grabbing melody
    CALM = "CALM"  # Gentle descending tone
    CELEBRATION = "CELEBRATION"  # Celebratory melody
    SLEEP = "SLEEP"  # Soft descending tone for sleep
    HELP = "HELP"  # Friendly alternating notes for help
    
    def __init__(self, pin_num=19):
        """Initialize the buzzer.
        
        Args:
            pin_num: GPIO pin connected to the buzzer
        """
        self.pwm = PWM(Pin(pin_num, Pin.OUT), freq=1000)
        self.pwm.duty(0)  # Initialize with no sound
        self.volume = 50  # Default volume (0-100)
        
        # Task management
        self.current_task = None
        self.is_playing = False
        self.task_list = {}  # Dictionary to store running tasks
    
    def set_volume(self, volume):
        """Set buzzer volume.
        
        Args:
            volume: Volume level (0-100)
        """
        self.volume = max(0, min(100, volume))
    
    def stop(self):
        """Stop buzzer immediately"""
        self.pwm.duty(0)
        self.cancel()
    
    def cancel(self):
        """Cancel current sound playback"""
        self.is_playing = False
        if self.current_task:
            self.current_task.cancel()
            self.current_task = None
    
    def cancel_all(self):
        """Cancel all sound tasks"""
        for task in self.task_list.values():
            task.cancel()
        self.task_list.clear()
    
    async def _play_frequency(self, frequency, duration_ms):
        """Internal method to play a frequency.
        
        Args:
            frequency: Frequency in Hz
            duration_ms: Duration in milliseconds
        """
        # Convert volume to PWM duty cycle (0-1023)
        duty = int(400 * self.volume / 100)
        
        # Set frequency and duty cycle
        self.pwm.freq(int(frequency))
        self.pwm.duty(duty)
        
        # Wait for the specified duration
        await asyncio.sleep(duration_ms / 1000)
        
        # Turn off the buzzer but don't change playing state
        self.pwm.duty(0)
    
    def play_note(self, note_name, duration_ms=500):
        """Play a musical note.
        
        Args:
            note_name: Note name (e.g., "C4", "D4", etc.)
            duration_ms: Duration in milliseconds
            
        Returns:
            The running task or None if note not found
        """
        if note_name in self.NOTES:
            return self.play_frequency(self.NOTES[note_name], duration_ms)
        return None
    
    def play_frequency(self, frequency, duration_ms=500):
        """Play a frequency.
        
        Args:
            frequency: Frequency in Hz
            duration_ms: Duration in milliseconds
            
        Returns:
            The running task
        """
        # Cancel any existing sound
        self.cancel()
        
        # Create new sound task
        self.is_playing = True
        self.current_task = asyncio.create_task(self._play_frequency(frequency, duration_ms))
        return self.current_task
    
    def play_pattern(self, pattern_type, base_frequency=440):
        """Play a predefined sound pattern.
        
        Args:
            pattern_type: One of the pattern constants
            base_frequency: Base frequency in Hz
            
        Returns:
            Task object that can be awaited
        """
        # Cancel any existing pattern
        self.cancel()
        
        # Set playing flag
        self.is_playing = True
        
        if pattern_type == self.DOUBLE:
            self.current_task = asyncio.create_task(self._double_pattern(base_frequency))
        elif pattern_type == self.TRIPLE:
            self.current_task = asyncio.create_task(self._triple_pattern(base_frequency))
        elif pattern_type == self.ASCENDING:
            self.current_task = asyncio.create_task(self._ascending_pattern())
        elif pattern_type == self.DESCENDING:
            self.current_task = asyncio.create_task(self._descending_pattern())
        elif pattern_type == self.SOS:
            self.current_task = asyncio.create_task(self._sos_pattern(base_frequency))
        elif pattern_type == self.DING:
            self.current_task = asyncio.create_task(self._ding_pattern())
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
    
    async def _double_pattern(self, frequency):
        """Internal method to play a double beep pattern."""
        if self.is_playing:
            await self._play_frequency(frequency, 200)
            await asyncio.sleep(0.1)
            await self._play_frequency(frequency, 200)
            self.is_playing = False
    
    async def _triple_pattern(self, frequency):
        """Internal method to play a triple beep pattern."""
        if self.is_playing:
            for _ in range(3):
                if not self.is_playing:
                    break
                await self._play_frequency(frequency, 200)
                if self.is_playing:
                    await asyncio.sleep(0.1)
            self.is_playing = False
    
    async def _ascending_pattern(self):
        """Internal method to play an ascending scale pattern."""
        if self.is_playing:
            notes = ["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"]
            for note in notes:
                if not self.is_playing:
                    break
                await self._play_frequency(self.NOTES[note], 300)
                if self.is_playing:
                    await asyncio.sleep(0.2)
            self.is_playing = False
    
    async def _descending_pattern(self):
        """Internal method to play a descending scale pattern."""
        if self.is_playing:
            notes = ["C5", "B4", "A4", "G4", "F4", "E4", "D4", "C4"]
            for note in notes:
                if not self.is_playing:
                    break
                await self._play_frequency(self.NOTES[note], 200)
                if self.is_playing and note != notes[-1]:
                    await asyncio.sleep(0.1)
            self.is_playing = False
    
    async def _sos_pattern(self, frequency):
        """Internal method to play an SOS pattern."""
        if self.is_playing:
            # Three short
            for _ in range(3):
                if not self.is_playing:
                    break
                await self._play_frequency(frequency, 200)
                if self.is_playing:
                    await asyncio.sleep(0.1)
            
            if self.is_playing:
                await asyncio.sleep(0.3)
            
            # Three long
            for _ in range(3):
                if not self.is_playing:
                    break
                await self._play_frequency(frequency, 500)
                if self.is_playing:
                    await asyncio.sleep(0.1)
            
            if self.is_playing:
                await asyncio.sleep(0.3)
            
            # Three short
            for _ in range(3):
                if not self.is_playing:
                    break
                await self._play_frequency(frequency, 200)
                if self.is_playing:
                    await asyncio.sleep(0.1)
            
            self.is_playing = False
    
    async def _ding_pattern(self):
        """Internal method to play a short ascending ding pattern."""
        if self.is_playing:
            await self._play_frequency(self.NOTES["C4"], 100)
            await asyncio.sleep(0.05)
            await self._play_frequency(self.NOTES["E4"], 200)
            self.is_playing = False
    
    async def _error_pattern(self):
        """Internal method to play an error pattern."""
        if self.is_playing:
            await self._play_frequency(self.NOTES["E4"], 200)
            await asyncio.sleep(0.1)
            await self._play_frequency(self.NOTES["C4"], 300)
            self.is_playing = False
    
    async def _info_pattern(self):
        """Internal method to play an info pattern."""
        if self.is_playing:
            await self._play_frequency(self.NOTES["A4"], 300)
            self.is_playing = False
    
    async def _connecting_pattern(self):
        """Internal method to play a connecting pattern."""
        if self.is_playing:
            # Ascending
            for note in ["C4", "E4", "G4", "C5"]:
                if not self.is_playing:
                    break
                await self._play_frequency(self.NOTES[note], 150)
                if self.is_playing:
                    await asyncio.sleep(0.1)
            
            if self.is_playing:
                await asyncio.sleep(0.2)
            
            # Descending
            for note in ["C5", "G4", "E4", "C4"]:
                if not self.is_playing:
                    break
                await self._play_frequency(self.NOTES[note], 150)
                if self.is_playing:
                    await asyncio.sleep(0.1)
            
            self.is_playing = False
    
    async def _connected_pattern(self):
        """Internal method to play a connection established pattern."""
        if self.is_playing:
            # Play a simple melody
            await self._play_frequency(self.NOTES["C4"], 200)
            await asyncio.sleep(0.1)
            await self._play_frequency(self.NOTES["E4"], 200)
            await asyncio.sleep(0.1)
            await self._play_frequency(self.NOTES["G4"], 300)
            self.is_playing = False
    
    async def _attention_pattern(self):
        """Internal method to play an attention pattern."""
        if self.is_playing:
            # Play attention-grabbing notes
            for _ in range(2):
                if not self.is_playing:
                    break
                await self._play_frequency(self.NOTES["A4"], 200)
                if self.is_playing:
                    await asyncio.sleep(0.1)
                await self._play_frequency(self.NOTES["C5"], 300)
                if self.is_playing:
                    await asyncio.sleep(0.2)
            self.is_playing = False
    
    async def _calm_pattern(self):
        """Internal method to play a calm pattern."""
        if self.is_playing:
            # Play a gentle descending tone
            await self._play_frequency(self.NOTES["C5"], 200)
            await asyncio.sleep(0.1)
            await self._play_frequency(self.NOTES["A4"], 200)
            await asyncio.sleep(0.1)
            await self._play_frequency(self.NOTES["F4"], 300)
            self.is_playing = False
    
    async def _celebration_pattern(self):
        """Internal method to play a celebration pattern."""
        if self.is_playing:
            # Play a celebratory melody
            notes = ["C4", "E4", "G4", "C5", "G4", "E4", "C4"]
            for note in notes:
                if not self.is_playing:
                    break
                await self._play_frequency(self.NOTES[note], 150)
                if self.is_playing:
                    await asyncio.sleep(0.05)
            
            # End with a flourish
            if self.is_playing:
                await asyncio.sleep(0.1)
                await self._play_frequency(self.NOTES["C5"], 300)
            
            self.is_playing = False
    
    async def _sleep_pattern(self):
        """Internal method to play a sleep pattern."""
        if self.is_playing:
            # Play a soft descending tone
            await self._play_frequency(self.NOTES["A4"], 200)
            await asyncio.sleep(0.1)
            await self._play_frequency(self.NOTES["F4"], 200)
            await asyncio.sleep(0.1)
            await self._play_frequency(self.NOTES["D4"], 300)
            self.is_playing = False
    
    async def _help_pattern(self):
        """Internal method to play a help pattern."""
        if self.is_playing:
            # Play friendly alternating notes
            for _ in range(2):
                if not self.is_playing:
                    break
                await self._play_frequency(self.NOTES["C4"], 200)
                if self.is_playing:
                    await asyncio.sleep(0.1)
                await self._play_frequency(self.NOTES["E4"], 200)
                if self.is_playing:
                    await asyncio.sleep(0.1)
                await self._play_frequency(self.NOTES["G4"], 300)
                if self.is_playing:
                    await asyncio.sleep(0.2)
            self.is_playing = False
    
    def play_demo(self):
        """Play a demo melody showcasing various sounds.
        
        Returns:
            Task object that can be awaited
        """
        # Cancel any existing pattern
        self.cancel()
        
        # Set playing flag
        self.is_playing = True
        
        # Create demo task
        self.current_task = asyncio.create_task(self._play_demo())
        return self.current_task
    
    async def _play_demo(self):
        """Internal method to play a demo melody."""
        if self.is_playing:
            # Play a simple melody
            notes = ["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"]
            for note in notes:
                if not self.is_playing:
                    break
                await self._play_frequency(self.NOTES[note], 300)
                if self.is_playing:
                    await asyncio.sleep(0.2)
            
            # Play a descending scale
            if self.is_playing:
                await asyncio.sleep(0.5)
                for note in reversed(notes):
                    if not self.is_playing:
                        break
                    await self._play_frequency(self.NOTES[note], 200)
                    if self.is_playing:
                        await asyncio.sleep(0.1)
            
            self.is_playing = False 