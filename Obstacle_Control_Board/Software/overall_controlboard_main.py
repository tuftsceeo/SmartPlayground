from machine import Pin, SPI, Timer
import espnow
from networking import Networking
import time
import ujson as json
import os
from playertracker import PlayerTracker
from gamestate import GameState
from max7219 import Max7219
import time

# --- Pin Constants for XIAO ESP32-C3 ---
CODER_BUTTON_PIN = 1 #3          
UNDO_BUTTON_PIN = 17 #20
RANDOM_BUTTON_PIN = 20 #9
PLAYER_BUTTON_PINS = [2,21,22,23] #[4, 5, 6, 7]  
NEOPIXEL_PIN = 16 #21       
SPI_SCK_PIN = 19 #8               
SPI_MOSI_PIN = 18 #10             
MAX7219_CS_PIN = 0 #2          

# --- Constants ---
INACTIVITY_TIMEOUT = 600  # 10 minutes in seconds
DISCONNECTION_TIMEOUT = 300  # 5 minutes in seconds
GAME_STATE_FILE = "game_state.json"
REQUEST_TIMEOUT = 5  # 5 seconds for request timeout

# --- ESP-NOW Setup ---
networking = Networking(True, False) #First bool is for network info messages, second for network debug messages
broadcast_mac = b'\xff\xff\xff\xff\xff\xff'
networking.ap._ap.active(False)
networking.aen.add_peer(broadcast_mac, "All")
networking.aen.ping(broadcast_mac)
networking.name = 'Control Board'

# --- Initialize Classes ---
game_state = GameState(coder_mac=None)
player_tracker = PlayerTracker(pin=NEOPIXEL_PIN)


# --- MAX7219 Setup ---
spi = SPI(1, baudrate=10000000, sck=Pin(SPI_SCK_PIN), mosi=Pin(SPI_MOSI_PIN))
cs = Pin(MAX7219_CS_PIN, Pin.OUT)
max_display = Max7219(64, 8, spi, cs)# 8 matrices (64 pixels wide, 8 pixels high)
max_display.fill(0)
max_display.text("READY GO",0,0,1)
max_display.show()


# --- Button Setup ---
coder_button = Pin(CODER_BUTTON_PIN, Pin.IN, Pin.PULL_UP)
undo_button = Pin(UNDO_BUTTON_PIN, Pin.IN, Pin.PULL_UP)
random_button = Pin(RANDOM_BUTTON_PIN, Pin.IN, Pin.PULL_UP)
player_buttons = [Pin(pin, Pin.IN, Pin.PULL_UP) for pin in PLAYER_BUTTON_PINS]

# --- Manage Active Invitations

# Global variables
current_invitation = None
invitation_timer = Timer(0)

class Invitation:
    def __init__(self, invite_type, position=None):
        """
        Create an invitation with a specific type.
        
        Args:
            invite_type: String "Coder" or "Player"
            position: Position number for player invitations (1-4)
        """
        self.type = invite_type
        self.position = position

def clear_invitation_and_display(timer):
    """
    Timer callback to clear invitation and update display.
    
    Args:
        timer: Timer instance (unused but required for callback)
    """
    global current_invitation
    if current_invitation:
        if current_invitation.type == "Coder":
            player_tracker.indicate_request(4, (0, 0, 0))
            player_tracker.stop_countdown()
        elif current_invitation.type == "Player":
            player_tracker.indicate_request(current_invitation.position-1, (0, 0, 0))
            player_tracker.stop_countdown()
        current_invitation = None
        print("Invitation expired")

def start_invitation(invite_type, position=None, timeout = 8000):
    """
    Start a new invitation if none exists.
    
    Args:
        invite_type: String "Coder" or "Player"
        position: Position number for player invitations (1-4)
    Returns:
        bool: True if invitation was started
    """
    global current_invitation
    if current_invitation:
        return False
        
    current_invitation = Invitation(invite_type, position)
    invitation_timer.init(mode=Timer.ONE_SHOT, period=timeout, 
                         callback=clear_invitation_and_display)
    return True



# --- Save and Load Game State ---
def save_game_state(filename = GAME_STATE_FILE):
    """Save the current game state to a file."""
    with open(filename, "w") as f:
        json.dump(game_state.to_dict(), f)
    print("Game state saved.")

def load_game_state(filename = GAME_STATE_FILE):
    """Load the game state from a file."""
    with open(filename, "r") as f:
        data = json.load(f)
        game_state.from_dict(data)
        player_tracker.reset_all_progress() # check this? 
        print("Previous game state loaded.")

def backup_and_load_previous_game():
    """Backup the current game and load the previous game state."""
    if os.path.exists(GAME_STATE_FILE): # If there is a saved game
        save_game_state("backup_" + GAME_STATE_FILE) # Save current game a backup
        load_game_state(GAME_STATE_FILE) # Load the saved game
    else:
        print("No Saved Game")
  
