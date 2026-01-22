"""
MusicBoard: Interactive Music Sequencer Game Controller
Handles the game flow for students to become coders and play musical sequences.
"""

from machine import Pin, I2S, Timer
import neopixel
import time
import network
import espnow
from networking import Networking
import ustruct



# Pin definitions for XIAO ESP32-C6
NEOPIXEL_PIN = 21
I2S_SCK_PIN = 20  # Serial Clock
I2S_WS_PIN = 18   # Word Select
I2S_SD_PIN = 19   # Serial Data
CODER_BUTTON_PIN = 1
PLAY_BUTTON_PIN = 2
STYLE_BUTTON_PIN = 0

# Constants
TOTAL_LEDS = 67
GRID_SIZE = 8
NOTE_COUNT = 8
BUFFER_SIZE = 1024  # Adjustable based on available memory

# Color mapping for notes (in GRB format)
NOTE_COLORS = {
    1: (100, 0, 0),    # Red for C (Middle C)
    2: (255, 127, 0),  # Orange for D
    3: (255, 255, 0),  # Yellow for E
    4: (0, 255, 0),    # Green for F
    5: (0, 255, 255),  # Cyan for G
    6: (0, 0, 255),    # Blue for A
    7: (50, 0, 255),   # Purple for B
    8: (150, 70, 200), # Pink for High C
    None: (0, 0, 0)    # Off
}

# Button LED status colors (in GRB format)
BUTTON_STATES = {
    'inactive': (0, 0, 0),      # Off
    'requesting': (0, 0, 255),  # Blue
    'active': (0, 125, 125),    # Teal
    'playing': (0, 255, 0),     # Green
    'paused': (255, 255, 0),    # Yellow
}

STATES = {
    'READY': {  # Initial state, waiting for coder
        'coder_led': 'playing',
        'play_led': 'inactive',
        'description': 'Ready for new coder'
    },
    'INVITING': {  # Inviting a coder
        'coder_led': 'requesting',
        'play_led': 'inactive',
        'description': 'Inviting coder'
    },
    'WAITING': {  # Have coder, waiting for sequence
        'coder_led': 'playing',
        'play_led': 'inactive',
        'description': 'Waiting for sequence'
    },
    'PLAYING': {  # Playing a sequence
        'coder_led': 'paused',
        'play_led': 'paused',
        'description': 'Playing sequence'
    },
    'PAUSED': {  # Sequence loaded but not playing
        'coder_led': 'playing',
        'play_led': 'playing',
        'description': 'Sequence paused'
    },
    'ERROR': {  # Error state
        'coder_led': 'inactive',
        'play_led': 'inactive',
        'description': 'Error occurred'
    }
}

# Tempo settings with corresponding delays and WAV file suffixes
TEMPOS = {
    'slow': {'delay': 1000, 'file_suffix': '_slow'},
    'normal': {'delay': 500, 'file_suffix': ''},
    'fast': {'delay': 250, 'file_suffix': '_fast'}
}


# --- ESP-NOW Setup ---
networking = Networking(True, False) #First bool is for network info messages, second for network debug messages
broadcast_mac = b'\xff\xff\xff\xff\xff\xff'
networking.ap._ap.active(False)
networking.aen.add_peer(broadcast_mac, "All")
networking.aen.ping(broadcast_mac)
networking.name = 'Music'

# -- Buttons --

# Initialize Neopixels
np = neopixel.NeoPixel(Pin(NEOPIXEL_PIN), TOTAL_LEDS)

            
# Initialize buttons with pull-up
coder_button = Pin(CODER_BUTTON_PIN, Pin.IN, Pin.PULL_UP)
play_button = Pin(PLAY_BUTTON_PIN, Pin.IN, Pin.PULL_UP)
style_button = Pin(STYLE_BUTTON_PIN, Pin.IN, Pin.PULL_UP)
            



# Initialize I2S with error handling
# I2S Setup Function with Variable Rate
def setup_i2s(sample_rate, bit_depth,BUFFER_SIZE = 1024):
    i2s = I2S(
        0,
        sck=Pin(20),   # Serial Clock BCLK D9
        ws=Pin(18),    # Word Select / LR Clock D10
        sd=Pin(19),    # Serial Data
        mode=I2S.TX,
        bits=bit_depth,
        format=I2S.MONO,
        rate=sample_rate,
        ibuf=BUFFER_SIZE
    )
    return i2s

# Helper function to parse the .wav header and extract audio parameters
def parse_wav_header(file):
    """
        Parse WAV file header to extract audio parameters.
        
        Args:
            file: Open file handle to WAV file
            
        Returns:
            tuple: (sample_rate, bit_depth)
    """
    file.seek(0)  # Ensure we're at the start of the file
    header = file.read(44)  # Standard .wav header size
    sample_rate = ustruct.unpack('<I', header[24:28])[0]
    bit_depth = ustruct.unpack('<H', header[34:36])[0]
    return sample_rate, bit_depth

