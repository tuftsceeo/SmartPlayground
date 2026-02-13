from pyscript import window
from pyscript.js_modules import ble
import asyncio

SERVICE_UUID = '0000fff0-0000-1000-8000-00805f9b34fb'
WRITE_UUID   = '0000fff3-0000-1000-8000-00805f9b34fb' 
NOTIFY_UUID  = '0000fff4-0000-1000-8000-00805f9b34fb'

# Command constants
KEEP_ALIVE = 0x01, 0x00
SOUND_OFF = 0x02, 0x00
ALL_LEDS_OFF = 0x03, 0x00
ALL_TASKS_OFF = 0x04, 0x00
READ_SWITCHES = 0x05, 0x00
READ_BATTERY = 0x06, 0x00
IDENTIFY_SPLAT = 0x00, 0x10
SET_VOLUME = 0x01, 0x10
PLAY_SOUND = 0x00, 0x20
PLAY_RECORDED_SOUND = 0x01, 0x20
LEDS_OFF = 0x04, 0x20
SET_LEDS = 0x01, 0x50
PLAY_LED_SEQUENCE = 0x01, 0x60
FLASH_LEDS = 0x01, 0x70
NOTE_ON = 0x00, 0x40
NOTE_OFF = 0x01, 0x40

class Hub():
    def __init__(self):
        self.info = None
        self.myble = ble.myBLE
        self.myble.callback = self.received
        self.reply = None
        self.callback = None
        
    async def received(self, data):
        data = [d for d in data]
        window.console.log(f'received {data}')
        self.reply = data
        if self.callback: 
            await self.callback(data)
        
    async def connect(self, name):
        await self.myble.connect(name, SERVICE_UUID, WRITE_UUID, NOTIFY_UUID)
        #await self.write([0x00, 0x10]) # confirm connection
        await asyncio.sleep(0.1)
        if self.reply == [0, 16]:
            window.console.log('Success')

    def disconnect(self):
        self.myble.disconnect()

    async def write(self, data):
        data = [b for b in data]
        await self.myble.write(data)
        print('sent ',data)

    async def keepAlive(self):
        """Keep Alive reset 3 second and 5 minute timers"""
        return await self.write(bytearray(KEEP_ALIVE))

    async def soundOff(self):
        """Turn sound off"""
        return await self.write(bytearray(SOUND_OFF))

    async def allLEDsOff(self):
        """Turn all LEDs Off"""
        return await self.write(bytearray(ALL_LEDS_OFF))

    async def allTasksOff(self):
        """Turn all tasks off"""
        return await self.write(bytearray(ALL_TASKS_OFF))

    async def readSwitches(self):
        """Read switch state"""
        return await self.write(bytearray(READ_SWITCHES))

    async def readBattery(self):
        """Read Battery voltage"""
        return await self.write(bytearray(READ_BATTERY))

    async def identifySplat(self):
        """Identify the Splat"""
        return await self.write(bytearray(IDENTIFY_SPLAT))

    async def setVolume(self, vol):
        """Set volume level"""
        return await self.write(bytearray(SET_VOLUME + (vol,)))

    async def playSound(self, soundIndex, vol):
        """Play system sound effect"""
        return await self.write(bytearray(PLAY_SOUND + (soundIndex, vol)))

    async def playRecordedSound(self, soundIndex, vol):
        """Play uploaded sound"""
        return await self.write(bytearray(PLAY_RECORDED_SOUND + (soundIndex, vol)))

    async def LEDsOff(self, lowByte, highByte):
        """Turn LEDs off"""
        return await self.write(bytearray(LEDS_OFF + (lowByte, highByte)))

    async def setLEDs(self, lowByte, highByte, red, green, blue):
        """Set color of LED"""
        return await self.write(bytearray(SET_LEDS + (lowByte, highByte, red, green, blue)))

    async def setLEDsON(self, color):
        return await self.write(bytearray(SET_LEDS + (0xFF, 0x3F, color[0], color[1], color[2])))

    async def setLEDs(self, leds, red, green, blue): 
        value = 0
        for led in leds:
            value = value | 1 << led 
        return await self.write(bytearray(SET_LEDS + (value & 0xFF, value >> 8 & 0xFF, red, green, blue)))

    async def playLEDSequence(self, seqIndex, red, green, blue, duration, loops):
        """Play light sequence"""
        #duration is in milliseconds
        return await self.write(bytearray(PLAY_LED_SEQUENCE + (seqIndex, red, green, blue, duration, loops)))

    async def flashLEDs(self, lowByte, highByte, red, green, blue, duration, flashes):
        """Flash LEDs"""
        return await self.write(bytearray(FLASH_LEDS + (lowByte, highByte, red, green, blue, duration, flashes)))
    
    async def noteOn(self, note, velocity, octave, instrument):
                # 0x4000    Note    Octave  Velocity    Instrument / Timbre Play MIDI Note or Chord 
        # This command receive to NoteOn, the channel will dynamic to play
        return await self.write(bytearray(NOTE_ON+ (note, octave, velocity, instrument)))
        
    async def noteOff(self, note, velocity, octave, instrument):
                # 0x4001    Note    Octave  Velocity    Instrument / Timbre Turn Off MIDI Note or Chord 
        # This command must same to NoteOn Command which note you want to NoteOFF. 
        return await self.write(bytearray(NOTE_OFF+ (note, octave, velocity, instrument)))