#---Broadcast Functions---
def send_to_close_modules(message, cutoff):
    rssi_buffer = []
    key_buffer = []
    networking.aen.ping(broadcast_mac)
    time.sleep(0.1)
    for key in networking.aen.rssi():
        rssi = networking.aen.rssi()[key][0]
        if rssi > cutoff:
            networking.aen.send(key, message)

# --- Button Handlers ---
def button_detect_long_press(pin, duration=100, feedback=None):
    """
    Waits for a button press of duration and a release 
    """
    start = time.ticks_ms()
    
    # Make sure button is held down for short duration (not noise)
    while time.ticks_diff(time.ticks_ms(),start)<duration:
        time.sleep_ms(10)      
        if pin.value():
            
            return False
        
    if feedback is not None:
        max_display.fill(0)
        max_display.text(feedback,0,0,1)
        max_display.show()
    while not pin.value(): #wait for release        
        time.sleep_ms(10)
        
    time.sleep_ms(50) # make sure release is finished
                                # maybe remove when invitiation tracking works
    return True
    
def add_coder_handler(pin):
    """Handler to initiate adding a coder."""
    if button_detect_long_press(pin) and game_state.state!="ACTIVE":
        if game_state.state == "COMPLETED":
            for position, player_data in game_state.players.items():
                if player_data["mac"]:  # if there's a player at this position
                    networking.aen.send(player_data["mac"], "Clear")
                player_tracker.set_button_led(position-1, 'unassigned')
            game_state.reset_game()
            max_display.fill(0)
            max_display.text("NEW GAME",0,0,1)
            max_display.show()
            player_tracker.clear_all()
            game_state.state = "SETUP"
            print("CLEAR?")
            time.sleep(.5)
        if start_invitation("Coder"):
            print("Inviting Coders...")
            #game_state.reset_game()
            max_display.fill(0)
            max_display.text("NEW GAME",0,0,1)
            max_display.show()
            #player_tracker.clear_all()
            
            #player_tracker.indicate_request(4, color=(0, 0, 255))
            send_to_close_modules('Coder', -60)
            player_tracker.start_countdown(4, 6000, (0,0,255))
        else:
            print("Invitation already pending")
    else:
        pass
        #print("Code Button Released Early")
        

def add_player_handler(pin, player_number):
    """
    Handler to initiate adding a specific player number.
    
    Args:
        pin: Button pin object
        player_number: Position number (1-4)
    """
    
    if button_detect_long_press(pin):
        print(game_state.state)
        if game_state.state == "COMPLETED":
            for position, player_data in game_state.players.items(): # Remove all players
                if player_data["mac"]:  # if there's a player at this position
                    networking.aen.send(player_data["mac"], "Clear")
                player_tracker.set_button_led(position-1, 'unassigned')
            game_state.reset_game()
            max_display.fill(0)
            max_display.text("NEW GAME",0,0,1)
            max_display.show()
            player_tracker.clear_all()
            game_state.state = "SETUP"
            print("CLEAR?")
            time.sleep(.5)
            
        if game_state.players[player_number]["mac"] is None:
            if start_invitation("Player", player_number):
                print(f"Inviting Player", player_number, "...")
                #player_tracker.indicate_request(player_number-1, color=(255, 0, 0))
                
                send_to_close_modules('Player ' + str(player_number), -60)
                player_tracker.start_countdown(player_number-1, 6000, (0,0,255))
            else:
                print("Invitation already pending")
        else:
            print(f"Player {player_number} is already assigned.")
    else:
        pass
        #print("Player Button Released Early")

def undo_handler(pin):
    """Handler to recover the previous game state."""
    print("Reset??")
    if button_detect_long_press(pin,duration=2000,feedback="RESET!"):
        print("Reset Game...")
        for position, player_data in game_state.players.items():
            if player_data["mac"]:  # if there's a player at this position
                networking.aen.send(player_data["mac"], "Clear")
            player_tracker.set_button_led(position-1, 'unassigned')
        game_state.reset_game()
        invitation_timer.deinit()  # Cancel timeout timer
        current_invitation = None  # Clear invitations        
        max_display.fill(0)
        max_display.text("NEW GAME",0,0,1)
        max_display.show()
        player_tracker.clear_all()
        game_state.state = "SETUP"
        print("CLEAR?")
        time.sleep(.5)
        #backup_and_load_previous_game()
        
    else:
        print("Reset released early")

def shuffle_handler(pin):
    """Handler to recover the previous game state."""
    if button_detect_long_press(pin):
        print("SHUFFLE")
        # TO DO

# Assign button handlers
coder_button.irq(trigger=Pin.IRQ_FALLING, handler=add_coder_handler)
undo_button.irq(trigger=Pin.IRQ_FALLING, handler=undo_handler)
random_button.irq(trigger=Pin.IRQ_FALLING, handler=shuffle_handler)