def play_sound(path):
        # Open the .wav file from the SD card
    with open(path, "rb") as wav_file:
        sample_rate, bit_depth = parse_wav_header(wav_file)
        print(sample_rate, bit_depth)
        i2s = setup_i2s(sample_rate, bit_depth)

        # Skip the header and begin reading audio data
        wav_file.seek(44)  # Start of PCM data after 44-byte header

        # Buffer to hold PCM data read from the file
        buffer = bytearray(1024)
        
        while True:
            try:
                num_read = wav_file.readinto(buffer)
                if num_read == 0:
                    break  # End of file
                i2s.write(buffer[:num_read])  # Write to I2S in chunks
            except KeyboardInterrupt:
                print("CTRL C pressed")
                


class MusicBoard:
    """
    Main controller class for the musical sequencer and display system.
    
    Manages LED display, button inputs, audio playback, and network communication.
    Supports multiple playback speeds and visual animations.
    
    Attributes:
        debug (bool): Enable/disable debug output
        np (NeoPixel): NeoPixel strip controller
        i2s (I2S): I2S audio controller
        current_sequence (list): Current musical sequence being played/displayed
        is_playing (bool): Playback state
        current_style (str): Current tempo setting ('slow', 'normal', 'fast')
        error_state (bool): System error status
    """

    def __init__(self, debug=False):
        """Initialize music board game controller."""
        self.debug = debug
        self.debug_print("Initializing MusicBoard Game...")
        
        
        self.np = np
        self.np.fill((0,0,0))
        time.sleep_ms(10) 
        self.np.write()

            
        # Initialize buttons with pull-up
        self.coder_button = coder_button
        self.play_button = play_button 
        self.style_button = style_button
        self._init_state()
        self._init_timers()
        self.networking = networking
        
        # Initialize game state
        self.game_state = "READY"  # States: READY, ACTIVE
        self.current_coder = None  # MAC address of current coder
        self.coders_list = set()   # Set of all coder MAC addresses
        self.invitation_active = False
        #self.is_playing = False
        
        # Display ready state
        self._show_ready_state()
        self._update_button_leds()
        self.debug_print("Game initialized and ready.")


        

    def _init_state(self):
        """
        Initialize internal state variables.
        
        Sets default values for:
        - Sequence and playback state
        - Animation parameters
        - System status flags
        """
      
        self.game_state = 'READY'
        self.current_sequence = []
        self.current_style = 'normal'
        self.styles = list(TEMPOS.keys())
        self.current_beat = -1
        self.button_brightness = 100
        self.pulse_direction = 1
        self.coders_list = set()
        self.current_coder = None
            
        

    def _init_timers(self):
        """
        Initialize system timers for playback and animations.
        
        Creates timers for:
        - Sequence playback
        - LED animations
        - Button status updates
        
        Sets error_state if initialization fails
        """
        try:
            self.play_timer = Timer(0)
            #self.animation_timer = Timer(1)
            #self.button_animation_timer = Timer(2)
        except Exception as e:
            self.debug_print(f"Timer initialization failed: {e}")
            self.error_state = True
        

    

    #def clear_display(self):
       # """Clear all LEDs in the display."""
        #self.np.fill((0, 0, 0))
        #self.np.write()

    def debug_print(self, message):
        """
        Print debug message if debug mode is enabled.
        
        Args:
            message (str): Debug message to print
        """
        if self.debug:
            print(f"[DEBUG] {message}")


    def _get_grid_index(self, col, row):
        """
        Convert grid coordinates to LED strip index.
        
        Args:
            col (int): Column index (0-7, right to left)
            row (int): Row index (0-7, bottom to top)
            
        Returns:
            int: LED strip index or None if coordinates invalid
            
        Note:
            LED strip addressing starts at top-right corner (index 0)
            and progresses column by column toward the left
        """
        if not (0 <= col < 8 and 0 <= row < 8):
            self.debug_print(f"Invalid grid position: col={col}, row={row}")
            return None
            
        base = (col) * 8 #(7-col) * 8
        index = base + (7 - row)
        
        if not (0 <= index < 64):
            self.debug_print(f"Invalid LED index calculated: {index}")
            return None
            
        return index

    def _play_note(self, note_number):
        """
        Play WAV file for specified note number.
        
        Args:
            note_number (int): Note to play (1-8)
            
        Uses current_style to determine which WAV file to play
        (e.g., note1.wav, note1_fast.wav, note1_slow.wav)
        
        Handles I2S errors and attempts recovery if playback fails
        """
       
            
        suffix = TEMPOS[self.current_style]['file_suffix']
        filename = f"notet{note_number}{suffix}.wav"
        print("playing file", filename)
        
        
        
        play_sound(filename)
        self.debug_print(f"Playing {filename}")
                

  

    def _play_sequence_step(self, timer):
        """
        Play one step of the current sequence.
        
        Args:
            timer: Timer instance (unused but required for callback)
            
        Updates display to highlight current beat
        Handles playback errors and stops sequence if error occurs
        """
        #if not self.game_state == 'PLAYING': # or not self.current_sequence:
        #    return
            
        
        self.current_beat = (self.current_beat + 1) % len(self.current_sequence)
        note = self.current_sequence[self.current_beat]
        
        # Update display with highlighted column
        self.display_sequence(self.current_sequence, self.current_beat)
        
        # Play the note
        if note is not None:
            self._play_note(note)


    def _update_button_leds(self):
        """Update button LEDs based on current state."""
        #brightness = self.button_brightness / 100
        
        state_config = STATES[self.game_state]
        
        # Coder button (index 64)
        coder_color = BUTTON_STATES[state_config['coder_led']]
        self.np[66] = coder_color
        
        # Play/Pause button (index 65)
        play_color = BUTTON_STATES[state_config['play_led']]
        self.np[65] = play_color
        
        # Style button (index 66)
        style_colors = {
            'normal': (0, 255, 0),    # Green
            'fast': (255, 0, 0),      # Red
            'slow': (0, 0, 255)       # Blue
        }
        self.np[64] = style_colors[self.current_style]
        time.sleep_ms(10) 
        self.np.write()
        
