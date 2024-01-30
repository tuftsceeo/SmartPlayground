import time
from BLE_MIDI import *
import distance_sensor as ds
from hub import port

notes = [60,61,62,63,64,63,62,61]

def Music():
    midi = MIDI_Player('fred')
    midi.wait_for_connection()
    Piano = MIDI_Instrument(midi, instruments['Acoustic Grand Piano'],channel = 0)
    
    try:
        while True:
            x = ds.distance(port.B)
            print(x)
            Piano.off(x)
            Piano.on(x,velocity['ff'])
            time.sleep(0.1)
    except:
        pass
    
    midi.disconnect()

Music()