def create_handler(num):
    # Returns a handler function specific to the player number
    def handler(pin):
        add_player_handler(pin, num)
        
    return handler

for i, button in enumerate(player_buttons):
    button.irq(trigger=Pin.IRQ_FALLING, handler=create_handler(i + 1))


# --- ESP-NOW Receive Handler ---

def on_receive_callback():
    """Handle incoming ESP-NOW messages."""
    global current_invitation
    
    for mac, msg, rtime in networking.aen.return_messages():
        print('received', msg, type(msg))
        
        if msg == 'Coder':
            if current_invitation and current_invitation.type == "Coder":
                
                game_state.add_coder_to_list(mac) # also removes from players
                print(f"Coder list added: {mac}")
                num_coders = len(game_state.coders_list)
                player_tracker.set_button_led(0, (0,0,int(12*min(num_coders,10)))) 
                # max_display.fill(0)
                # max_display.text("CODE",0,0,1)
                # max_display.show()
                # player_tracker.indicate_request(4, (0,0,0))
                # invitation_timer.deinit()  # Cancel timeout timer
                # current_invitation = None  # Clear invitations
                # DO NOT CLEAR INVITATION / MULTIPLE CODERS ALLOWED
            

            else:
                print("No pending coder invitation")

        elif 'Player' in msg:
            if current_invitation and current_invitation.type == "Player":
                msg_position = msg[-1] #just in case we want to error check
                position = current_invitation.position
                if game_state.add_player(mac, position):
                    if len(game_state.sequence) > 0:
                        networking.aen.send(mac, game_state.sequence)
                    player_tracker.stop_countdown()
                    player_tracker.indicate_request(position-1, (0,0,0))
                    print(f"Player confirmed: {mac}")
                    player_tracker.set_button_led(position, "connected")
                invitation_timer.deinit()  # Cancel timeout timer
                current_invitation = None  # Clear invitations
                
            else:
                print("No pending player invitation")

        elif isinstance(msg, list):
            # Handle coder sequence
            print("List received, Game State:", game_state.state)
            if game_state.state == "ACTIVE":
                
                if game_state.get_player_position(mac) is not None: 
                    # Handle player progress update    
                    step = len(msg)
                    # Find player position from MAC address
                    position = game_state.get_player_position(mac)
                    if position is not None:
                        game_state.update_progress(mac, step)
                        player_tracker.update_player_progress(position-1, step, game_state.sequence)
                        print(f"Player at position {position} updated to step {step}")
                        if step == len(game_state.sequence):
                            count_complete = 0
                            player_tracker.set_button_led(position, "completed")
                            for __, player_data in game_state.players.items():
                                if player_data["progress"] == len(game_state.sequence):
                                    count_complete = count_complete + 1
                            if count_complete == game_state.player_count():
                                game_state.state = "COMPLETED"
                                print("GAME COMPLETE")
                                max_display.fill(0)
                                max_display.text("COMPLETE",0,0,1)
                                max_display.show()
                                player_tracker.set_button_led(0, "completed") #coder
                                # add button indication
                                
                            
                else:
                    print(f"Sequence received from nonplayer {mac}")

            elif game_state.state == "SETUP" or game_state.state == "COMPLETED":        
                        
                if mac in game_state.coders_list and len(msg)>0:
                    sequence = msg
                    #if len(game_state.sequence) == 0:   #if no coder sequence before and players registered, send to registered players
                        # Send sequence to all registered players
                    if game_state.state == "COMPLETED":
                        # Reset complete game
                        for position, player_data in game_state.players.items():
                            if player_data["mac"]:  # if there's a player at this position
                                networking.aen.send(player_data["mac"], "Clear")
                            player_tracker.set_button_led(position-1, 'unassigned')
                        game_state.reset_game()
                        max_display.fill(0)
                        max_display.text("NEW GAME",0,0,1)
                        max_display.show()
                        player_tracker.clear_all()
                        print("CLEAR?")
                        time.sleep(.5)
                    else:
                        # Send sequence to existing players
                        for position, player_data in game_state.players.items():
                            if player_data["mac"]:  # if there's a player at this position
                                networking.aen.send(player_data["mac"], sequence)

                    #save_game_state(GAME_STATE_FILE) # TODO this also saves "blank" games currently
                    #print('saving game state')
                    player_tracker.reset_all_progress()
                    game_state.set_sequence(sequence)
                    player_tracker.set_button_led(0, "connected") #coder button
                    player_tracker.display_coder_sequence(sequence)
                    max_display.fill(0)
                    max_display.draw_5x3_list(sequence)
                    max_display.show()
                    game_state.state = "ACTIVE"
                    print(f"Sequence received: {sequence}")
                else:
                    print(mac, "not in", game_state.coders_list) 

networking.aen.irq(on_receive_callback)

# --- Main Loop ---
def main():
    print("Game controller initialized. Waiting for input...")
    while True:
        time.sleep(0.5)

if __name__ == "__main__":
    main()