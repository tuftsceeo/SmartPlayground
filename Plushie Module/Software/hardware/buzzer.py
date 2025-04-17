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
    PATTERN_DOUBLE = "DOUBLE"
    PATTERN_TRIPLE = "TRIPLE"
    PATTERN_ASCENDING = "ASCENDING"
    PATTERN_DESCENDING = "DESCENDING"
    PATTERN_SOS = "SOS"
    
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
            try:
                self.current_task.cancel()
            except:
                pass
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
            pattern_type: One of the PATTERN_* constants
            base_frequency: Base frequency for patterns
            
        Returns:
            The running task
        """
        # Cancel any existing sound
        self.cancel()
        
        # Create new pattern task
        self.is_playing = True
        
        if pattern_type == self.PATTERN_DOUBLE:
            self.current_task = asyncio.create_task(self._double_pattern(base_frequency))
        elif pattern_type == self.PATTERN_TRIPLE:
            self.current_task = asyncio.create_task(self._triple_pattern(base_frequency))
        elif pattern_type == self.PATTERN_ASCENDING:
            self.current_task = asyncio.create_task(self._ascending_pattern())
        elif pattern_type == self.PATTERN_DESCENDING:
            self.current_task = asyncio.create_task(self._descending_pattern())
        elif pattern_type == self.PATTERN_SOS:
            self.current_task = asyncio.create_task(self._sos_pattern(base_frequency))
        
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
    
    def play_demo(self):
        """Play a demonstration phone ring melody"""
        self.cancel()
        self.is_playing = True
        
        tones = [
            (659.26, 150),  # E5
            (587.33, 150),  # D5
            (369.99, 300),  # F#4
            (415.3, 300),   # G#4
            (554.37, 150),  # C#5
            (493.88, 150),  # B4
            (293.66, 300),  # D4
            (329.63, 300),  # E4
            (493.88, 150),  # B4
            (440, 150),     # A4
            (277.18, 300),  # C#4
            (329.62, 300),  # E4
            (440, 600)      # A4
        ]
        
        async def _play_demo():
            for freq, duration in tones:
                if not self.is_playing:
                    break
                await self._play_frequency(freq, duration)
                if self.is_playing and freq != tones[-1][0]:
                    await asyncio.sleep(0.05)
            self.is_playing = False
        
        self.current_task = asyncio.create_task(_play_demo())
        return self.current_task 