#     def _start_invitation_timer(self):
#         """Start timer for coder invitation timeout."""
#         def _timeout_handler(timer):
#             self.debug_print("Invitation timer triggered")  # Add debug print
#             if self.game_state == '':
#                 self.debug_print("Resetting to READY state")
#                 self.game_state = 'READY'
#                 #self.invitation_active = False  # Also reset this flag
#                 self._update_button_leds()
#                 self.debug_print("Invitation timeout complete")
#         
#         self.debug_print("Starting invitation timer")  # Add debug print
#         timer = Timer(3)
#         timer.init(mode=Timer.ONE_SHOT, period=5000, callback=_timeout_handler)    
#     
#     def _animate_buttons(self, timer):
#         """
#         Update button pulsing animation.
#         
#         Args:
#             timer: Timer instance (unused but required for callback)
#         """
#         self.button_brightness += self.pulse_direction * 5
#         if self.button_brightness >= 100:
#             self.button_brightness = 100
#             self.pulse_direction = -1
#         elif self.button_brightness <= 20:
#             self.button_brightness = 20
#             self.pulse_direction = 1
#             
#         self._update_button_leds()

    def _stop_playback(self):
        """
        Stop current sequence playback.
        
        Stops timers and resets playback state.
        """
        self.play_timer.deinit()
        #self.button_animation_timer.deinit()
        self.current_beat = -1
        self.display_sequence(self.current_sequence)  # Remove highlight
        self.game_state == 'PAUSED'
        self._update_button_leds()

    def display_sequence(self, sequence, highlight_col=None):
        """
        Display sequence on LED grid with optional column highlight.
        
        Args:
            sequence (list): List of notes to display
            highlight_col (int, optional): Column to highlight
        """
        for p in range(64):
            self.np[p] = (0, 0, 0)
        
        for col, note in enumerate(sequence):
            if note is not None and 1 <= note <= 8:
                row = note-1 # 0 botton to top 7
                            # col 0 left to right 7
                led_index = self._get_grid_index(col, row)
                
                if led_index is not None:
                    # draw notes of sequence
                    color = NOTE_COLORS[note]
                    
                    
                    if col == highlight_col:
                        if note == 1:
                            color=(255,10,5)
                        #elif col%2 != 0:
                         #   print(range(0-(8-note),note-(8-note)))
                          #  for i in range(0,note):
                           #     self.np[(col*8)+i] = color
                        else:
                            for fill_row in range(0,row):
                                fill_index = self._get_grid_index(col, fill_row)
                                if fill_index is not None:
                                    self.np[fill_index] = color
                            #print(range(8-note,8))
                            #for i in range(8-note,8):
                            #    self.np[(col*8+i)] = color
                    self.np[led_index] = color
                    
                    
                    
        
        
        time.sleep_ms(10) 
        self.np.write()


    def _debounce(self, pin, delay_ms=100):
        """
        Debounce button input.
        
        Args:
            pin: Pin to debounce
            delay_ms (int): Debounce delay in milliseconds
            
        Returns:
            bool: True if input is stable and button press is confirmed
        """
        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < delay_ms:
            if pin.value():
                return False
        return True


    def _show_ready_state(self):
        """Display ready state pattern on LED grid."""
        self.np.fill((0, 0, 0))
        
        for i in range(8):
            for j in range(8):
                if (i + j) % 2 == 0:
                    led_index = self._get_grid_index(i, j)
                    if led_index is not None:
                        self.np[led_index] = NOTE_COLORS[i+1]#(0, 0, 255)  # Blue checkerboard pattern
        self._update_button_leds()

    def _coder_button_handler(self, pin):
        """Handle coder button with state transitions."""
        if not self._debounce(pin):
            return
            
        #if self.game_state == 'READY' :
        self.debug_print("Coder button pressed - NOT transitioning to INVITING")
        #self.game_state = 'INVITING'
        #self.invitation_active = True
        self.networking.aen.send(broadcast_mac, 'Coder')
        self._update_button_leds()
        #self._start_invitation_timer()
        #self.debug_print("Invitation sequence complete")

    def _play_button_handler(self, pin):
        """Handle play button with state transitions."""
        if not self._debounce(pin):
            return
            
        #if self.game_state == 'PLAYING':
        #    print("Pause Button")
        #    self.game_state = 'PAUSED'
        #    self._stop_playback()
        #elif self.game_state == 'PAUSED' and
        if self.current_sequence and not self.game_state == 'PLAYING':
            self.game_state = 'PLAYING'
            self._update_button_leds()
            print("Play Button")
            self._start_playback()
        
        self.game_state = 'PAUSED'
        self._update_button_leds()

    def _style_button_handler(self, pin):
        """Handle style button press to change tempo."""
        if not self._debounce(pin):
            return
            
        # Cycle through styles
        current_index = self.styles.index(self.current_style)
        self.current_style = self.styles[(current_index + 1) % len(self.styles)]
        
        # If currently playing, restart with new tempo
        was_playing = self.game_state == 'PLAYING'
        #if was_playing:
            #self._stop_playback()
        self._update_button_leds()
        if was_playing:
            self._start_playback()

    def _start_playback(self):
        """Start playing the current sequence."""
        if not self.current_sequence:
            return
            
        self.current_beat = -1  # Reset to start
        tempo_delay = TEMPOS[self.current_style]['delay']

        #self.play_timer.init(period=tempo_delay, mode=Timer.PERIODIC, callback=self._play_sequence_step)
        print(tempo_delay)
        for i in range(0,len(self.current_sequence)):
            if self.game_state == 'PLAYING':
                self._play_sequence_step(None)
                #time.sleep(tempo_delay/1000)
            else:
                break
        self.display_sequence(self.current_sequence)  # Remove highlight
        self.game_state == 'PAUSED'
        board._update_button_leds()
        # Start button animation
        #self.button_animation_timer.init(period=50, mode=Timer.PERIODIC,
                                       #callback=self._animate_buttons)
    def handle_error_state(self):
        """
        Handle error state with visual feedback.
        
        Returns:
            bool: True if system is in error state
                                 bv
        Sets all button LEDs to red in error state
        """
        if self.error_state:
            self.np.fill((0, 0, 0))
            
            # Display error pattern
            for i in range(64, 67):
                self.np[i] = (255, 0, 0)  # Red
            time.sleep_ms(10) 
            self.np.write()
            self.debug_print("System in error state")
            return True
        return False
    
    def run(self):
        """Main game loop with simplified state handling."""
        print(f"Music Board running in {self.game_state} state...")
        
 
 
 
board = MusicBoard(debug=True)


coder_button.irq(trigger=Pin.IRQ_FALLING, handler=board._coder_button_handler)
play_button.irq(trigger=Pin.IRQ_FALLING, handler=board._play_button_handler)
style_button.irq(trigger=Pin.IRQ_FALLING, handler=board._style_button_handler)

def network_callback():
        """Handle network messages with state transitions."""
        for mac, msg, rtime in networking.aen.return_messages():
            print('received', msg, type(msg))
            
            if msg == 'Coder': #and board.game_state == 'INVITING':
                board.coders_list.add(mac)
                board.current_coder = mac
                board.game_state = 'WAITING'
                board._update_button_leds()
                
            elif isinstance(msg, list) and len(msg) <= 8:
                #if mac in board.coders_list:
                board.current_sequence = msg
                board.game_state = 'PAUSED'
                board._update_button_leds()
                board.display_sequence(msg)
                #board._start_playback()

networking.aen.irq(network_callback)

# --- Main Loop ---
def main():
    print("Game controller initialized. Waiting for input...")
    while True:
        time.sleep(0.5)

if __name__ == "__main__":
    main()
